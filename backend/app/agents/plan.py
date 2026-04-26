"""Agent 6 of 11 — Plan Agent.

Generates a concrete, hypothesis-specific experiment plan using an LLM
(instructor + OpenAI). The plan follows Benchling-style protocol structure:
steps organised by day, each step including expected duration and safety notes,
and explicitly named positive/negative controls.

The LLM owns:
    * objective, experimental_design, controls (pos + neg)
    * step_by_step_protocol (6-10 steps, grouped by day)
    * assumptions, decision_criteria, reproducibility_notes
    * execution_readiness_score + execution_readiness_label

Python owns:
    * risk mitigation steps (appended deterministically from risk items)
    * step numbering
    * feedback_incorporated pass-through

Two execution modes:
- USE_STUB_AGENTS=true → returns the existing deterministic stub plan.
- Otherwise → LLM-powered via instructor.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

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
# LLM intermediate schemas
# ---------------------------------------------------------------------------


class _StepLLM(BaseModel):
    day: int = Field(..., description="Experimental day this step occurs on (1, 2, 3 ...).")
    description: str = Field(
        ...,
        description=(
            "Full step description including technique, key parameters (volumes, "
            "temperatures, durations), safety/handling notes, and expected outcome. "
            "Be concrete — avoid vague language like 'perform assay'."
        ),
    )
    sub_protocol: str = Field(
        ...,
        description=(
            "Name of the sub-protocol or technique this step belongs to "
            "(e.g. 'Cell culture', 'PCR', 'Gel electrophoresis', 'Data analysis'). "
            "Used for linking in the plan record."
        ),
    )
    expected_duration: str = Field(
        ...,
        description=(
            "Realistic time estimate for this step based on your knowledge of the "
            "technique (e.g. '2h', '45min', 'overnight', '30min setup + 12h incubation')."
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
            "Concrete positive control for this experiment — name the specific "
            "reagent, sample, or condition (not 'appropriate control')."
        ),
    )
    negative_control: str = Field(
        ...,
        description=(
            "Concrete negative control — name the specific blank, buffer-only, "
            "or reaction-minus-key-component condition."
        ),
    )
    steps: list[_StepLLM] = Field(
        ...,
        min_length=4,
        description=(
            "6–10 concrete protocol steps. Organise by day — any step with "
            "overnight incubation starts a new day. Include preparation steps "
            "and a final data analysis / results interpretation step."
        ),
    )
    assumptions: list[str] = Field(
        ...,
        description="2–4 explicit assumptions the plan rests on.",
    )
    decision_criteria: list[str] = Field(
        ...,
        description=(
            "2–3 criteria for deciding whether to proceed, pilot, or stop "
            "after seeing results."
        ),
    )
    reproducibility_notes: list[str] = Field(
        ...,
        description=(
            "2–3 notes on what must be recorded/standardised to ensure "
            "reproducibility (e.g. lot numbers, passage counts, timestamps)."
        ),
    )
    execution_readiness_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Score from 0.0 to 1.0 reflecting how ready this experiment is to "
            "execute as described. 1.0 = run today, 0.0 = major gaps remain."
        ),
    )
    execution_readiness_label: Literal[
        "execution_ready_after_review", "pilot_only", "blocked_pending_expert_review"
    ] = Field(
        ...,
        description=(
            "execution_ready_after_review: plan is sound, proceed after scientist sign-off. "
            "pilot_only: run a small pilot first to validate assumptions. "
            "blocked_pending_expert_review: critical gaps or risks prevent execution."
        ),
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a senior experimental scientist generating a detailed, actionable
experiment plan from a structured hypothesis.

Your plan must follow these structural conventions (derived from real lab
protocol standards):

STRUCTURE RULES:
1. Steps are organised by experimental day (DAY 1, DAY 2, ...). Any step
   involving overnight incubation, long culture periods, or multi-hour waiting
   starts a new day.
2. Each step includes: what is being done, key parameters (volumes,
   temperatures, concentrations), safety/handling notes, and expected duration.
3. Controls must be named concretely: state the actual reagent, sample, or
   condition (e.g. "wild-type untreated cells as negative control",
   "commercially validated positive control reagent X").
4. The plan ends with a data collection and results interpretation step.
5. Preparations needed before Day 1 (reagent preparation, overnight cultures,
   equipment booking) should be listed as a Day 0 or prep note.

CONTENT RULES:
- Base every step on the hypothesis fields provided. Do not invent unrelated
  experiments.
- If protocol candidates from protocols.io are provided, reference them in the
  relevant steps — but adapt them to fit the hypothesis, do not copy blindly.
- Use your knowledge of the scientific domain to generate realistic step
  descriptions and duration estimates. Do not use generic placeholder text.
- The execution_readiness_score should reflect genuine gaps or blockers in the
  hypothesis (e.g. underspecified dosing, missing controls, unvalidated model).
"""


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_protocol_candidates(candidates: list[ProtocolCandidate]) -> str:
    if not candidates:
        return "(none available)"
    lines = []
    for i, c in enumerate(candidates[:3]):
        lines.append(
            f"[{i}] {c.protocol_name} (fit={c.fit_score:.2f})\n"
            f"    Adaptation notes: {c.adaptation_notes}\n"
            f"    Limitations: {'; '.join(c.limitations) if c.limitations else 'none'}"
        )
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


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _generate_plan_with_llm(
    hypothesis: StructuredHypothesis,
    protocol_candidates: list[ProtocolCandidate],
    literature_qc: LiteratureQCResult,
    feedback_notes: list[str],
) -> _PlanLLMOutput:
    client = get_client()

    feedback_section = ""
    if feedback_notes:
        feedback_section = "\nPRIOR FEEDBACK TO INCORPORATE:\n" + "\n".join(
            f"- {note}" for note in feedback_notes
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
        "LITERATURE CONTEXT\n"
        f"{_format_literature_context(literature_qc)}\n\n"
        "AVAILABLE PROTOCOL CANDIDATES (from protocols.io)\n"
        f"{_format_protocol_candidates(protocol_candidates)}\n"
        f"{feedback_section}\n\n"
        "Generate a concrete, actionable experiment plan for this hypothesis."
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
                    description=f"Risk mitigation — {risk.risk_id}: {risk.mitigation}",
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
    """Generate an experiment plan for the given hypothesis.

    Args:
        hypothesis: Structured hypothesis from the intake agent.
        risks: Risk items from the risk agent (used for mitigation steps).
        feedback_incorporated: Prior feedback notes to incorporate.
        protocol_candidates: Candidate protocols from protocol retrieval.
        literature_qc: Literature QC result for context.

    Returns:
        A fully populated ExperimentPlan.
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

    try:
        llm_output = _generate_plan_with_llm(hypothesis, candidates, lit_qc, feedback_incorporated)

        controls = [llm_output.positive_control, llm_output.negative_control]
        if hypothesis.comparator_or_control and hypothesis.comparator_or_control not in controls:
            controls.append(hypothesis.comparator_or_control)

        protocol_steps = [
            ProtocolStep(
                step_number=i + 1,
                description=step.description,
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
