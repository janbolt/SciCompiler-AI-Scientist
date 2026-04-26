"""Agent 6 of 11 — Plan Agent.

Generates a concrete, hypothesis-specific experiment plan using an LLM
(instructor + OpenAI).

Key improvements over the original:
  * Complexity classification (simple/moderate/complex) scales the step count
    to 8-12 / 12-18 / 18-25 steps respectively.
  * Richer _StepLLM schema: equipment, reagents, expected_outcome, safety_note
    are extracted and embedded into the stored ProtocolStep.description so the
    frontend can render full expert-level steps without schema changes.
  * Actual protocols.io step text (raw_steps) is injected into the LLM prompt,
    giving it a real procedural skeleton to adapt — not just a 500-char abstract.
  * System prompt prohibits vague language and mandates numeric parameters.

The LLM owns:
    * objective, experimental_design, controls (pos + neg)
    * step_by_step_protocol (count scaled to complexity)
    * assumptions, decision_criteria, reproducibility_notes
    * execution_readiness_score + execution_readiness_label

Python owns:
    * complexity classification
    * step description formatting (embeds day/duration/equipment/outcome)
    * risk mitigation steps
    * step numbering
    * feedback_incorporated pass-through

Two execution modes:
- USE_STUB_AGENTS=true → returns the existing deterministic stub plan.
- Otherwise → LLM-powered via instructor.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import (
    ExperimentPlan,
    LiteratureQCResult,
    PlanAction,
    ProtocolCandidate,
    ProtocolStep,
    RiskItem,
    StructuredHypothesis,
)
from app.services.llm import LLM_MAX_RETRIES, LLM_MODEL, USE_STUB_AGENTS, get_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Complexity classification
# ---------------------------------------------------------------------------

_COMPLEX_KEYWORDS = {
    "bioelectrochemical", "electrosynthesis", "microbial electro",
    "multi", "omics", "sequencing", "genomic", "transcriptomic", "proteomic",
    "in_vivo", "in vivo", "clinical", "longitudinal", "chassis",
    "crispr", "gene editing", "directed evolution", "fermentation",
    "bioreactor", "chemostat", "anaerobic", "syntrophic",
}

_MODERATE_KEYWORDS = {
    "elisa", "western", "pcr", "qpcr", "culture", "flow cytometry",
    "immunofluorescence", "confocal", "cryopreservation", "dose response",
    "mass spectrometry", "hplc", "gc-ms", "rnaseq", "chip",
}


def _classify_complexity(hypothesis: StructuredHypothesis) -> Literal["simple", "moderate", "complex"]:
    """Classify hypothesis complexity to drive step count scaling."""
    text = " ".join([
        hypothesis.experiment_type or "",
        hypothesis.intervention or "",
        hypothesis.biological_system or "",
        hypothesis.mechanistic_rationale or "",
    ]).lower()

    if any(k in text for k in _COMPLEX_KEYWORDS):
        return "complex"
    if any(k in text for k in _MODERATE_KEYWORDS):
        return "moderate"
    return "simple"


_STEP_COUNT_MAP: dict[str, tuple[int, int]] = {
    "simple": (8, 12),
    "moderate": (12, 18),
    "complex": (18, 25),
}


# ---------------------------------------------------------------------------
# LLM intermediate schemas
# ---------------------------------------------------------------------------


class _StepLLM(BaseModel):
    day: int = Field(..., ge=0, description="Experimental day this step occurs on (0 = prep day before Day 1).")
    sub_protocol: str = Field(
        ...,
        description=(
            "Name of the sub-protocol or technique this step belongs to "
            "(e.g. 'Reactor assembly', 'Inoculation', 'Chronoamperometry', 'HPLC analysis')."
        ),
    )
    description: str = Field(
        ...,
        description=(
            "Complete procedural action for this step. Must include: "
            "what is being done, numeric parameters (exact volumes in µL/mL, "
            "temperatures in °C, centrifuge speeds in ×g, incubation times in min/h), "
            "and any critical handling notes. "
            "PROHIBITED: vague language like 'perform assay', 'analyse results', "
            "'prepare samples', 'add appropriate amount'."
        ),
    )
    expected_duration: str = Field(
        ...,
        description="Realistic time estimate, e.g. '45 min', '2 h', 'overnight (16 h)'.",
    )
    equipment: list[str] = Field(
        ...,
        description=(
            "Specific instruments and consumables needed for this step. "
            "Name the instrument model where known (e.g. 'Bio-Logic SP-150 potentiostat', "
            "'Eppendorf 5424 centrifuge', 'Shimadzu HPLC-LC-20A'). "
            "Include consumables: electrode type, filter pore size, plate format, etc."
        ),
    )
    reagents: list[str] = Field(
        default_factory=list,
        description=(
            "Specific reagents with concentrations, e.g. "
            "'50 mM NaHCO3 in ultrapure water', 'Sporomusa ovata ATCC 49399 stock culture'. "
            "Empty list if step is purely instrumental with no reagents."
        ),
    )
    expected_outcome: str = Field(
        ...,
        description=(
            "What a successful outcome looks like — a measurable, observable result "
            "(e.g. 'OCP stabilises within ±5 mV over 10 min', "
            "'OD600 reaches 0.4-0.6 within 48 h', 'acetate peak area >1000 mAU·s')."
        ),
    )
    safety_note: str = Field(
        default="",
        description=(
            "Specific safety or containment requirement for this step, or empty string "
            "if none. E.g. 'CO2 asphyxiation risk — operate in ventilated fume hood', "
            "'Anaerobic conditions — use Schlenk line or glove box'."
        ),
    )


class _PlanLLMOutput(BaseModel):
    objective: str = Field(
        ...,
        description="One clear sentence stating what this experiment aims to determine.",
    )
    experimental_design: str = Field(
        ...,
        description=(
            "2–3 sentences describing the overall design: how the experiment is "
            "structured, what is being compared, and the key gating logic."
        ),
    )
    positive_control: str = Field(
        ...,
        description=(
            "Concrete positive control — name the specific reagent, strain, or condition "
            "(e.g. 'known acetate-producing Sporomusa ovata culture at −400 mV vs SHE', "
            "'validated cryoprotectant: 10% DMSO standard protocol'). "
            "Not 'appropriate positive control'."
        ),
    )
    negative_control: str = Field(
        ...,
        description=(
            "Concrete negative control — e.g. "
            "'abiotic cathode at −400 mV vs SHE with sterile medium', "
            "'uninoculated medium blank', 'buffer-only reaction'. "
            "Not 'appropriate negative control'."
        ),
    )
    steps: list[_StepLLM] = Field(
        ...,
        min_length=6,
        description=(
            "Expert-level protocol steps. Count is specified in the user message "
            "based on experiment complexity. Steps must be ordered by day, cover "
            "the full arc from setup/prep to data collection and analysis."
        ),
    )
    assumptions: list[str] = Field(
        ...,
        description="2–4 explicit scientific assumptions the plan rests on.",
    )
    decision_criteria: list[str] = Field(
        ...,
        description=(
            "2–3 concrete, numeric criteria for deciding whether to proceed, "
            "run a pilot, or stop (e.g. 'Proceed if acetate rate ≥ 150 mmol/L/day')."
        ),
    )
    reproducibility_notes: list[str] = Field(
        ...,
        description=(
            "3–5 notes specifying what must be standardised: electrode lot numbers, "
            "strain passage count, medium batch, instrument calibration records, etc."
        ),
    )
    execution_readiness_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Score from 0.0 to 1.0 reflecting how ready this experiment is to execute. "
            "1.0 = run today, 0.0 = major gaps remain."
        ),
    )
    execution_readiness_label: Literal[
        "execution_ready_after_review", "pilot_only", "blocked_pending_expert_review"
    ] = Field(
        ...,
        description=(
            "execution_ready_after_review: plan is sound, proceed after scientist sign-off. "
            "pilot_only: run a small pilot first to validate key assumptions. "
            "blocked_pending_expert_review: critical gaps or risks prevent execution."
        ),
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a senior experimental scientist generating a CRO-ready, expert-level
protocol for a planned experiment. A real lab will execute this plan.

=====================================================================
STRUCTURE RULES
=====================================================================
1. Steps are ordered chronologically by day (day=0 for prep before Day 1).
   Any step with overnight incubation, long culture, or multi-hour passive
   waiting starts a new day.
2. Every step must cover exactly ONE logical operation at the bench —
   do not bundle unrelated actions into a single step.
3. The first 1–2 steps are always setup / reagent prep / equipment booking.
4. The final step is always data analysis and results interpretation with
   specific statistical tests named.

=====================================================================
CONTENT RULES — MANDATORY
=====================================================================
- PROHIBITED PHRASES: "perform assay", "analyse results", "prepare samples",
  "add appropriate amount", "incubate as needed", "standard conditions",
  "follow manufacturer instructions". These are not acceptable. Replace
  with the exact procedure.
- Every step description must include numeric parameters:
    * volumes: in µL or mL
    * temperatures: in °C
    * centrifuge / rpm / time: e.g. "centrifuge at 6,000 × g, 10 min, 4°C"
    * incubation times: in minutes or hours, never "overnight" without "~16 h"
    * electrode potentials: in mV vs SHE or Ag/AgCl
    * concentrations: in mM, µM, mg/mL, % w/v, OD units
- Equipment must be named specifically (brand and model where known).
- Reagents must include concentration and source grade where relevant.
- expected_outcome must be a numeric/observable criterion, not "step succeeds".

=====================================================================
PROTOCOLS.IO SOURCE STEPS — HOW TO USE THEM
=====================================================================
If protocol source steps are provided, treat them as expert procedural
skeletons. Adapt them to the specific hypothesis (organism, conditions,
readout), expand them with the required numeric parameters, and fill any
gaps identified by the adaptation_notes. Do not copy blindly — the
source protocol may be for a different system.

=====================================================================
COMPLEXITY AND STEP COUNT
=====================================================================
The required step count range is stated in the user message. You MUST
generate at least the minimum number of steps specified. For complex
multi-phase experiments, each phase (setup, operation, sampling, analysis)
should be represented by multiple steps.
"""


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_protocol_candidates(candidates: list[ProtocolCandidate]) -> str:
    if not candidates:
        return "(none available)"
    lines: list[str] = []
    for i, c in enumerate(candidates[:3]):
        lines.append(f"\n[{i}] {c.protocol_name} (fit={c.fit_score:.2f}, confidence={c.confidence:.2f})")
        if c.protocol_url:
            lines.append(f"    Source: {c.protocol_url}")
        lines.append(f"    Adaptation needed: {c.adaptation_notes}")
        if c.missing_steps:
            lines.append(f"    Missing: {'; '.join(c.missing_steps)}")
        if c.limitations:
            lines.append(f"    Limitations: {'; '.join(c.limitations)}")
        if c.raw_steps:
            lines.append(f"    SOURCE STEPS ({len(c.raw_steps)} steps fetched from protocols.io):")
            for j, step_text in enumerate(c.raw_steps[:15]):
                lines.append(f"      {j + 1}. {step_text}")
        else:
            lines.append("    (No raw steps available — infer procedure from hypothesis and training knowledge)")
    return "\n".join(lines)


def _format_literature_context(lit_qc: LiteratureQCResult) -> str:
    lines = [
        f"Novelty signal: {lit_qc.novelty_signal}",
        f"Explanation: {lit_qc.explanation}",
    ]
    if lit_qc.references:
        refs = "; ".join(r.title for r in lit_qc.references[:3])
        lines.append(f"Key references: {refs}")
    return "\n".join(lines)


def _format_step_description(step: _StepLLM) -> str:
    """Embed all _StepLLM fields into a rich description string."""
    day_label = f"DAY {step.day}" if step.day > 0 else "DAY 0 (PREP)"
    header = f"{day_label} | {step.expected_duration} | {step.sub_protocol}"

    parts = [header, step.description]

    if step.equipment:
        parts.append("Equipment: " + ", ".join(step.equipment))
    if step.reagents:
        parts.append("Reagents: " + ", ".join(step.reagents))
    if step.expected_outcome:
        parts.append(f"Expected outcome: {step.expected_outcome}")
    if step.safety_note:
        parts.append(f"Safety: {step.safety_note}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _generate_plan_with_llm(
    hypothesis: StructuredHypothesis,
    protocol_candidates: list[ProtocolCandidate],
    literature_qc: LiteratureQCResult,
    feedback_notes: list[str],
    complexity: Literal["simple", "moderate", "complex"],
) -> _PlanLLMOutput:
    client = get_client()

    min_steps, max_steps = _STEP_COUNT_MAP[complexity]

    feedback_section = ""
    if feedback_notes:
        feedback_section = (
            "\n=================================================================\n"
            "SCIENTIST FEEDBACK ON THE PLAN / PROTOCOL STEPS — YOU MUST ADDRESS:\n"
            "=================================================================\n"
            + "\n".join(f"- {note}" for note in feedback_notes)
            + "\n\n"
            "These corrections come from a scientist who reviewed an earlier\n"
            "version of this plan. You MUST incorporate every point in your\n"
            "regenerated steps, controls, decision criteria, and reproducibility\n"
            "notes. If a request is impossible (e.g. a step the technique does\n"
            "not allow), state this explicitly in the corresponding step's\n"
            "expected_outcome or in assumptions, then provide the closest\n"
            "feasible alternative.\n"
        )

    user_message = (
        "STRUCTURED HYPOTHESIS\n"
        f"- intervention: {hypothesis.intervention}\n"
        f"- biological_system: {hypothesis.biological_system}\n"
        f"- comparator_or_control: {hypothesis.comparator_or_control}\n"
        f"- measurable_outcome: {hypothesis.measurable_outcome}\n"
        f"- threshold: {hypothesis.threshold}\n"
        f"- mechanistic_rationale: {hypothesis.mechanistic_rationale}\n"
        f"- experiment_type: {hypothesis.experiment_type}\n"
        f"- readiness: {hypothesis.readiness}\n\n"
        f"COMPLEXITY: {complexity.upper()} — generate {min_steps}–{max_steps} steps minimum.\n\n"
        "LITERATURE CONTEXT\n"
        f"{_format_literature_context(literature_qc)}\n\n"
        "AVAILABLE PROTOCOL CANDIDATES (from protocols.io)\n"
        f"{_format_protocol_candidates(protocol_candidates)}\n"
        f"{feedback_section}\n\n"
        "Generate a complete, expert-level experiment plan for this hypothesis. "
        f"You MUST produce at least {min_steps} steps."
    )

    return client.chat.completions.create(
        model=LLM_MODEL,
        response_model=_PlanLLMOutput,
        max_retries=LLM_MAX_RETRIES,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )


# ---------------------------------------------------------------------------
# Risk mitigation integration
# ---------------------------------------------------------------------------


def _apply_risk_mitigations(
    steps: list[ProtocolStep],
    risks: list[RiskItem],
    execution_readiness_score: float,
    execution_readiness_label: str,
    decision_criteria: list[str],
) -> tuple[list[ProtocolStep], list[str], float, str, list[str]]:
    """Append mitigation steps for actionable risks; downgrade label/score if needed."""
    risk_mitigations_applied: list[str] = []
    label = execution_readiness_label
    score = execution_readiness_score
    criteria = list(decision_criteria)

    for risk in risks:
        if risk.action == PlanAction.modify_plan:
            risk_mitigations_applied.append(f"{risk.risk_id}: {risk.mitigation}")
            steps.append(
                ProtocolStep(
                    step_number=len(steps) + 1,
                    description=f"Mitigation step for {risk.risk_id}: {risk.mitigation}",
                    linked_to=f"risk:{risk.risk_id}",
                )
            )
        elif risk.action == PlanAction.downgrade_to_pilot:
            risk_mitigations_applied.append(f"{risk.risk_id}: downgraded to pilot ({risk.mitigation})")
            label = "pilot_only"
            score = min(score, 0.62)
            criteria.append("Pilot-only mode: do not scale to full run until replicate criteria are met.")
        elif risk.action == PlanAction.block_execution:
            risk_mitigations_applied.append(f"{risk.risk_id}: execution blocked ({risk.mitigation})")
            label = "blocked_pending_expert_review"
            score = 0.25
            criteria.append("Execution blocked pending expert scientific review.")

    return steps, risk_mitigations_applied, score, label, criteria


# ---------------------------------------------------------------------------
# Stub mode
# ---------------------------------------------------------------------------


def _stub_plan(
    hypothesis: StructuredHypothesis,
    risks: list[RiskItem],
    feedback_incorporated: list[str],
) -> ExperimentPlan:
    controls = [hypothesis.comparator_or_control]
    protocol_steps = [
        ProtocolStep(step_number=1, description="Standardize culture or sample conditions before treatment.", linked_to="user_input"),
        ProtocolStep(step_number=2, description=f"Prepare {hypothesis.comparator_or_control} (control) and intervention arms.", linked_to="hypothesis.intervention"),
        ProtocolStep(step_number=3, description="Apply intervention and log batch metadata.", linked_to="reproducibility"),
        ProtocolStep(step_number=4, description=f"Measure {hypothesis.measurable_outcome} per protocol.", linked_to="validation.primary_endpoint"),
        ProtocolStep(step_number=5, description="Record results and perform initial data analysis.", linked_to="results"),
    ]
    risk_mitigations_applied: list[str] = []
    label = "execution_ready_after_review"
    score = 0.75
    decision_criteria = [
        f"Proceed if intervention meets threshold: {hypothesis.threshold}.",
        "Request scientist review before execution approval.",
    ]

    protocol_steps, risk_mitigations_applied, score, label, decision_criteria = _apply_risk_mitigations(
        protocol_steps, risks, score, label, decision_criteria
    )

    return ExperimentPlan(
        objective=f"Evaluate whether {hypothesis.intervention} produces {hypothesis.measurable_outcome} under specified conditions.",
        experimental_design=f"Controlled {hypothesis.experiment_type} comparing {hypothesis.intervention} against {hypothesis.comparator_or_control}.",
        controls=list(dict.fromkeys(controls)),
        step_by_step_protocol=protocol_steps,
        assumptions=[
            "Sample handling and processing are standardized across arms.",
            "Reagent preparation follows documented SOP versions.",
        ],
        decision_criteria=decision_criteria,
        risk_mitigations_applied=risk_mitigations_applied,
        reproducibility_notes=[
            "Record operator, reagent lots, instrument settings, and timestamps per batch.",
            "Maintain identical assay conditions across all experimental arms.",
        ],
        execution_readiness_score=score,
        execution_readiness_label=label,  # type: ignore[arg-type]
        feedback_incorporated=feedback_incorporated,
    )


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def run(
    hypothesis: StructuredHypothesis,
    risks: list[RiskItem],
    feedback_incorporated: list[str],
    protocol_candidates: list[ProtocolCandidate] | None = None,
    literature_qc: LiteratureQCResult | None = None,
) -> ExperimentPlan:
    """Generate an expert-level experiment plan for the given hypothesis.

    Args:
        hypothesis: Structured hypothesis from the intake agent.
        risks: Risk items from the risk agent (used for mitigation steps).
        feedback_incorporated: Prior feedback notes to incorporate.
        protocol_candidates: Candidates from protocol retrieval (may include raw_steps).
        literature_qc: Literature QC result for context.

    Returns:
        A fully populated ExperimentPlan with rich, hypothesis-scaled steps.
    """
    if USE_STUB_AGENTS:
        return _stub_plan(hypothesis, risks, feedback_incorporated)

    candidates = protocol_candidates or []
    lit_qc = literature_qc or LiteratureQCResult(
        novelty_signal="not_found",
        references=[],
        confidence_score=0.0,
        explanation="No literature context available.",
        recommended_action="",
        search_coverage="none",
    )

    complexity = _classify_complexity(hypothesis)
    logger.info("Plan agent complexity=%s for experiment_type=%r", complexity, hypothesis.experiment_type)

    try:
        llm_output = _generate_plan_with_llm(
            hypothesis, candidates, lit_qc, feedback_incorporated, complexity
        )

        controls = [llm_output.positive_control, llm_output.negative_control]
        if hypothesis.comparator_or_control and hypothesis.comparator_or_control not in controls:
            controls.append(hypothesis.comparator_or_control)

        protocol_steps = [
            ProtocolStep(
                step_number=i + 1,
                description=_format_step_description(step),
                linked_to=step.sub_protocol or "hypothesis",
            )
            for i, step in enumerate(llm_output.steps)
        ]

        score = llm_output.execution_readiness_score
        label = llm_output.execution_readiness_label
        decision_criteria = list(llm_output.decision_criteria)

        protocol_steps, risk_mitigations_applied, score, label, decision_criteria = _apply_risk_mitigations(
            protocol_steps, risks, score, label, decision_criteria
        )

        return ExperimentPlan(
            objective=llm_output.objective,
            experimental_design=llm_output.experimental_design,
            controls=list(dict.fromkeys(controls)),
            step_by_step_protocol=protocol_steps,
            assumptions=llm_output.assumptions,
            decision_criteria=decision_criteria,
            risk_mitigations_applied=risk_mitigations_applied,
            reproducibility_notes=llm_output.reproducibility_notes,
            execution_readiness_score=score,
            execution_readiness_label=label,  # type: ignore[arg-type]
            feedback_incorporated=feedback_incorporated,
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("Plan agent LLM call failed, falling back to stub: %s", exc)
        return _stub_plan(hypothesis, risks, feedback_incorporated)
