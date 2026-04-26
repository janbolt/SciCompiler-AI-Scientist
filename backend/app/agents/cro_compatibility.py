"""CRO-Compatibility Classifier — bundle-only LLM reasoning.

DESIGN
────────────────────────────────────────────────────────────────────────────
Modern commercial CROs sell SERVICE BUNDLES (one quote, one deliverable),
not individual prep steps. A scientist sends one protocol section; the CRO
returns one quote covering the prep, execution, readout, analysis, and
reporting in that section.

Naïve per-step scoring marks every prep card as bespoke and misses that the
*coherent group* IS the quotable service. We fix this by giving the LLM
**full decision power** at the workflow level:

  • The LLM reads the entire plan and returns ONLY the positive bundles
    it can defend with named commercial CROs.
  • The backend derives per-card flags purely from bundle membership.
    Cards inside a bundle → cro_compatible=True with bundle metadata.
    Cards outside any bundle → cro_compatible=False, no negative reasoning.
    The frontend then renders nothing for those (no "Not CRO" pill).

We deliberately do NOT inject a hardcoded catalogue of services or decision
rules into the prompt. The LLM brings its own up-to-date knowledge of CRO
service lines (Synthego, Charles River, Eurofins, WuXi, FCDI, Azenta,
HistoWiz, …). Stripping the catalogue:
  • removes our prior bias toward a specific list,
  • lets the LLM generalise to services we haven't enumerated,
  • shortens the prompt for cheaper / faster / more reproducible calls.

Reproducibility tactics:
  • temperature = 1 (gpt-5.5 reasoning model rejects other values)
  • structured outputs via instructor (schema-enforced)
  • deterministic input ordering (cards iterated in plan order)
  • bundles must cite ≥1 real CRO (server-side guard) — anything the LLM
    can't back with a real provider name is dropped silently
  • card_ids in bundles are validated against real input ids; fabricated
    ids are dropped silently
  • when the LLM is unreachable we degrade to NO flags rather than an
    invented hardcoded heuristic — this preserves "the LLM decides" as
    the only way a card gets a positive flag
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.schemas import StructuredHypothesis
from app.services.llm import LLM_MAX_RETRIES, LLM_MODEL, USE_STUB_AGENTS, get_client

logger = logging.getLogger(__name__)


# ── Output schema ─────────────────────────────────────────────────────────────


class CROServiceBundle(BaseModel):
    """A coherent group of cards that, taken together, form a single
    quotable service line at a real commercial CRO."""

    bundle_name: str = Field(
        ...,
        description=(
            "Human-readable bundle name as it would appear on a CRO statement of work."
        ),
    )
    service_category: str = Field(
        ...,
        description=(
            "Short canonical slug describing the service category (your own choice; "
            "snake_case)."
        ),
    )
    card_ids: list[str] = Field(
        ...,
        description="experiment_id values from the input list that belong to this bundle.",
    )
    cro_examples: list[str] = Field(
        ...,
        min_length=1,
        description=(
            "2-3 specific commercial CROs that currently sell this exact bundle. "
            "Real provider names only — if you cannot cite at least one, do NOT "
            "propose this bundle."
        ),
    )
    rationale: str = Field(
        ...,
        description=(
            "One sentence explaining why these cards form a single quotable "
            "deliverable at the named CROs."
        ),
    )
    confidence: float = Field(..., ge=0.0, le=1.0)


class _BatchEvaluation(BaseModel):
    """Top-level structured response: bundles only.

    Per-card flags are derived server-side from bundle membership, so the
    LLM has no surface on which to invent negative verdicts.
    """

    bundles: list[CROServiceBundle]


class CROCompatibilityVerdict(BaseModel):
    """Per-card record consumed by the adapter.

    Built server-side, never produced directly by the LLM. Only the positive
    case (membership in a bundle) carries reasoning; the negative case is
    silent so the frontend can hide it.
    """

    experiment_id: str
    cro_compatible: bool
    bundle_name: str = ""
    routine_match: str = ""
    confidence: float = 0.0
    reason: str = ""
    blockers: list[str] = Field(default_factory=list)
    bundle_examples: list[str] = Field(default_factory=list)


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior R&D operations specialist with extensive experience placing
work at commercial CROs. You evaluate experimental protocols to identify
which groups of steps can be outsourced to a CRO as a single quoted
deliverable.

Modern commercial CROs sell SERVICE BUNDLES, not individual prep steps. A
scientist sends one protocol section; the CRO returns one quote covering
all the prep, execution, readout, analysis, and reporting in that section.

YOUR TASK
Read the experiment cards below and identify any GROUPS of cards that,
taken together, form a service line that a real commercial CRO currently
sells today. For each bundle you identify, return:
  • bundle_name        — clear, operational name as it would appear on a CRO statement of work
  • service_category   — short canonical slug (your own choice; snake_case)
  • card_ids           — the experiment_id values that belong to this bundle, echoed verbatim
  • cro_examples       — 2-3 specific real commercial CROs that currently sell this exact bundle
  • rationale          — one sentence on why these cards form one quotable deliverable
  • confidence         — 0.0 to 1.0

REASONING PRINCIPLES
  • Always reason at the WORKFLOW LEVEL, not the step level.  Single steps
    in isolation often look bespoke; the same steps as part of a coherent
    workflow are routinely outsourced.  If three or more cards together
    form a service line that a CRO would quote as one deliverable, that is
    a bundle even if individual cards look custom.
  • Use your own up-to-date knowledge of the commercial CRO industry.  Do
    not be limited by any examples in this prompt; consider the full range
    of services CROs sell today.
  • If you cannot name 2-3 real commercial CROs that currently sell a
    particular bundle, DO NOT propose it.  Speculative bundles are worse
    than no bundle.
  • A card is allowed to belong to no bundle — that is fine.  Do NOT label
    cards as "not CRO compatible" or emit any negative reasoning.  Your
    only job is to identify positive bundles you can defend.
  • Echo experiment_id values verbatim from the input.  Do not invent ids.
  • Do not force every card into a bundle.  Skip cards that genuinely have
    no commercial CRO offering.

OUTPUT
Return only the bundles you are confident in.  Empty bundles list is a
valid response when no part of the plan is bundle-quotable.
"""


USER_PROMPT_TEMPLATE = """\
HYPOTHESIS CONTEXT
  Original input    : {original_hypothesis}
  Experiment type   : {experiment_type}
  Intervention      : {intervention}
  Biological system : {biological_system}
  Measurable outcome: {measurable_outcome}

EXPERIMENT CARDS (full plan, in order)
{experiment_block}

Identify the CRO service bundles in this plan. Return only bundles you
can defend with named commercial CROs. Do not classify cards individually.
"""


# ── Public API ────────────────────────────────────────────────────────────────


def evaluate_batch(
    hypothesis: StructuredHypothesis,
    experiments: list[dict],
) -> dict[str, CROCompatibilityVerdict]:
    """Workflow-aware CRO compatibility evaluation in a single batched LLM call.

    Args:
        hypothesis:  Intake-agent output, used as plan-level context.
        experiments: List of dicts shaped::
                       {"id": str, "name": str, "duration": str,
                        "goal": str, "steps": list[str]}
                     Iterated in plan order; ``id`` is echoed back.

    Returns:
        Mapping experiment_id → CROCompatibilityVerdict for every input id.
        Cards inside an LLM-identified bundle carry positive metadata;
        cards outside any bundle carry a silent default (cro_compatible=False
        with no reason / no blockers) so the frontend can hide them.
    """
    if not experiments:
        return {}

    valid_ids = {exp["id"] for exp in experiments}

    if USE_STUB_AGENTS:
        logger.info("CRO-Compat Agent: stub mode — emitting no positive flags.")
        return _silent_default_for_all(experiments)

    try:
        client = get_client()
        logger.info(
            "CRO-Compat Agent: classifying %d experiments via %s (bundle-only LLM reasoning)",
            len(experiments),
            LLM_MODEL,
        )
        result: _BatchEvaluation = client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_BatchEvaluation,
            max_retries=LLM_MAX_RETRIES,
            temperature=1,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(
                        original_hypothesis=_safe(hypothesis.original_hypothesis),
                        experiment_type=_safe(hypothesis.experiment_type),
                        intervention=_safe(hypothesis.intervention),
                        biological_system=_safe(hypothesis.biological_system),
                        measurable_outcome=_safe(hypothesis.measurable_outcome),
                        experiment_block=_format_experiment_block(experiments),
                    ),
                },
            ],
        )

        # ── Validate bundles against the input ───────────────────────────────
        # Drop bundles with no valid card_ids or no commercial CRO citations.
        # Build a per-card lookup so the adapter can fill metadata directly.
        clean_bundles: list[CROServiceBundle] = []
        for b in result.bundles:
            real_ids = [cid for cid in b.card_ids if cid in valid_ids]
            if not real_ids:
                logger.warning(
                    "CRO-Compat Agent: dropping bundle %r — no valid card_ids.",
                    b.bundle_name,
                )
                continue
            real_examples = [e.strip() for e in (b.cro_examples or []) if e and e.strip()]
            if not real_examples:
                logger.warning(
                    "CRO-Compat Agent: dropping bundle %r — no commercial CRO examples cited.",
                    b.bundle_name,
                )
                continue
            if len(real_ids) != len(b.card_ids):
                logger.info(
                    "CRO-Compat Agent: bundle %r had fabricated ids; kept %d/%d real ones.",
                    b.bundle_name, len(real_ids), len(b.card_ids),
                )
            b.card_ids = real_ids
            b.cro_examples = real_examples
            clean_bundles.append(b)

        bundle_by_card: dict[str, CROServiceBundle] = {}
        for b in clean_bundles:
            for cid in b.card_ids:
                bundle_by_card.setdefault(cid, b)  # first bundle wins on conflict

        # ── Build the verdict map (positive only; silent default elsewhere) ──
        verdicts: dict[str, CROCompatibilityVerdict] = {}
        for exp in experiments:
            cid = exp["id"]
            bundle = bundle_by_card.get(cid)
            if bundle is None:
                verdicts[cid] = _silent_default(cid)
                continue

            verdicts[cid] = CROCompatibilityVerdict(
                experiment_id=cid,
                cro_compatible=True,
                bundle_name=bundle.bundle_name,
                routine_match=bundle.service_category,
                confidence=bundle.confidence,
                reason=bundle.rationale,
                blockers=[],
                bundle_examples=list(bundle.cro_examples),
            )

        compatible = sum(1 for v in verdicts.values() if v.cro_compatible)
        bundle_names = sorted({b.bundle_name for b in clean_bundles})
        logger.info(
            "CRO-Compat Agent: OK | %d/%d compatible across %d bundle(s): %s",
            compatible, len(verdicts), len(clean_bundles),
            ", ".join(bundle_names) if bundle_names else "(none)",
        )
        return verdicts

    except Exception as exc:  # noqa: BLE001 — pipeline must continue
        logger.exception(
            "CRO-Compat Agent: LLM call failed (%s) — emitting no positive flags.",
            type(exc).__name__,
        )
        return _silent_default_for_all(experiments)


# ── Helpers ───────────────────────────────────────────────────────────────────


_MAX_STEPS_IN_PROMPT = 10


def _safe(value: object) -> str:
    """Render hypothesis fields as strings, hiding our 'missing' sentinel."""
    text = str(value or "").strip()
    if not text or text == "missing_required_field":
        return "(not specified)"
    return text


def _format_experiment_block(experiments: list[dict]) -> str:
    parts: list[str] = []
    for idx, exp in enumerate(experiments, start=1):
        steps: list[str] = list(exp.get("steps", []))
        steps_text = "\n".join(
            f"      {i + 1}. {s}" for i, s in enumerate(steps[:_MAX_STEPS_IN_PROMPT])
        )
        if len(steps) > _MAX_STEPS_IN_PROMPT:
            steps_text += (
                f"\n      … and {len(steps) - _MAX_STEPS_IN_PROMPT} more "
                "step(s) omitted for brevity."
            )
        parts.append(
            f"  [{idx}] experiment_id : {exp['id']}\n"
            f"      name          : {exp.get('name', '')}\n"
            f"      duration      : {exp.get('duration', '')}\n"
            f"      goal          : {exp.get('goal', '')}\n"
            f"      steps         :\n{steps_text or '      (no steps)'}"
        )
    return "\n\n".join(parts)


def _silent_default(experiment_id: str) -> CROCompatibilityVerdict:
    """Verdict for cards the LLM did not place in any bundle.

    Carries no reasoning so the frontend can hide the card silently
    (no "Not CRO" pill, no negative tooltip).
    """
    return CROCompatibilityVerdict(
        experiment_id=experiment_id,
        cro_compatible=False,
        bundle_name="",
        routine_match="",
        confidence=0.0,
        reason="",
        blockers=[],
        bundle_examples=[],
    )


def _silent_default_for_all(experiments: list[dict]) -> dict[str, CROCompatibilityVerdict]:
    """Stub / failure path: every card gets a silent default."""
    return {exp["id"]: _silent_default(exp["id"]) for exp in experiments}


__all__ = [
    "CROCompatibilityVerdict",
    "CROServiceBundle",
    "evaluate_batch",
]
