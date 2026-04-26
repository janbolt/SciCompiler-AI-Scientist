"""
adapters.py
-----------
Transforms internal agent outputs into the FrontendPlanData shape that the
React frontend consumes verbatim.  All field-name mismatches, enum remappings,
and structural reshaping are handled here — not in agents or orchestrator logic.
"""
from __future__ import annotations

import re

from .schemas import (
    BudgetEstimate,
    DemoRunResponse,
    ExperimentPlan,
    FrontendBudget,
    FrontendBudgetLine,
    FrontendExperiment,
    FrontendMaterial,
    FrontendPhase,
    FrontendPlanData,
    FrontendReference,
    LiteratureQCResult,
    MaterialItem,
    StructuredHypothesis,
    TimelineEstimate,
    ValidationPlan,
)

# ── Novelty signal ────────────────────────────────────────────────────────────

# Keys are plain strings (matching the Literal type on LiteratureQCResult),
# not NoveltySignal enum instances.
_NOVELTY_MAP: dict[str, str] = {
    "not_found": "not found",
    "similar_work_exists": "similar work exists",
    "exact_match_found": "exact match found",
}


def _map_novelty(signal: str) -> str:
    return _NOVELTY_MAP.get(signal, "not found")


# ── References ────────────────────────────────────────────────────────────────

def _map_references(lit_qc: LiteratureQCResult) -> list[FrontendReference]:
    refs = []
    for r in lit_qc.references:  # was: lit_qc.relevant_references
        # Build citation from available fields
        citation = r.title
        if r.published_year:  # was: r.year
            citation = f"{r.title} ({r.published_year})"
        if r.relevance_note:  # was: r.source (doesn't exist on ProtocolReference)
            citation = f"{citation}. {r.relevance_note}."

        # Extract DOI from protocol_url if present (doi.org/10.xxx), else blank
        doi = ""
        if r.protocol_url and "doi.org" in r.protocol_url:  # was: r.url
            doi = r.protocol_url.split("doi.org/", 1)[-1]

        refs.append(FrontendReference(citation=citation, doi=doi))
    return refs


# ── Phases ────────────────────────────────────────────────────────────────────

def _parse_days(duration_estimate: str) -> int:
    """Extract the leading integer from a string like '3 days' or '2 weeks'."""
    match = re.search(r"\d+", duration_estimate)
    if not match:
        return 1
    value = int(match.group())
    lower = duration_estimate.lower()
    if "week" in lower:
        return value * 7
    if "month" in lower:
        return value * 30
    return value


def _map_phases(timeline: TimelineEstimate) -> list[FrontendPhase]:
    return [
        FrontendPhase(
            name=p.phase_name,
            days=_parse_days(p.duration_estimate),  # was: p.estimated_duration_days
        )
        for p in timeline.phases
    ]


# ── Budget ────────────────────────────────────────────────────────────────────

def _build_budget(experiments: list[FrontendExperiment]) -> FrontendBudget:
    """
    Derive a structured budget from the experiment materials.

    Split into three categories by heuristic:
      fixed    — equipment/infrastructure one-off fees
      staff    — researcher time (8h/experiment-day at 45 EUR/h)
      recurring — all consumable materials
    """
    recurring: list[FrontendBudgetLine] = []
    for exp in experiments:
        for m in exp.materials:
            recurring.append(FrontendBudgetLine(
                item=f"{m.name} ({exp.name})",
                cost_eur=m.total_eur,
            ))

    fixed = [
        FrontendBudgetLine(
            item="Equipment use fees (plate reader, centrifuge, imaging)",
            cost_eur=320.0,
        ),
    ]

    total_days = sum(
        int(e.duration.split()[0]) if e.duration.split()[0].isdigit() else 3
        for e in experiments
    )
    staff_hours = total_days * 8
    staff = [
        FrontendBudgetLine(
            item=f"Researcher time ({staff_hours}h × 45 EUR/h)",
            cost_eur=round(staff_hours * 45.0, 2),
        )
    ]

    total = (
        sum(b.cost_eur for b in fixed)
        + sum(b.cost_eur for b in staff)
        + sum(b.cost_eur for b in recurring)
    )

    return FrontendBudget(
        fixed=fixed,
        staff=staff,
        recurring=recurring,
        total_eur=round(total, 2),
    )


# ── Experiments ───────────────────────────────────────────────────────────────

def _map_experiments(demo: DemoRunResponse) -> list[FrontendExperiment]:
    """
    Build one FrontendExperiment from the single ExperimentPlan produced by
    the pipeline, joined with materials, budget, validation, and timeline.
    """
    plan: ExperimentPlan = demo.plan
    materials: list[MaterialItem] = demo.materials
    budget: BudgetEstimate = demo.budget
    validation: ValidationPlan = demo.validation
    timeline: TimelineEstimate = demo.timeline
    hypothesis: StructuredHypothesis = demo.hypothesis

    # Build a cost lookup by item name from the budget line items
    cost_by_name: dict[str, tuple[float, float]] = {}
    for line in budget.line_items:
        cost_by_name[line.item_name.lower()] = (
            line.unit_cost_estimate,
            line.total_cost_estimate,
        )

    frontend_materials: list[FrontendMaterial] = []
    for m in materials:
        unit_cost, total = cost_by_name.get(m.item_name.lower(), (0.0, 0.0))
        frontend_materials.append(FrontendMaterial(
            name=m.item_name,
            catalog=m.catalog_number or "verify_before_ordering",
            supplier=m.supplier,
            qty=m.quantity,
            unit_cost_eur=unit_cost,
            total_eur=total,
        ))

    cro_compatible = plan.execution_readiness_label != "blocked_pending_expert_review"

    return [
        FrontendExperiment(
            id=demo.plan_id,
            name=hypothesis.experiment_type.replace("_", " ").title(),
            duration=timeline.total_duration_estimate,
            cro_compatible=cro_compatible,
            goal=plan.objective,
            success_criteria=validation.success_threshold,
            steps=[s.description for s in plan.step_by_step_protocol],
            materials=frontend_materials,
        )
    ]


# ── Objective ─────────────────────────────────────────────────────────────────

def _derive_objective(hypothesis: StructuredHypothesis) -> str:
    """Build a one-sentence objective from the structured hypothesis fields."""
    intervention = hypothesis.intervention
    outcome = hypothesis.measurable_outcome  # was: hypothesis.outcome
    if intervention != "missing_required_field" and outcome != "missing_required_field":
        return (
            f"Evaluate whether {intervention} produces "
            f"{outcome} under the specified experimental conditions."
        )
    return "Evaluate the stated hypothesis under controlled experimental conditions."


# ── Top-level transformers ────────────────────────────────────────────────────

def to_frontend_plan(
    hypothesis: StructuredHypothesis,
    lit_qc: LiteratureQCResult,
    timeline: TimelineEstimate,
    experiments: list[FrontendExperiment],
) -> FrontendPlanData:
    """
    Assemble a FrontendPlanData object from individual agent outputs.
    This is the single point of truth for the frontend JSON contract.
    """
    return FrontendPlanData(
        hypothesis=hypothesis.original_hypothesis,  # was: hypothesis.raw_input
        objective=_derive_objective(hypothesis),
        novelty_signal=_map_novelty(lit_qc.novelty_signal),  # type: ignore[arg-type]
        references=_map_references(lit_qc),
        phases=_map_phases(timeline),
        experiments=experiments,
        budget=_build_budget(experiments),
    )


def demo_response_to_frontend(demo: DemoRunResponse) -> FrontendPlanData:
    """Convert a full DemoRunResponse into the FrontendPlanData the UI consumes."""
    experiments = _map_experiments(demo)
    fp = to_frontend_plan(
        hypothesis=demo.hypothesis,
        lit_qc=demo.literature_qc,
        timeline=demo.timeline,
        experiments=experiments,
    )
    fp.confidence_score = demo.confidence_score
    return fp
