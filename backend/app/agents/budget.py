from __future__ import annotations

from app.schemas import BudgetEstimate, BudgetLineItem, ConfidenceLevel, MaterialItem


def run() -> tuple[list[MaterialItem], BudgetEstimate]:
    materials = [
        MaterialItem(
            item_name="HeLa cell vial",
            supplier="ATCC candidate supplier",
            catalog_number="verify_before_ordering",
            quantity="1 vial",
            confidence=ConfidenceLevel.medium,
            uncertainty_note="Exact catalog and lot to be confirmed by lab procurement.",
        ),
        MaterialItem(
            item_name="Cell culture grade DMSO",
            supplier="Thermo Fisher candidate supplier",
            catalog_number="verify_before_ordering",
            quantity="500 mL",
            confidence=ConfidenceLevel.medium,
            uncertainty_note="Catalog varies by region and purity grade.",
        ),
        MaterialItem(
            item_name="Trehalose",
            supplier="Sigma-Aldrich candidate supplier",
            catalog_number="verify_before_ordering",
            quantity="100 g",
            confidence=ConfidenceLevel.low,
            uncertainty_note="Pricing and grade are approximate pending concentration protocol.",
        ),
    ]

    line_items = [
        BudgetLineItem(
            item_name="HeLa cell vial",
            quantity="1 vial",
            unit_cost_estimate=450.0,
            total_cost_estimate=450.0,
            confidence=ConfidenceLevel.medium,
            uncertainty_note="Approximate, verify quotation.",
        ),
        BudgetLineItem(
            item_name="DMSO",
            quantity="500 mL",
            unit_cost_estimate=85.0,
            total_cost_estimate=85.0,
            confidence=ConfidenceLevel.medium,
            uncertainty_note="Approximate, verify quotation.",
        ),
        BudgetLineItem(
            item_name="Trehalose",
            quantity="100 g",
            unit_cost_estimate=120.0,
            total_cost_estimate=120.0,
            confidence=ConfidenceLevel.low,
            uncertainty_note="Low confidence until exact grade is fixed.",
        ),
        BudgetLineItem(
            item_name="Consumables and viability assay kit",
            quantity="1 package",
            unit_cost_estimate=380.0,
            total_cost_estimate=380.0,
            confidence=ConfidenceLevel.low,
            uncertainty_note="Assay kit pricing varies by vendor and format.",
        ),
    ]

    estimate = BudgetEstimate(
        line_items=line_items,
        estimated_total_cost=sum(line.total_cost_estimate for line in line_items),
        uncertainty_notes=[
            "All costs are deterministic demo estimates.",
            "Use verify_before_ordering before procurement decisions.",
        ],
    )
    return materials, estimate

