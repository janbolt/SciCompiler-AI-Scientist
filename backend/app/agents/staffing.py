"""Agent 12 — Staffing Evaluation Agent.

Reads the experiment plan + timeline (with responsible_role per phase)
and produces a StaffingPlan: which roles are required, how many hours
each role contributes, hourly rates (EUR), and total staffing cost.

The LLM owns:
    * identifying which roles are needed and their skill requirements
    * assigning roles to phases
    * estimating hours per role
    * recommending hourly rates by seniority

Python owns:
    * recomputing total_cost_eur per role and total_staffing_cost_eur
      via @model_validator to eliminate LLM arithmetic errors

Two execution modes:
- USE_STUB_AGENTS=true → deterministic stub output.
- Otherwise → LLM-powered via instructor + Mode.TOOLS.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.schemas import (
    ExperimentPlan,
    StaffingPlan,
    StaffingRole,
    StructuredHypothesis,
    TimelineEstimate,
)
from app.services.llm import LLM_MAX_RETRIES, LLM_MODEL, USE_STUB_AGENTS, get_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM intermediate schemas
# ---------------------------------------------------------------------------


class _RoleLLM(BaseModel):
    role_title: str = Field(
        ...,
        description=(
            "Exact lab role title (e.g. 'Research Associate', 'Scientist', "
            "'Senior Scientist', 'PI', 'Bioinformatician', 'Lab Manager')."
        ),
    )
    required_skills: list[str] = Field(
        ...,
        description=(
            "Specific technical skills the role must have for this experiment "
            "(e.g. 'cell culture', 'qPCR', 'FACS', 'bioinformatics pipeline')."
        ),
    )
    phases_involved: list[str] = Field(
        ...,
        description=(
            "phase_name values from the supplied timeline that this role is "
            "responsible for. Must match exactly."
        ),
    )
    estimated_hours: float = Field(
        ...,
        ge=0.0,
        description="Total active working hours across the entire experiment for this role.",
    )
    hourly_rate_eur: float = Field(
        ...,
        ge=0.0,
        description=(
            "Loaded EUR hourly rate for this role at an academic or biotech lab. "
            "PI: 90–120; Senior Scientist: 70–90; Scientist: 50–70; "
            "Research Associate: 35–50; Bioinformatician: 55–75; "
            "Lab Manager: 40–55."
        ),
    )


class _StaffingLLMOutput(BaseModel):
    roles: list[_RoleLLM] = Field(
        ...,
        min_length=1,
        description=(
            "One entry per distinct role required to run this experiment. "
            "Do not pad — only include roles that are genuinely needed."
        ),
    )
    minimum_team_size: int = Field(
        ...,
        ge=1,
        description=(
            "Fewest people who could run this experiment (one person may "
            "cover multiple roles where skills allow)."
        ),
    )
    recommended_team_size: int = Field(
        ...,
        ge=1,
        description="Optimal team size for quality and timeline adherence.",
    )
    can_single_person_execute: bool = Field(
        ...,
        description=(
            "True only if a single scientist with the right skills can "
            "realistically run every phase without help."
        ),
    )
    cro_delegation_recommendation: str = Field(
        ...,
        description=(
            "Which specific phases or tasks would most benefit from CRO "
            "delegation, and why (cost, complexity, equipment access, "
            "specialist certification). Must name the phases."
        ),
    )
    staffing_notes: str = Field(
        ...,
        description=(
            "Caveats: parallel vs sequential role requirements, biosafety "
            "training, equipment-operator certifications, or single points "
            "of expertise that create bottlenecks."
        ),
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an experienced lab operations specialist staffing experimental
projects in academic and biotech laboratories. You evaluate the
experimental plan and timeline, then decide which roles are required,
how many active working hours each role contributes, and the realistic
loaded hourly cost in EUR.

STANDARD ACADEMIC / BIOTECH LAB ROLES AND LOADED HOURLY RATES (EUR):
  - PI                : 90–120 EUR/h
  - Senior Scientist  : 70–90  EUR/h
  - Scientist         : 50–70  EUR/h
  - Research Associate: 35–50  EUR/h
  - Bioinformatician  : 55–75  EUR/h
  - Lab Manager       : 40–55  EUR/h
These ranges are loaded costs (salary + overhead) — pick the value within
each range that matches the seniority required by the work.

RULES:
- Only include roles that are GENUINELY required for this experiment.
  Do not pad the role list.
- A Research Associate cannot independently run techniques requiring
  senior-level expertise (flow cytometry setup, high-content imaging,
  bioinformatics pipeline development, novel assay design). Capture such
  techniques in `required_skills` on the appropriate senior role.
- `phases_involved` must use the EXACT phase_name values from the supplied
  timeline. Do not invent phase names.
- `can_single_person_execute` = TRUE only if there are no parallel steps
  requiring two people simultaneously, no techniques requiring a second
  operator for safety (e.g. animal handling, BSL-2+ transfers), and the
  full skill set can plausibly live in one person.
- `cro_delegation_recommendation` must be SPECIFIC: name the phase(s) and
  state the reason (cost, required equipment access, specialist
  certification, throughput). Generic recommendations are not acceptable.
- `staffing_notes` should call out: parallel vs sequential constraints,
  biosafety training requirements, equipment-operator certifications, or
  single points of expertise that create bottlenecks.
- DO NOT compute total_cost_eur or total_staffing_cost_eur — Python will
  recompute these from estimated_hours × hourly_rate_eur after you respond.
"""


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _format_phases(timeline: TimelineEstimate) -> str:
    if not timeline.phases:
        return "(no phases supplied)"
    lines = []
    for i, p in enumerate(timeline.phases, start=1):
        lines.append(
            f"{i}. {p.phase_name} | role: {p.responsible_role} | duration: {p.duration_estimate}"
        )
    return "\n".join(lines)


def _format_steps(plan: ExperimentPlan) -> str:
    if not plan.step_by_step_protocol:
        return "(no steps available)"
    return "\n".join(
        f"Step {step.step_number}: {step.description}"
        for step in plan.step_by_step_protocol
    )


def _generate_staffing_with_llm(
    hypothesis: StructuredHypothesis,
    plan: ExperimentPlan,
    timeline: TimelineEstimate,
    scientist_feedback: str = "",
) -> _StaffingLLMOutput:
    client = get_client()

    feedback_block = ""
    if scientist_feedback.strip():
        feedback_block = (
            "\n=================================================================\n"
            "SCIENTIST FEEDBACK ON STAFFING — YOU MUST ADDRESS:\n"
            "=================================================================\n"
            f"{scientist_feedback.strip()}\n"
            "Adjust roles, hours, rates, team size, and CRO delegation\n"
            "recommendations to address every point above. If a requested\n"
            "change is unrealistic (e.g. one person executing an experiment\n"
            "that requires two-operator handling), state this in\n"
            "staffing_notes and choose the closest realistic configuration.\n"
        )

    user_message = (
        "HYPOTHESIS\n"
        f"- intervention: {hypothesis.intervention}\n"
        f"- biological_system: {hypothesis.biological_system}\n"
        f"- experiment_type: {hypothesis.experiment_type}\n\n"
        "TIMELINE PHASES (use these exact phase_name values in phases_involved)\n"
        f"{_format_phases(timeline)}\n\n"
        "PROTOCOL STEPS\n"
        f"{_format_steps(plan)}\n"
        f"{feedback_block}\n"
        "Determine the staffing required to run this experiment. Return roles, "
        "hours, rates, team-size recommendations, can_single_person_execute, "
        "a specific CRO delegation recommendation, and notable staffing notes."
    )

    return client.chat.completions.create(
        model=LLM_MODEL,
        response_model=_StaffingLLMOutput,
        max_retries=LLM_MAX_RETRIES,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )


# ---------------------------------------------------------------------------
# Builder helper
# ---------------------------------------------------------------------------


def _build_staffing_plan(
    llm_output: _StaffingLLMOutput,
    hypothesis: StructuredHypothesis,
) -> StaffingPlan:
    """Construct the StaffingPlan from the LLM intermediate schema.

    The @model_validator on StaffingPlan recomputes both per-role
    total_cost_eur and the top-level total_staffing_cost_eur from
    estimated_hours × hourly_rate_eur, so the LLM never owns arithmetic.
    """
    _ = hypothesis  # reserved for future hypothesis-aware adjustments
    roles: list[StaffingRole] = []
    for r in llm_output.roles:
        roles.append(
            StaffingRole(
                role_title=r.role_title,
                required_skills=list(r.required_skills),
                phases_involved=list(r.phases_involved),
                estimated_hours=float(r.estimated_hours),
                hourly_rate_eur=float(r.hourly_rate_eur),
                # placeholder; the validator will overwrite this with the
                # correct estimated_hours × hourly_rate_eur product.
                total_cost_eur=0.0,
            )
        )

    return StaffingPlan(
        roles=roles,
        minimum_team_size=int(llm_output.minimum_team_size),
        recommended_team_size=int(llm_output.recommended_team_size),
        can_single_person_execute=bool(llm_output.can_single_person_execute),
        # placeholder; the validator will overwrite this from the per-role sum.
        total_staffing_cost_eur=0.0,
        cro_delegation_recommendation=llm_output.cro_delegation_recommendation,
        staffing_notes=llm_output.staffing_notes,
    )


# ---------------------------------------------------------------------------
# Stub mode
# ---------------------------------------------------------------------------


def _stub_staffing(
    hypothesis: StructuredHypothesis | None = None,
    plan: ExperimentPlan | None = None,
    timeline: TimelineEstimate | None = None,
) -> StaffingPlan:
    _ = (hypothesis, plan, timeline)
    return StaffingPlan(
        roles=[
            StaffingRole(
                role_title="Research Associate",
                required_skills=["cell culture", "general bench techniques"],
                phases_involved=["Pilot experiment run", "Replicate confirmation run"],
                estimated_hours=40.0,
                hourly_rate_eur=45.0,
                total_cost_eur=0.0,  # validator recomputes
            ),
            StaffingRole(
                role_title="Scientist",
                required_skills=["protocol design", "data analysis"],
                phases_involved=["Data analysis and review"],
                estimated_hours=20.0,
                hourly_rate_eur=60.0,
                total_cost_eur=0.0,  # validator recomputes
            ),
        ],
        minimum_team_size=1,
        recommended_team_size=2,
        can_single_person_execute=True,
        total_staffing_cost_eur=0.0,  # validator recomputes
        cro_delegation_recommendation=(
            "Outsource data acquisition phases to a CRO when in-house "
            "throughput or specialist equipment becomes the bottleneck."
        ),
        staffing_notes="Standard single-PI lab setup sufficient for this protocol.",
    )


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def run(
    hypothesis: StructuredHypothesis | None = None,
    plan: ExperimentPlan | None = None,
    timeline: TimelineEstimate | None = None,
    scientist_feedback: str = "",
) -> StaffingPlan:
    """Generate a staffing plan for the experiment.

    Args:
        hypothesis: Structured hypothesis (required in live mode).
        plan: Experiment plan whose protocol steps inform skill needs.
        timeline: Timeline whose phase_name values drive phases_involved
            and whose responsible_role hints at the role mix.
        scientist_feedback: Free-text scientist corrections specifically
            targeting the staffing plan. Empty string = no feedback.

    Returns:
        A StaffingPlan with per-role hours/rates/costs, team-size
        recommendations, and a CRO delegation recommendation. All cost
        fields are recomputed by the @model_validator on StaffingPlan.
    """
    if USE_STUB_AGENTS or hypothesis is None or plan is None or timeline is None:
        return _stub_staffing(hypothesis, plan, timeline)

    try:
        llm_output = _generate_staffing_with_llm(
            hypothesis,
            plan,
            timeline,
            scientist_feedback=scientist_feedback,
        )
        return _build_staffing_plan(llm_output, hypothesis)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Staffing agent LLM call failed, falling back to stub: %s", exc)
        return _stub_staffing(hypothesis, plan, timeline)
