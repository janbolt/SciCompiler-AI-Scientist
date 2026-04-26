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
            "The specific perturbation the experiment will apply. "
            "QUALIFIES: a concrete compound + dose/concentration + delivery, e.g. "
            "'replace 10% DMSO with 200 mM trehalose in the freezing medium'. "
            "DOES NOT QUALIFY: vague goals like 'use a better cryoprotectant', "
            "'optimize the protocol', 'improve cryopreservation'. "
            "If the user did not state a concrete intervention, return the exact "
            "string 'missing_required_field'."
        ),
    )
    biological_system: str = Field(
        ...,
        description=(
            "The exact biological model being perturbed. "
            "QUALIFIES: a named cell line ('HeLa cells'), a strain + sex + age "
            "('C57BL/6 mice, male, 8-10 weeks'), or a defined primary culture. "
            "DOES NOT QUALIFY: 'mammalian cells', 'cells', 'a human cell line', "
            "'patient samples' without a defined cohort. "
            "If the user did not name a specific system, return "
            "'missing_required_field'."
        ),
    )
    comparator_or_control: str = Field(
        ...,
        description=(
            "The reference condition the intervention is measured against. "
            "QUALIFIES: a concretely-named control such as 'standard 10% DMSO "
            "freezing protocol' or 'vehicle-only DMSO at matched volume'. "
            "DOES NOT QUALIFY: 'compared to standard conditions', 'vs control', "
            "'vs baseline' with no protocol named. "
            "If absent, return 'missing_required_field'."
        ),
    )
    measurable_outcome: str = Field(
        ...,
        description=(
            "The specific assay or readout that will be quantified. "
            "QUALIFIES: 'post-thaw viability by trypan blue exclusion', "
            "'EdU incorporation by flow cytometry', 'tumor volume by caliper'. "
            "DOES NOT QUALIFY: 'cell survival', 'viability', 'response' without "
            "a named assay. "
            "If absent, return 'missing_required_field'."
        ),
    )
    threshold: str = Field(
        ...,
        description=(
            "The numeric success criterion. MUST contain a number AND a unit. "
            "QUALIFIES: 'at least 15 percentage points higher than DMSO control', "
            "'>=30% reduction vs vehicle', 'IC50 below 100 nM'. "
            "DOES NOT QUALIFY: 'higher than control', 'improved', 'better' "
            "without a numeric threshold. "
            "If no number is present, return 'missing_required_field'."
        ),
    )
    mechanistic_rationale: str = Field(
        ...,
        description=(
            "The biological reason the intervention is expected to work. "
            "QUALIFIES: 'trehalose replaces water molecules in phospholipid "
            "hydration shells, reducing membrane damage during ice crystal "
            "formation'. "
            "DOES NOT QUALIFY: 'because it is better', 'due to superior "
            "properties', 'it should work'. "
            "If absent or non-biological, return 'missing_required_field'."
        ),
    )
    experiment_type: str = Field(
        ...,
        description=(
            "A short experiment-class label, e.g. 'comparative_cryopreservation', "
            "'small_molecule_dose_response', 'in_vivo_efficacy_study'. "
            "If the hypothesis is too vague to classify, return "
            "'missing_required_field'."
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
Inventing biology that the user did not state is the single most damaging
failure mode. When in doubt, mark a field as "missing_required_field" and
ask the user a clarifying question.

================================================================
SECTION 1 — What a strong hypothesis requires
================================================================
For each core field, here is what counts as STRONG vs WEAK.

Intervention
  STRONG: "replace 10% DMSO with 200 mM trehalose in the freezing medium"
  WEAK:   "use a better cryoprotectant", "improve cryopreservation"

Biological system
  STRONG: "HeLa cells", "C57BL/6 mice, male, 8-10 weeks"
  WEAK:   "mammalian cells", "cells", "human cell line"

Comparator / control
  STRONG: "standard 10% DMSO freezing protocol"
  WEAK:   "compared to standard conditions"

Measurable outcome
  STRONG: "post-thaw viability by trypan blue exclusion"
  WEAK:   "cell survival", "viability"

Threshold
  STRONG: "at least 15 percentage points higher than DMSO control"
  WEAK:   "improved", "higher than"  (no number = NOT a threshold)

Mechanistic rationale
  STRONG: "trehalose replaces water molecules in phospholipid hydration
           shells, reducing membrane damage during ice crystal formation"
  WEAK:   "because it is better", "due to superior properties"

================================================================
SECTION 2 — Non-negotiable rules
================================================================
Rule 1: Never invent biology. If the user did not state it, return the
        exact sentinel string "missing_required_field". A false assumption
        can send a real lab down the wrong path for weeks.

Rule 2: Never paraphrase into invention. "standard DMSO protocol" stays
        "standard DMSO protocol" — do not silently expand it to
        "10% DMSO in RPMI-1640".

Rule 3: Goals are not hypotheses. "AI will improve drug discovery" is a
        goal — every core field for it is "missing_required_field".

Rule 4: Threshold requires a number. "Higher than control" with no number
        is "missing_required_field".

Rule 5: Mechanism requires biology. "Because it works better" is
        "missing_required_field".

Rule 6: Constraints in the constraints dict are ONLY constraints the user
        explicitly mentioned in the hypothesis text. If the user said
        nothing about budget, timeline, or other limits, leave constraints
        as an empty object. Budget/timeline/execution_mode passed as
        separate arguments are merged in Python afterwards — do NOT copy
        them into this dict.

Rule 7: clarifying_questions must be specific and actionable. Not
        "please provide more detail" but "What cell line are you using?"
        or "What is the numeric success threshold (e.g. >=15% improvement)?"

================================================================
SECTION 3 — Readiness classification
================================================================
execution_ready
    All 6 core fields (intervention, biological_system, comparator_or_control,
    measurable_outcome, threshold, mechanistic_rationale) are present and
    specific. The hypothesis could be handed to a CRO today.

pilot_ready
    Core fields are present but at least one is weak: mechanism is thin,
    threshold is approximate, or comparator is only partially specified.
    Needs a scientist review and probably a pilot run before scale-up.

underspecified
    ANY of intervention, biological_system, comparator_or_control, or
    measurable_outcome is missing. The pipeline cannot meaningfully proceed
    until the user fills the gap.

================================================================
SECTION 4 — literature_search_hint
================================================================
Synthesise 3-6 keywords from the hypothesis for the Literature QC agent.
Include: the intervention compound/method, the biological system, the
assay type, and the key outcome.

Example: "trehalose DMSO cryopreservation HeLa viability trypan blue"

If the hypothesis is too vague to extract keywords, emit the most useful
keywords you can and lower confidence_score accordingly.
"""


USER_PROMPT_TEMPLATE = """\
Extract a structured hypothesis from the input below.

Reminder: use the exact string "missing_required_field" for any field the
user did not explicitly state. Do not invent biology. Do not paraphrase a
vague phrase into a specific one.

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


def run_intake_agent(
    hypothesis: str,
    budget: str | None = None,
    timeline: str | None = None,
    execution_mode: str | None = None,
) -> StructuredHypothesis:
    """Convert a raw hypothesis string into a typed ``StructuredHypothesis``.

    Mode selection:
      - ``USE_STUB_AGENTS=true`` → hardcoded demo stub.
      - Otherwise use schema-enforced LLM extraction.
    """
    if USE_STUB_AGENTS:
        return _stub_intake(hypothesis, budget, timeline, execution_mode)

    try:
        client = get_client()
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
    except Exception as exc:
        logger.exception("Intake Agent LLM call failed.")
        raise RuntimeError(f"Intake Agent failed: {exc}") from exc

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
