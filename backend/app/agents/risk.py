from __future__ import annotations

from app.schemas import PlanAction, RiskCategory, RiskItem


def run() -> list[RiskItem]:
    return [
        RiskItem(
            risk_id="RISK-001",
            category=RiskCategory.biological_assumption,
            description="Trehalose intracellular protection may be insufficient in the chosen HeLa setup.",
            severity="medium",
            likelihood="medium",
            mitigation="Add concentration pilot arm and viability check at 0h and 24h.",
            action=PlanAction.modify_plan,
        ),
        RiskItem(
            risk_id="RISK-002",
            category=RiskCategory.control_gap,
            description="Comparator alone may be insufficient to explain handling artifacts.",
            severity="high",
            likelihood="medium",
            mitigation="Add no-cryoprotectant stress control and sham-freeze control.",
            action=PlanAction.modify_plan,
        ),
        RiskItem(
            risk_id="RISK-003",
            category=RiskCategory.replication_gap,
            description="Single run can overfit to batch effects.",
            severity="medium",
            likelihood="high",
            mitigation="Require minimum three biological replicates before execution claim.",
            action=PlanAction.downgrade_to_pilot,
        ),
        RiskItem(
            risk_id="RISK-004",
            category=RiskCategory.safety_or_compliance,
            description="Cell line provenance and handling approvals must be verified by lab lead.",
            severity="low",
            likelihood="medium",
            mitigation="Document institutional biosafety verification before wet-lab execution.",
            action=PlanAction.document_only,
        ),
    ]

