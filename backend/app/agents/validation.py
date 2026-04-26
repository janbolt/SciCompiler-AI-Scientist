from __future__ import annotations

from app.schemas import StructuredHypothesis, ValidationPlan


def run(hypothesis: StructuredHypothesis) -> ValidationPlan:
    threshold = hypothesis.threshold if hypothesis.threshold != "missing_required_field" else ">=10 percentage points (pilot fallback)"
    return ValidationPlan(
        primary_endpoint="Post-thaw viability percentage at immediate and 24h checkpoints.",
        secondary_endpoints=["Cell recovery count", "Morphology quality score", "Replicate variance"],
        success_threshold=f"{threshold} improvement over comparator in replicate-confirmed data.",
        failure_conditions=[
            "No meaningful viability gain in replicate-confirmed runs.",
            "Intervention increases delayed viability loss at 24h.",
        ],
        suggested_statistical_comparison="Two-group comparison against comparator using t-test or Mann-Whitney based on normality.",
        minimum_replicates_or_design_note="Minimum three biological replicates before execution-level claim.",
    )

