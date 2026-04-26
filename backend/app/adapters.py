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
    ProtocolStep,
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

def _estimate_duration_from_steps(steps: list[ProtocolStep]) -> str:
    """Parse DAY N markers from step descriptions to estimate duration for a group."""
    day_pattern = re.compile(r"\bDAY\s+(\d+)", re.IGNORECASE)
    days = {int(m.group(1)) for s in steps for m in day_pattern.finditer(s.description)}
    if not days:
        return "< 1 day"
    span = max(days) - min(days) + 1
    return f"{span} day{'s' if span > 1 else ''}"


def _compute_cro_compatible(demo: DemoRunResponse) -> bool:
    """
    Score protocol standardness from multiple pipeline signals to determine
    whether this experiment is suitable for outsourcing to a CRO.

    A protocol is CRO-compatible when it is:
      - not blocked by the plan agent (hard gate)
      - backed by real protocols.io matches and/or published methods literature

    Scoring (threshold = 4):
      execution_ready_after_review  +2 | pilot_only               +1
      protocols.io fit >= 0.7       +2 | fit >= 0.5               +1  (per candidate, max 3)
      novelty: exact_match_found    +2 | similar_work_exists       +1
      references >= 3               +2 | >= 1                      +1
      search_coverage == full       +1
    """
    plan = demo.plan
    lit = demo.literature_qc
    candidates = demo.protocol_candidates

    if plan.execution_readiness_label == "blocked_pending_expert_review":
        return False

    score = 0

    if plan.execution_readiness_label == "execution_ready_after_review":
        score += 2
    elif plan.execution_readiness_label == "pilot_only":
        score += 1

    real_candidates = [c for c in candidates if c.source_type != "stub" and c.raw_steps]
    for c in real_candidates[:3]:
        if c.fit_score >= 0.7:
            score += 2
        elif c.fit_score >= 0.5:
            score += 1

    if lit.novelty_signal == "exact_match_found":
        score += 2
    elif lit.novelty_signal == "similar_work_exists":
        score += 1

    real_refs = [r for r in lit.references if not r.is_stub]
    if len(real_refs) >= 3:
        score += 2
    elif len(real_refs) >= 1:
        score += 1

    if lit.search_coverage == "full":
        score += 1

    return score >= 4


def _map_experiments(demo: DemoRunResponse) -> list[FrontendExperiment]:
    """
    Build one FrontendExperiment per distinct sub-protocol (grouped by
    ProtocolStep.linked_to) from the ExperimentPlan produced by the pipeline.

    Materials are distributed to their matching sub-protocol card using
    MaterialItem.linked_to. For old plans without tags, all materials fall
    back to the first card.
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

    # Build FrontendMaterial objects paired with their sub-protocol tag
    frontend_materials_tagged: list[tuple[str, FrontendMaterial]] = []
    for m in materials:
        unit_cost, total = cost_by_name.get(m.item_name.lower(), (0.0, 0.0))
        fm = FrontendMaterial(
            name=m.item_name,
            catalog=m.catalog_number or "verify_before_ordering",
            supplier=m.supplier,
            qty=m.quantity,
            unit_cost_eur=unit_cost,
            total_eur=total,
        )
        frontend_materials_tagged.append((m.linked_to or "general", fm))

    # Determine whether the budget agent tagged materials with sub-protocols
    has_tagged = any(tag != "general" for tag, _ in frontend_materials_tagged)

    # Build a per-group material index (tagged materials) or full fallback list
    all_frontend_materials = [fm for _, fm in frontend_materials_tagged]
    materials_by_group: dict[str, list[FrontendMaterial]] = {}
    for tag, fm in frontend_materials_tagged:
        materials_by_group.setdefault(tag, []).append(fm)

    cro_compatible = _compute_cro_compatible(demo)

    # Group steps by linked_to, preserving agent-defined order
    groups: dict[str, list[ProtocolStep]] = {}
    for step in plan.step_by_step_protocol:
        groups.setdefault(step.linked_to or "Protocol", []).append(step)

    if not groups:
        # Fallback: single card with all steps when the agent emits no steps
        return [
            FrontendExperiment(
                id=demo.plan_id,
                name=hypothesis.experiment_type.replace("_", " ").title(),
                duration=timeline.total_duration_estimate,
                cro_compatible=cro_compatible,
                goal=plan.objective,
                success_criteria=validation.success_threshold,
                steps=[],
                materials=all_frontend_materials,
            )
        ]

    return [
        FrontendExperiment(
            id=f"{demo.plan_id}-{i}",
            name=group_name,
            duration=_estimate_duration_from_steps(steps),
            cro_compatible=cro_compatible,
            goal=plan.objective,
            success_criteria=validation.success_threshold,
            steps=[s.description for s in steps],
            # Tagged materials: assign per group; also include 'general' materials on every card.
            # Untagged (old plans): all materials on card 0, empty elsewhere.
            materials=(
                materials_by_group.get(group_name, []) + materials_by_group.get("general", [])
                if has_tagged
                else (all_frontend_materials if i == 0 else [])
            ),
        )
        for i, (group_name, steps) in enumerate(groups.items())
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
