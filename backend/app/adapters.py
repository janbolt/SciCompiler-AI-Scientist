"""
adapters.py
-----------
Transforms internal agent outputs into the FrontendPlanData shape that the
React frontend consumes verbatim.  All field-name mismatches, enum remappings,
and structural reshaping are handled here — not in agents or orchestrator logic.
"""
from __future__ import annotations

from .schemas import (
    FrontendBudget,
    FrontendBudgetLine,
    FrontendExperiment,
    FrontendPhase,
    FrontendPlanData,
    FrontendReference,
    LiteratureQCResult,
    NoveltySignal,
    StructuredHypothesis,
    TimelineEstimate,
)

# ── Novelty signal ────────────────────────────────────────────────────────────

_NOVELTY_MAP = {
    NoveltySignal.not_found: "not found",
    NoveltySignal.similar_work_exists: "similar work exists",
    NoveltySignal.exact_match_found: "exact match found",
}


def _map_novelty(signal: NoveltySignal) -> str:
    return _NOVELTY_MAP.get(signal, "not found")


# ── References ────────────────────────────────────────────────────────────────

def _map_references(lit_qc: LiteratureQCResult) -> list[FrontendReference]:
    refs = []
    for r in lit_qc.relevant_references:
        # Build a citation string from available fields
        citation = r.title
        if r.year:
            citation = f"{r.title} ({r.year})"
        if r.source and r.source not in ("semantic_scholar_stub", "pubmed_stub"):
            citation = f"{citation}. {r.source}."

        # Extract DOI from URL if present (doi.org/10.xxx), else blank
        doi = ""
        if r.url and "doi.org" in r.url:
            doi = r.url.split("doi.org/", 1)[-1]

        refs.append(FrontendReference(citation=citation, doi=doi))
    return refs


# ── Phases ────────────────────────────────────────────────────────────────────

def _map_phases(timeline: TimelineEstimate) -> list[FrontendPhase]:
    return [
        FrontendPhase(name=p.phase_name, days=p.estimated_duration_days)
        for p in timeline.phases
    ]


# ── Budget ────────────────────────────────────────────────────────────────────

def _build_budget(experiments: list[FrontendExperiment]) -> FrontendBudget:
    """
    Derive a structured budget from the experiment materials.

    Split into three categories by heuristic:
      fixed    — housing, equipment, one-off infrastructure
      staff    — researcher time (estimated as 8h/experiment-day at 45 EUR/h)
      recurring — all consumable materials
    """
    # Recurring: sum all materials across experiments
    recurring: list[FrontendBudgetLine] = []
    for exp in experiments:
        for m in exp.materials:
            recurring.append(FrontendBudgetLine(
                item=f"{m.name} ({exp.name})",
                cost_eur=m.total_eur,
            ))

    # Fixed: equipment use fee estimate
    fixed = [
        FrontendBudgetLine(
            item="Equipment use fees (plate reader, centrifuge, imaging)",
            cost_eur=320.0,
        ),
    ]

    # Staff: 8h/day × 45 EUR/h × total experiment days
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


# ── Top-level transformer ─────────────────────────────────────────────────────

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
        hypothesis=hypothesis.raw_input,
        objective=_derive_objective(hypothesis),
        novelty_signal=_map_novelty(lit_qc.novelty_signal),  # type: ignore[arg-type]
        references=_map_references(lit_qc),
        phases=_map_phases(timeline),
        experiments=experiments,
        budget=_build_budget(experiments),
    )


def _derive_objective(hypothesis: StructuredHypothesis) -> str:
    """Build a one-sentence objective from the structured hypothesis fields."""
    if hypothesis.intervention != "missing_required_field" and hypothesis.outcome != "missing_required_field":
        return (
            f"Evaluate whether {hypothesis.intervention} produces "
            f"{hypothesis.outcome} under the specified experimental conditions."
        )
    return "Evaluate the stated hypothesis under controlled experimental conditions."
