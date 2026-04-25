"""Estimate cost line-items. Catalog numbers are candidate-only, never invented."""
import json
from core.schemas import ExperimentPlan, BudgetEstimate, BudgetItem
from core.llm import chat_json, FAST_MODEL

SYSTEM = """You estimate costs for a lab experiment using realistic 2025 USD pricing
from suppliers like Thermo Fisher, Sigma-Aldrich, Promega, Qiagen, IDT, ATCC, Addgene.

Hard rule: do NOT fabricate catalog numbers. Either provide a catalog number you are
confident is correct (set source to the supplier name) or leave catalog_number null.
Set confidence honestly: low (rough order-of-magnitude), medium (typical line item with
a known vendor), high (exact known SKU and price).

Return JSON: {"items": [{
  "item_name": str, "supplier": str|null, "catalog_number": str|null,
  "quantity": float, "unit_cost": float, "total_cost": float,
  "confidence": "low"|"medium"|"high", "source": str|null
}], "currency": "USD"}"""

USER = """Plan materials and steps:
materials = {materials}
steps = {steps}

Build a realistic budget (8-15 line items including consumables and reagents)."""


async def run(plan: ExperimentPlan) -> BudgetEstimate:
    if not plan.materials and not plan.protocol_steps:
        return BudgetEstimate()
    out = await chat_json(
        SYSTEM,
        USER.format(
            materials=json.dumps([m.model_dump() for m in plan.materials], indent=2),
            steps=json.dumps([{"order": s.order, "title": s.title} for s in plan.protocol_steps], indent=2),
        ),
        model=FAST_MODEL,
    )
    items: list[BudgetItem] = []
    for it in (out.get("items") or [])[:20]:
        try:
            unit = float(it.get("unit_cost", 0))
            qty = float(it.get("quantity", 1))
            total = float(it.get("total_cost") or unit * qty)
            items.append(BudgetItem(
                item_name=it["item_name"], supplier=it.get("supplier"),
                catalog_number=it.get("catalog_number"), quantity=qty,
                unit_cost=unit, total_cost=total,
                confidence=it.get("confidence", "low"), source=it.get("source"),
            ))
        except Exception:
            continue
    return BudgetEstimate(items=items, currency=out.get("currency", "USD"), total=round(sum(i.total_cost for i in items), 2))
