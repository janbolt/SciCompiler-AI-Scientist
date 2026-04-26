"""Agent 5 of 11 — Risk Agent.

Derives 1–2 risk items deterministically from existing confidence signals —
no LLM call, no hardcoded domain knowledge. This keeps risk assessment fast
and focused on what the pipeline actually knows.

Signal sources:
    * hypothesis.readiness   → underspecified hypothesis raises a high-severity flag
    * literature_qc.confidence_score < 0.4 → limited literature coverage flag
    * literature_qc.novelty_signal == "not_found" → exploratory risk flag

If none of the above signals fire, one low-severity default item is returned
reminding the scientist to review the plan before execution.

No stub path needed — this agent is entirely deterministic.
"""

from __future__ import annotations

from app.schemas import (
    LiteratureQCResult,
    PlanAction,
    RiskCategory,
    RiskItem,
    StructuredHypothesis,
)


def run(
    hypothesis: StructuredHypothesis | None = None,
    literature_qc: LiteratureQCResult | None = None,
) -> list[RiskItem]:
    """Derive risk items from hypothesis and literature QC signals.

    Args:
        hypothesis: Structured hypothesis from the intake agent.
        literature_qc: Result from the literature QC agent.

    Returns:
        A list of 1–3 RiskItem objects. Never empty.
    """
    risks: list[RiskItem] = []

    # --- Signal 1: underspecified hypothesis ----------------------------------
    if hypothesis is not None and hypothesis.readiness == "underspecified":
        risks.append(
            RiskItem(
                risk_id="RISK-001",
                category=RiskCategory.technical_assumption,
                description=(
                    f"Hypothesis is underspecified: {hypothesis.readiness_rationale}. "
                    "Missing required fields must be resolved before execution."
                ),
                severity="high",
                likelihood="high",
                mitigation=(
                    "Clarify the following fields before proceeding: "
                    + (", ".join(hypothesis.missing_required_fields) if hypothesis.missing_required_fields else "see readiness_rationale")
                ),
                action=PlanAction.document_only,
            )
        )

    # --- Signal 2: low literature confidence ----------------------------------
    if literature_qc is not None and literature_qc.confidence_score < 0.4:
        risks.append(
            RiskItem(
                risk_id=f"RISK-{len(risks) + 1:03d}",
                category=RiskCategory.biological_assumption,
                description=(
                    f"Limited literature coverage (confidence score: {literature_qc.confidence_score:.2f}). "
                    "Few or no related publications were found — the experimental basis may be weak."
                ),
                severity="medium",
                likelihood="medium",
                mitigation=(
                    "Conduct a manual literature review on PubMed and bioRxiv before committing "
                    "to this experimental design. Consider a small pilot to validate the approach."
                ),
                action=PlanAction.document_only,
            )
        )

    # --- Signal 3: no prior work found ----------------------------------------
    if (
        literature_qc is not None
        and literature_qc.novelty_signal == "not_found"
        and literature_qc.confidence_score >= 0.4
    ):
        risks.append(
            RiskItem(
                risk_id=f"RISK-{len(risks) + 1:03d}",
                category=RiskCategory.biological_assumption,
                description=(
                    "No directly matching protocols or publications found. "
                    "This may be a novel experimental combination with higher inherent uncertainty."
                ),
                severity="low",
                likelihood="low",
                mitigation=(
                    "Pilot experiment recommended before committing full resources. "
                    "Document all assumptions explicitly in the plan."
                ),
                action=PlanAction.document_only,
            )
        )

    # --- Default: always return at least one item ----------------------------
    if not risks:
        risks.append(
            RiskItem(
                risk_id="RISK-001",
                category=RiskCategory.biological_assumption,
                description=(
                    "Standard experimental risk — the approach has literature support "
                    "but execution details should be reviewed before proceeding."
                ),
                severity="low",
                likelihood="low",
                mitigation=(
                    "Confirm all materials, controls, and readiness criteria with "
                    "a scientist before execution."
                ),
                action=PlanAction.document_only,
            )
        )

    return risks
