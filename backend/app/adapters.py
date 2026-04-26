"""
adapters.py
-----------
Transforms internal agent outputs into the FrontendPlanData shape that the
React frontend consumes verbatim.  All field-name mismatches, enum remappings,
and structural reshaping are handled here — not in agents or orchestrator logic.
"""
from __future__ import annotations

import logging
import re

from .agents.cro_compatibility import (
    CROCompatibilityVerdict,
    evaluate_batch as evaluate_cro_batch,
)
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

logger = logging.getLogger(__name__)

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

    # Group steps by linked_to, preserving agent-defined order.
    #
    # Risk-mitigation steps emitted by `plan._apply_risk_mitigations` carry an
    # internal linkage like ``linked_to="risk:RISK-002"`` (or the literal
    # ``"risk_mitigation"``). Without remapping, those create cryptic phantom
    # cards in the UI named "risk:RISK-002". We fold them into the most
    # recently-established real protocol group so the mitigation step shows
    # up *inside* the protocol it modifies. If a risk step has no preceding
    # real group, it lands in a clean "Risk Mitigations" card.
    groups: dict[str, list[ProtocolStep]] = {}
    last_real_group: str | None = None
    for step in plan.step_by_step_protocol:
        raw_link = step.linked_to or "Protocol"
        is_risk_phantom = raw_link.lower().startswith("risk:") or raw_link.lower() == "risk_mitigation"
        if is_risk_phantom:
            target = last_real_group or "Risk Mitigations"
        else:
            target = raw_link
            last_real_group = target
        groups.setdefault(target, []).append(step)

    if not groups:
        # Single-card fallback when the plan agent emitted no steps. We still
        # run the LLM classifier so the card gets a real verdict + reason.
        single_name = hypothesis.experiment_type.replace("_", " ").title()
        single_id = demo.plan_id
        verdicts = evaluate_cro_batch(
            hypothesis,
            [
                {
                    "id": single_id,
                    "name": single_name,
                    "duration": timeline.total_duration_estimate,
                    "goal": plan.objective,
                    "steps": [],
                }
            ],
        )
        v = verdicts.get(single_id)
        return [
            _build_experiment_card(
                exp_id=single_id,
                name=single_name,
                duration=timeline.total_duration_estimate,
                goal=plan.objective,
                success_criteria=validation.success_threshold,
                steps=[],
                materials=all_frontend_materials,
                verdict=v,
            )
        ]

    # Build provisional card descriptors (without final cro_* fields). We need
    # these dicts both for the LLM batch call and for assembling the response,
    # so we materialise the iteration once.
    card_specs: list[dict] = []
    for i, (group_name, steps) in enumerate(groups.items()):
        exp_id = f"{demo.plan_id}-{i}"
        card_specs.append(
            {
                "id": exp_id,
                "name": group_name,
                "duration": _estimate_duration_from_steps(steps),
                "goal": plan.objective,
                "success_criteria": validation.success_threshold,
                "steps": [s.description for s in steps],
                "materials": (
                    materials_by_group.get(group_name, []) + materials_by_group.get("general", [])
                    if has_tagged
                    else (all_frontend_materials if i == 0 else [])
                ),
            }
        )

    # ── Single batched LLM CRO-compatibility classifier ──────────────────────
    # Falls back to a deterministic heuristic internally if the LLM is
    # unreachable, so this call cannot raise.
    verdicts = evaluate_cro_batch(hypothesis, card_specs)

    return [
        _build_experiment_card(
            exp_id=spec["id"],
            name=spec["name"],
            duration=spec["duration"],
            goal=spec["goal"],
            success_criteria=spec["success_criteria"],
            steps=spec["steps"],
            materials=spec["materials"],
            verdict=verdicts.get(spec["id"]),
        )
        for spec in card_specs
    ]


def _build_experiment_card(
    *,
    exp_id: str,
    name: str,
    duration: str,
    goal: str,
    success_criteria: str,
    steps: list[str],
    materials: list[FrontendMaterial],
    verdict: CROCompatibilityVerdict | None,
) -> FrontendExperiment:
    """Assemble a FrontendExperiment, merging in the LLM CRO verdict if present."""
    if verdict is None:
        # Should be unreachable because evaluate_cro_batch guarantees coverage,
        # but stay defensive: ship a non-compatible card with an honest reason.
        logger.warning("CRO verdict missing for experiment_id=%s — emitting safe default.", exp_id)
        return FrontendExperiment(
            id=exp_id,
            name=name,
            duration=duration,
            cro_compatible=False,
            goal=goal,
            success_criteria=success_criteria,
            steps=steps,
            materials=materials,
            cro_reason="CRO classifier did not return a verdict for this card.",
            cro_blockers=["Verdict missing — defaulted to non-CRO for safety."],
            cro_confidence=0.0,
            cro_routine_match="unknown",
            cro_bundle_name="",
            cro_bundle_examples=[],
        )

    return FrontendExperiment(
        id=exp_id,
        name=name,
        duration=duration,
        cro_compatible=verdict.cro_compatible,
        goal=goal,
        success_criteria=success_criteria,
        steps=steps,
        materials=materials,
        cro_reason=verdict.reason,
        cro_blockers=list(verdict.blockers),
        cro_confidence=verdict.confidence,
        cro_routine_match=verdict.routine_match,
        cro_bundle_name=verdict.bundle_name,
        cro_bundle_examples=list(verdict.bundle_examples),
    )


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
