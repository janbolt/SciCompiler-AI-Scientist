"""Agent 9 of 11 — Timeline Agent.

Reads the experiment plan's protocol steps and uses an LLM (instructor +
OpenAI) to assign realistic durations to each phase. The LLM reasons from
its training knowledge of how long experimental techniques take — nothing
is hardcoded.

Key structural rules (from real lab protocol conventions):
    * Any step with overnight incubation becomes its own day-phase.
    * Active working hours and total calendar days are tracked separately.
    * A risk buffer (approx 20%) is added per phase.
    * Multi-day experiments split into DAY N phases.

The LLM owns:
    * phase names, day assignment, duration estimates
    * dependencies, bottlenecks, risk buffers
    * responsible role per phase

Python owns:
    * building TimelinePhase + TimelineEstimate from LLM output
    * computing total_duration_estimate

Two execution modes:
- USE_STUB_AGENTS=true → returns deterministic stub output.
- Otherwise → LLM-powered via instructor.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.schemas import (
    ExperimentPlan,
    StructuredHypothesis,
    TimelineEstimate,
    TimelinePhase,
)
from app.services.llm import LLM_MAX_RETRIES, LLM_MODEL, USE_STUB_AGENTS, get_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM intermediate schemas
# ---------------------------------------------------------------------------


class _PhaseLLM(BaseModel):
    phase_name: str = Field(
        ...,
        description="Descriptive name for this phase (e.g. 'Day 1: Sample preparation', 'Day 2-3: Treatment and incubation').",
    )
    day: int = Field(
        ...,
        ge=1,
        description="Which experimental day this phase starts on.",
    )
    duration_hours: float = Field(
        ...,
        ge=0.0,
        description=(
            "Active working hours required within this phase (excludes passive "
            "incubation/waiting time). E.g. 2.0 hours active work even if overnight "
            "incubation follows."
        ),
    )
    duration_days: int = Field(
        ...,
        ge=1,
        description=(
            "Total calendar days consumed by this phase, including any overnight "
            "or long incubation periods. E.g. a step with 1h active work + overnight "
            "incubation = 2 calendar days."
        ),
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Names of phases that must complete before this phase can start.",
    )
    responsible_role: str = Field(
        ...,
        description="Who typically runs this phase (e.g. 'Research associate', 'Scientist', 'PI').",
    )
    risk_buffer_days: int = Field(
        ...,
        ge=0,
        description=(
            "Additional calendar days as a risk buffer (~20% of duration_days, "
            "minimum 1 for critical phases). Accounts for failed runs, repeat steps, "
            "equipment downtime."
        ),
    )
    bottlenecks: list[str] = Field(
        default_factory=list,
        description="Specific factors that could delay this phase.",
    )


class _TimelineLLMOutput(BaseModel):
    phases: list[_PhaseLLM] = Field(
        ...,
        min_length=2,
        description=(
            "Phases covering the full experiment from preparation to results. "
            "Any protocol step with overnight incubation, long culture periods, "
            "or significant waiting time must be split into its own phase. "
            "The final phase should be data analysis and results interpretation."
        ),
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an experienced lab scientist estimating how long an experiment will
take to complete, phase by phase.

You will receive:
1. A structured hypothesis describing the experiment.
2. The experiment plan's protocol steps.

Your job is to build a realistic phase-by-phase timeline based on your
knowledge of how long different experimental techniques take.

RULES:
- Use your training knowledge of technique durations. Do not make up durations
  for techniques you know — common ones have well-established timing:
    * Cell culture passaging: 30-45min active, cells need 24-48h to settle
    * PCR (setup + run + cleanup + gel): ~3.75h total
    * Gel electrophoresis: 1-1.5h
    * Overnight incubation: creates a new day (1 active + 1 calendar day)
    * DNA extraction/precipitation: can be 2+ day protocols
    * Miniprep: 45-60min
    * Western blot: 4-8h
    * ELISA: 4-6h + overnight blocking
    * Flow cytometry: 2-4h
    * Sequencing: send same day, results next day or later
  For less common techniques, estimate conservatively (longer rather than shorter).

- Any step with overnight incubation, long culture, or multi-hour passive
  waiting MUST be a separate phase spanning multiple calendar days.

- Active working hours (duration_hours) and calendar days (duration_days) are
  tracked separately. A phase with 2h active work + overnight wait = 2 days.

- Risk buffers should be ~20% of duration_days, minimum 1 day for key phases.

- List concrete bottlenecks (equipment booking, reagent lead time, repeat runs,
  biological variability) — not generic placeholders.

- The last phase is always data analysis and results write-up.

- Responsible roles: use realistic lab roles (Research associate, Scientist,
  Senior scientist, PI, Bioinformatician, Lab manager).
"""


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _format_steps(plan: ExperimentPlan) -> str:
    lines = []
    for step in plan.step_by_step_protocol:
        lines.append(f"Step {step.step_number}: {step.description}")
    return "\n".join(lines) if lines else "(no steps available)"


def _generate_timeline_with_llm(
    hypothesis: StructuredHypothesis,
    plan: ExperimentPlan,
    scientist_feedback: str = "",
) -> _TimelineLLMOutput:
    client = get_client()

    feedback_block = ""
    if scientist_feedback.strip():
        feedback_block = (
            "\n=================================================================\n"
            "SCIENTIST FEEDBACK ON TIMELINE — YOU MUST ADDRESS:\n"
            "=================================================================\n"
            f"{scientist_feedback.strip()}\n"
            "Adjust phase durations, ordering, parallelisation, and risk buffers\n"
            "to address every point above. If a requested change is unrealistic\n"
            "(e.g. a duration shorter than physically possible for the technique),\n"
            "state this explicitly in the corresponding phase's bottlenecks list\n"
            "and choose the closest realistic value.\n"
        )

    user_message = (
        "HYPOTHESIS\n"
        f"- intervention: {hypothesis.intervention}\n"
        f"- biological_system: {hypothesis.biological_system}\n"
        f"- experiment_type: {hypothesis.experiment_type}\n\n"
        "PROTOCOL STEPS\n"
        f"{_format_steps(plan)}\n"
        f"{feedback_block}\n"
        "Generate a realistic phase-by-phase timeline for this experiment."
    )

    return client.chat.completions.create(
        model=LLM_MODEL,
        response_model=_TimelineLLMOutput,
        max_retries=LLM_MAX_RETRIES,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )


# ---------------------------------------------------------------------------
# Builder helper
# ---------------------------------------------------------------------------


def _build_timeline(llm_output: _TimelineLLMOutput) -> TimelineEstimate:
    phases: list[TimelinePhase] = []
    total_days = 0

    for p in llm_output.phases:
        phases.append(
            TimelinePhase(
                phase_name=p.phase_name,
                duration_estimate=f"{p.duration_days} days",
                dependencies=p.dependencies,
                responsible_role=p.responsible_role,
                risk_buffer=f"{p.risk_buffer_days} days",
                bottlenecks=p.bottlenecks,
            )
        )
        total_days += p.duration_days + p.risk_buffer_days

    return TimelineEstimate(
        phases=phases,
        total_duration_estimate=f"{total_days} days (including risk buffers)",
    )


# ---------------------------------------------------------------------------
# Stub mode
# ---------------------------------------------------------------------------


def _stub_timeline(
    hypothesis: StructuredHypothesis | None = None,
    plan: ExperimentPlan | None = None,
) -> TimelineEstimate:
    return TimelineEstimate(
        phases=[
            TimelinePhase(
                phase_name="Protocol finalisation and reagent verification",
                duration_estimate="3 days",
                dependencies=[],
                responsible_role="Research associate",
                risk_buffer="1 day",
                bottlenecks=["Supplier confirmation", "SOP sign-off"],
            ),
            TimelinePhase(
                phase_name="Pilot experiment run",
                duration_estimate="5 days",
                dependencies=["Protocol finalisation and reagent verification"],
                responsible_role="Scientist",
                risk_buffer="2 days",
                bottlenecks=["Sample preparation", "Equipment availability"],
            ),
            TimelinePhase(
                phase_name="Replicate confirmation run",
                duration_estimate="7 days",
                dependencies=["Pilot experiment run"],
                responsible_role="Scientist",
                risk_buffer="2 days",
                bottlenecks=["Biological replicate scheduling"],
            ),
            TimelinePhase(
                phase_name="Data analysis and review",
                duration_estimate="3 days",
                dependencies=["Replicate confirmation run"],
                responsible_role="PI",
                risk_buffer="1 day",
                bottlenecks=["Statistical review turnaround"],
            ),
        ],
        total_duration_estimate="24 days (including risk buffers)",
    )


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def run(
    hypothesis: StructuredHypothesis | None = None,
    plan: ExperimentPlan | None = None,
    scientist_feedback: str = "",
) -> TimelineEstimate:
    """Generate a timeline estimate for the experiment.

    Args:
        hypothesis: Structured hypothesis (required in live mode).
        plan: Experiment plan whose steps drive phase inference.
        scientist_feedback: Free-text scientist corrections specifically
            targeting the timeline. Injected into the LLM prompt with
            mandatory-address language. Empty string = no feedback.

    Returns:
        A TimelineEstimate with phases and total duration.
    """
    if USE_STUB_AGENTS or hypothesis is None or plan is None:
        return _stub_timeline(hypothesis, plan)

    try:
        llm_output = _generate_timeline_with_llm(hypothesis, plan, scientist_feedback=scientist_feedback)
        return _build_timeline(llm_output)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Timeline agent LLM call failed, falling back to stub: %s", exc)
        return _stub_timeline(hypothesis, plan)
