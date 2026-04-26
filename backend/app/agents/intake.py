"""Agent 1 of 11 — Intake Agent.

Converts a raw scientific hypothesis string into a fully-typed
``StructuredHypothesis``. Every downstream agent (Literature QC, Risk, Plan,
CRO) consumes this output, so the cardinal rule is:

    Never invent biology. If the user did not state it, return the sentinel
    string ``"missing_required_field"``.

Two execution modes:

- ``USE_STUB_AGENTS=true``        → ``_stub_intake`` returns a hardcoded,
  fully-populated demo hypothesis. Used for offline UI demos.
- LLM mode (default with key set) → instructor + OpenAI extracts a
  ``_IntakeLLMOutput`` using ``Mode.TOOLS`` (schema-enforced function calling).
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

from app.schemas import MISSING, ReadinessLevel, StructuredHypothesis
from app.services.llm import LLM_MAX_RETRIES, LLM_MODEL, USE_STUB_AGENTS, get_client

logger = logging.getLogger(__name__)


def _exception_chain_text(exc: BaseException) -> str:
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        parts.append(f"{current.__class__.__name__}: {current}")
        current = current.__cause__ or current.__context__
    return " -> ".join(parts)


DEMO_HYPOTHESIS = (
    "Replacing sucrose with trehalose as a cryoprotectant in the freezing medium "
    "will increase post-thaw viability of HeLa cells by at least 15 percentage "
    "points compared to the standard DMSO protocol, due to trehalose's superior "
    "membrane stabilization at low temperatures."
)


# ---------------------------------------------------------------------------
# LLM extraction model — only fields the LLM is allowed to fill in.
# original_hypothesis and missing_required_fields are computed in Python.
# ---------------------------------------------------------------------------


class _IntakeLLMOutput(BaseModel):
    """Schema enforced on the LLM via instructor TOOLS mode.

    Each field description tells the model exactly what qualifies, what does
    NOT qualify, and when to emit ``"missing_required_field"``.
    """

    intervention: str = Field(
        ...,
        description=(
            "The perturbation the experiment will apply, extracted as faithfully "
            "as possible from the user's text. "
            "PREFERRED: extract whatever the user named (compound class, technique, "
            "replacement, modification) verbatim, even if dose/concentration/delivery "
            "details are missing. e.g. for 'GLP-1 agonists in obese mice' extract "
            "'GLP-1 agonists' and add a clarifying_question for the missing dose. "
            "STRONG (best case): a concrete compound + dose/concentration + delivery, "
            "e.g. 'replace 10% DMSO with 200 mM trehalose in the freezing medium'. "
            "Return 'missing_required_field' ONLY when the user named no perturbation "
            "at all (pure goal statements like 'optimize the protocol' with no named "
            "perturbation)."
        ),
    )
    biological_system: str = Field(
        ...,
        description=(
            "The biological model being perturbed, extracted as faithfully as the "
            "user wrote it. "
            "PREFERRED: extract whatever was named, even if not fully specified. "
            "e.g. 'mammalian cells' → extract 'mammalian cells (specific cell line "
            "to be confirmed)' and add a clarifying_question; "
            "'mouse model' → extract 'mouse model (strain/sex/age TBD)'. "
            "STRONG (best case): a named cell line ('HeLa cells') or a fully-specified "
            "cohort ('C57BL/6 mice, male, 8-10 weeks'). "
            "Return 'missing_required_field' ONLY when no system is named at all."
        ),
    )
    comparator_or_control: str = Field(
        ...,
        description=(
            "The reference condition the intervention is measured against. "
            "PREFERRED: extract whatever the user named even if generic, e.g. "
            "'standard protocol' → extract 'standard protocol (to be specified)'; "
            "'untreated controls' → extract 'untreated controls'. "
            "STRONG (best case): a concretely-named control such as 'standard 10% "
            "DMSO freezing protocol' or 'vehicle-only DMSO at matched volume'. "
            "Return 'missing_required_field' ONLY when no comparator is mentioned."
        ),
    )
    measurable_outcome: str = Field(
        ...,
        description=(
            "The readout that will be quantified. "
            "PREFERRED: extract whatever the user named, even without a named assay. "
            "e.g. 'cell viability' → extract 'cell viability (assay to be specified)'; "
            "'tumor regression' → extract 'tumor regression (measurement method TBD)'. "
            "STRONG (best case): 'post-thaw viability by trypan blue exclusion', "
            "'EdU incorporation by flow cytometry', 'tumor volume by caliper'. "
            "Return 'missing_required_field' ONLY when no outcome is mentioned."
        ),
    )
    threshold: str = Field(
        ...,
        description=(
            "The success criterion. Numeric thresholds are strongly preferred. "
            "STRONG: 'at least 15 percentage points higher than DMSO control', "
            "'>=30% reduction vs vehicle', 'IC50 below 100 nM'. "
            "If the user expressed direction without a number ('improved', 'reduced'), "
            "extract the qualitative threshold and add a clarifying_question for the "
            "numeric target. "
            "Return 'missing_required_field' ONLY when no success criterion is "
            "mentioned at all."
        ),
    )
    mechanistic_rationale: str = Field(
        ...,
        description=(
            "The biological reason the intervention is expected to work. "
            "PREFERRED: extract whatever rationale the user gave, even if thin. "
            "e.g. 'because it stabilizes membranes' is acceptable as "
            "'stabilizes membranes (mechanism details TBD)'. "
            "STRONG (best case): 'trehalose replaces water molecules in phospholipid "
            "hydration shells, reducing membrane damage during ice crystal formation'. "
            "Return 'missing_required_field' ONLY when no rationale is given. "
            "Do NOT invent biology — only extract what was stated."
        ),
    )
    experiment_type: str = Field(
        ...,
        description=(
            "A short experiment-class label, inferred from the hypothesis even when "
            "the wording is loose. e.g. 'comparative_cryopreservation', "
            "'small_molecule_dose_response', 'in_vivo_efficacy_study', "
            "'cell_viability_assay', 'comparative_treatment_study'. "
            "Always provide your best-effort label. "
            "Return 'missing_required_field' ONLY if the input contains no scientific "
            "content at all (e.g. greetings, off-topic chatter)."
        ),
    )
    constraints: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Constraints the user EXPLICITLY stated in the hypothesis text only. "
            "Do NOT include constraints that were passed as separate budget/"
            "timeline/execution_mode arguments — those are merged in Python. "
            "If the user mentioned no constraints in the hypothesis itself, "
            "return an empty object {}."
        ),
    )
    readiness: ReadinessLevel = Field(  # type: ignore[assignment]
        ...,
        description=(
            "Classify the hypothesis: "
            "'execution_ready' = all 6 core fields present and specific; CRO-ready today. "
            "'pilot_ready' = core fields present but mechanism weak, threshold "
            "approximate, or comparator partially specified; needs scientist review. "
            "'underspecified' = missing ANY of intervention, biological_system, "
            "comparator_or_control, or measurable_outcome; pipeline cannot proceed."
        ),
    )
    readiness_rationale: str = Field(
        ...,
        description=(
            "1-2 sentence justification for the readiness label, naming the "
            "specific weak or missing fields if applicable."
        ),
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "0.0-1.0 self-assessed confidence in the extraction. Lower this "
            "score if you had to guess intent or if many fields were missing."
        ),
    )
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description=(
            "Concrete, actionable questions for the user, ONE per missing or "
            "weak field. Examples: 'What cell line are you using?', "
            "'What is the numeric success threshold (e.g. >=15% improvement)?'. "
            "Do NOT use generic prompts like 'please provide more detail'. "
            "Empty list if nothing is missing."
        ),
    )
    literature_search_hint: str = Field(
        ...,
        description=(
            "3-6 keywords synthesised from the hypothesis for the Literature "
            "QC agent. Include intervention compound/method, biological system, "
            "assay type, and key outcome. "
            "Example: 'trehalose DMSO cryopreservation HeLa viability trypan blue'."
        ),
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = """\
You are a senior wet-lab scientist with 15+ years of experience designing,
running, and reviewing experiments. You are reviewing a hypothesis a junior
scientist wants to take to a CRO. Your job is to extract a structured
representation that downstream planning agents can rely on.

A real lab will spend weeks and thousands of dollars based on this output.
Your job is to be PRACTICAL: extract what the user said, even when it is
incomplete, so the pipeline can produce a useful first draft. The user will
see clarifying_questions and refine the plan iteratively.

================================================================
PRIME DIRECTIVES
================================================================
DIRECTIVE 1 — Preserve, do not erase.
    If the user gave partial information, EXTRACT IT. Do NOT replace partial
    text with "missing_required_field" just because it lacks dose, units, or
    a specific assay name. Add a clarifying_question for the missing detail
    instead.

DIRECTIVE 2 — Never invent biology.
    Only extract what was actually written or trivially implied. Do not
    silently expand "standard DMSO protocol" into "10% DMSO in RPMI-1640".
    Do not assert a mechanism the user never mentioned.

DIRECTIVE 3 — Always produce a usable hypothesis.
    The pipeline must continue. "missing_required_field" is reserved for
    fields where the user provided NOTHING that could plausibly populate
    them. Lower confidence_score generously when extraction was partial,
    but populate the field whenever possible.

================================================================
SECTION 1 — What a strong hypothesis looks like
================================================================
The full target is below — but partial extraction is acceptable and
expected for many real hypotheses. Use clarifying_questions to fill gaps.

Intervention
  STRONG:   "replace 10% DMSO with 200 mM trehalose in the freezing medium"
  PARTIAL:  "GLP-1 agonists" → extract verbatim, ask for compound + dose
  ABSENT:   "improve drug discovery"  (no perturbation named at all)

Biological system
  STRONG:   "HeLa cells", "C57BL/6 mice, male, 8-10 weeks"
  PARTIAL:  "mammalian cells" → extract "mammalian cells (cell line TBD)"
  ABSENT:   only emit missing_required_field if no organism/system named

Comparator / control
  STRONG:   "standard 10% DMSO freezing protocol"
  PARTIAL:  "standard protocol" → extract verbatim, ask for the specific
            named protocol
  ABSENT:   no control mentioned at all → missing_required_field

Measurable outcome
  STRONG:   "post-thaw viability by trypan blue exclusion"
  PARTIAL:  "cell viability" → extract "cell viability (assay TBD)"
  ABSENT:   no outcome mentioned → missing_required_field

Threshold
  STRONG:   "at least 15 percentage points higher than DMSO control"
  PARTIAL:  "higher than control" → extract direction; ask for numeric target
  ABSENT:   no success criterion mentioned → missing_required_field

Mechanistic rationale
  STRONG:   "trehalose replaces water molecules in phospholipid hydration
             shells, reducing membrane damage during ice crystal formation"
  PARTIAL:  "stabilizes membranes" → extract; ask for detail
  ABSENT:   no rationale at all → missing_required_field

================================================================
SECTION 2 — Non-negotiable rules
================================================================
Rule 1: Prefer partial extraction over erasure (Directive 1).
Rule 2: Never invent biology (Directive 2).
Rule 3: Constraints in the constraints dict are ONLY constraints the user
        explicitly mentioned in the hypothesis text. Budget/timeline/
        execution_mode passed as separate arguments are merged in Python
        afterwards — do NOT copy them into this dict.
Rule 4: clarifying_questions must be specific and actionable. Not
        "please provide more detail" but "What cell line are you using?"
        or "What is the numeric success threshold (e.g. >=15% improvement)?"

================================================================
SECTION 3 — Readiness classification
================================================================
execution_ready
    All 6 core fields are present AND specific. CRO-ready today.

pilot_ready
    Core fields are populated (possibly with partial information) and the
    plan is workable for a pilot run. This is the typical case for a
    moderately-specified hypothesis. PREFER this label whenever you have
    a usable extraction even if some fields are partial.

underspecified
    Use ONLY if intervention, biological_system, comparator_or_control,
    AND measurable_outcome are ALL "missing_required_field" — i.e. the
    input contained essentially no extractable scientific content.

================================================================
SECTION 4 — literature_search_hint
================================================================
Always produce 3-6 keywords from whatever the user wrote, even if the
hypothesis is loose. The Literature QC agent needs SOME query to run.
Lower confidence_score if you had to extrapolate.
Example: "trehalose DMSO cryopreservation HeLa viability trypan blue"
"""


USER_PROMPT_TEMPLATE = """\
Extract a structured hypothesis from the input below.

Reminder:
  - PREFER partial extraction over erasure. If the user named a compound
    class, technique, or system without full detail, extract it verbatim
    and add a clarifying_question.
  - Use "missing_required_field" ONLY when a field has no extractable
    content at all.
  - Do not invent biology. Do not paraphrase a vague phrase into a specific
    one.

----- RAW USER HYPOTHESIS (verbatim) -----
{hypothesis}
----- END HYPOTHESIS -----

Caller-supplied operational context (separate from the hypothesis text;
do NOT echo these into the constraints dict — they are merged in Python):
  budget:         {budget}
  timeline:       {timeline}
  execution_mode: {execution_mode}

Return a fully-populated _IntakeLLMOutput object.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_constraints(
    budget: str | None,
    timeline: str | None,
    execution_mode: str | None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    constraints: dict[str, str] = {}
    if extra:
        constraints.update({k: v for k, v in extra.items() if v})
    if budget is not None:
        constraints["budget"] = budget
    if timeline is not None:
        constraints["timeline"] = timeline
    if execution_mode is not None:
        constraints["execution_mode"] = execution_mode
    return constraints


# ---------------------------------------------------------------------------
# Stub mode (USE_STUB_AGENTS=true) — hardcoded to the canonical demo only.
# ---------------------------------------------------------------------------


def _stub_intake(
    hypothesis: str,
    budget: str | None = None,
    timeline: str | None = None,
    execution_mode: str | None = None,
) -> StructuredHypothesis:
    """Return a fully-valid StructuredHypothesis hardcoded to the demo input.

    Only values explicitly present in the demo hypothesis string are used.
    No invented biology.
    """
    return StructuredHypothesis(
        intervention="replace sucrose with trehalose as the cryoprotectant in the freezing medium",
        biological_system="HeLa cells",
        comparator_or_control="standard DMSO protocol",
        measurable_outcome="post-thaw viability",
        threshold="at least 15 percentage points higher than the standard DMSO protocol",
        mechanistic_rationale=(
            "trehalose's superior membrane stabilization at low temperatures"
        ),
        experiment_type="comparative_cryopreservation",
        constraints=_build_constraints(budget, timeline, execution_mode),
        readiness="execution_ready",
        readiness_rationale=(
            "All six core fields are explicitly stated in the hypothesis with a "
            "concrete intervention, named cell line, defined comparator, named "
            "outcome, numeric threshold, and a biological mechanism."
        ),
        confidence_score=0.95,
        clarifying_questions=[],
        literature_search_hint="trehalose DMSO cryopreservation HeLa viability trypan blue",
        original_hypothesis=hypothesis,
    )


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def _is_network_error(exc: BaseException) -> bool:
    """True iff the exception chain is dominated by network/connection problems
    (DNS lookup failure, connect timeout, proxy block, OpenAI APIConnectionError).
    Distinguishes recoverable infrastructure failures from genuine API errors
    (auth, quota, malformed requests) where degraded fallback would be wrong.
    """
    chain = _exception_chain_text(exc).lower()
    network_tokens = (
        "connecterror",
        "apiconnectionerror",
        "connection error",
        "gaierror",
        "nodename nor servname",
        "name or service not known",
        "proxyerror",
        "timeout",
        "remotedisconnected",
    )
    return any(t in chain for t in network_tokens)


def _heuristic_intake(
    hypothesis: str,
    budget: str | None,
    timeline: str | None,
    execution_mode: str | None,
    failure_reason: str,
) -> StructuredHypothesis:
    """Deterministic, no-LLM fallback that keeps the user's actual text.

    Used only when the LLM is unreachable (network/DNS/proxy). We do NOT
    invent biology — we leave structured fields as MISSING and put the
    user's verbatim hypothesis in ``original_hypothesis`` and the search
    hint, so downstream agents and the frontend show input-specific output
    instead of identical mock data.
    """
    text = hypothesis.strip()
    return StructuredHypothesis(
        intervention=MISSING,
        biological_system=MISSING,
        comparator_or_control=MISSING,
        measurable_outcome=MISSING,
        threshold=MISSING,
        mechanistic_rationale=MISSING,
        experiment_type="unspecified",
        constraints=_build_constraints(budget, timeline, execution_mode),
        readiness="underspecified",
        readiness_rationale=(
            "Heuristic fallback: the LLM was unreachable so structured fields "
            f"could not be extracted. Underlying error: {failure_reason}. "
            "Pipeline continued in degraded mode using the user's verbatim text."
        ),
        confidence_score=0.2,
        clarifying_questions=[
            "Which intervention / compound / technique are you applying?",
            "Which biological system (cell line, organism, tissue)?",
            "What is the measurable outcome and the comparator?",
        ],
        literature_search_hint=text[:200],
        original_hypothesis=text,
    )


def run_intake_agent(
    hypothesis: str,
    budget: str | None = None,
    timeline: str | None = None,
    execution_mode: str | None = None,
) -> StructuredHypothesis:
    """Convert a raw hypothesis string into a typed ``StructuredHypothesis``.

    Mode selection:
      - ``USE_STUB_AGENTS=true`` → hardcoded demo stub.
      - Otherwise use schema-enforced LLM extraction. On *network* failure
        (DNS / proxy / timeout / APIConnectionError) we degrade to a heuristic
        fallback so the pipeline can still produce output reflecting the
        user's actual input. Genuine API errors (auth/quota/malformed) are
        re-raised so the caller can surface them properly.
    """
    if USE_STUB_AGENTS:
        return _stub_intake(hypothesis, budget, timeline, execution_mode)

    try:
        client = get_client()
        logger.info("Intake Agent: calling OpenAI model=%s …", LLM_MODEL)
        llm_output: _IntakeLLMOutput = client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_IntakeLLMOutput,
            max_retries=LLM_MAX_RETRIES,
            temperature=1,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(
                        hypothesis=hypothesis,
                        budget=budget if budget is not None else "not specified",
                        timeline=timeline if timeline is not None else "not specified",
                        execution_mode=execution_mode if execution_mode is not None else "not specified",
                    ),
                },
            ],
        )
        logger.info(
            "Intake Agent: OpenAI OK (intervention=%r, system=%r, readiness=%s)",
            llm_output.intervention[:60],
            llm_output.biological_system[:60],
            llm_output.readiness,
        )
    except Exception as exc:
        logger.exception("Intake Agent LLM call failed.")
        chain = _exception_chain_text(exc)
        if _is_network_error(exc):
            logger.warning(
                "Intake Agent network error — falling back to heuristic extraction. "
                "Pipeline will continue in degraded mode."
            )
            return _heuristic_intake(
                hypothesis=hypothesis,
                budget=budget,
                timeline=timeline,
                execution_mode=execution_mode,
                failure_reason=chain,
            )
        status_hint = ""
        lowered = chain.lower()
        if any(token in lowered for token in ("401", "unauthorized", "invalid_api_key")):
            status_hint = " | status_hint=401"
        elif any(token in lowered for token in ("429", "rate_limit", "quota")):
            status_hint = " | status_hint=429"
        raise RuntimeError(
            f"Intake Agent failed: {exc} | repr={exc!r} | chain={chain}{status_hint}"
        ) from exc

    merged_constraints = _build_constraints(
        budget=budget,
        timeline=timeline,
        execution_mode=execution_mode,
        extra=llm_output.constraints,
    )

    return StructuredHypothesis(
        intervention=llm_output.intervention,
        biological_system=llm_output.biological_system,
        comparator_or_control=llm_output.comparator_or_control,
        measurable_outcome=llm_output.measurable_outcome,
        threshold=llm_output.threshold,
        mechanistic_rationale=llm_output.mechanistic_rationale,
        experiment_type=llm_output.experiment_type,
        constraints=merged_constraints,
        readiness=llm_output.readiness,
        readiness_rationale=llm_output.readiness_rationale,
        confidence_score=llm_output.confidence_score,
        clarifying_questions=llm_output.clarifying_questions,
        literature_search_hint=llm_output.literature_search_hint,
        original_hypothesis=hypothesis,
    )


# ---------------------------------------------------------------------------
# Adapter for the orchestrator (which still passes a DemoRunRequest).
# This is intentionally minimal so the orchestrator and the legacy test
# import surface ``from app.agents.intake import run`` continue to work.
# ---------------------------------------------------------------------------


def run(request) -> StructuredHypothesis:  # type: ignore[no-untyped-def]
    from app.schemas import DemoRunRequest

    if not isinstance(request, DemoRunRequest):
        raise TypeError("run() expects a DemoRunRequest")

    def _opt(value: str) -> str | None:
        return None if value == MISSING else value

    return run_intake_agent(
        hypothesis=request.question,
        budget=_opt(request.constraints.budget),
        timeline=_opt(request.constraints.timeline),
        execution_mode=request.constraints.execution_mode.value,
    )


# ---------------------------------------------------------------------------
# CLI smoke test:  python -m app.agents.intake
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = run_intake_agent(
        hypothesis=DEMO_HYPOTHESIS,
        budget="$5,000",
        timeline="4 weeks",
        execution_mode="in_house",
    )
    print(json.dumps(result.model_dump(), indent=2))
    print(
        f"\nreadiness={result.readiness}  "
        f"confidence={result.confidence_score:.2f}  "
        f"missing_fields={len(result.missing_required_fields)}  "
        f"literature_search_hint={result.literature_search_hint!r}"
    )
