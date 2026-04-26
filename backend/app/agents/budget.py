"""Agent 8 of 11 — Budget Agent.

Reads the experiment plan's protocol steps and uses an LLM (instructor +
OpenAI) to infer the required materials and estimate their costs. Materials
are always categorised as: instrument, consumable, chemical, control.

The LLM reasons about:
    * which materials are needed based on the protocol steps
    * typical academic lab pricing in EUR
    * appropriate supplier families (from its training knowledge)

Python owns:
    * building MaterialItem + BudgetEstimate from LLM output
    * computing estimated_total_cost

Rules enforced by system prompt:
    * catalog_number is always "verify_before_ordering"
    * prices are estimates only — marked with confidence level
    * no hardcoded supplier lists — LLM reasons from domain knowledge

Two execution modes:
- USE_STUB_AGENTS=true → returns deterministic stub output.
- Otherwise → LLM-powered via instructor.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import (
    BudgetEstimate,
    BudgetLineItem,
    ConfidenceLevel,
    ExperimentPlan,
    MaterialItem,
    StructuredHypothesis,
)
from app.services.llm import LLM_MAX_RETRIES, LLM_MODEL, USE_STUB_AGENTS, get_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM intermediate schemas
# ---------------------------------------------------------------------------


class _BudgetMaterialLLM(BaseModel):
    sub_protocol: str = Field(
        "general",
        description=(
            "Name of the sub-protocol this material is primarily used in. "
            "Must exactly match one of the sub-protocol names listed in the protocol steps "
            "(e.g. 'Nanoparticle Synthesis', 'Cell Culture', 'Data Analysis'). "
            "Use 'general' only if the material is shared across multiple sub-protocols."
        ),
    )
    category: Literal["instrument", "consumable", "chemical", "control"] = Field(
        ...,
        description=(
            "instrument = lab equipment needed (centrifuge, thermocycler, etc.); "
            "consumable = single-use items (tips, tubes, plates); "
            "chemical = reagents, kits, buffers, media; "
            "control = positive/negative control materials."
        ),
    )
    item_name: str = Field(..., description="Descriptive name of the material.")
    supplier: str = Field(
        ...,
        description=(
            "Most likely supplier based on your knowledge of this reagent/material "
            "(e.g. Sigma-Aldrich, ThermoFisher, NEB, Zymo, Sartorius, etc.). "
            "Do not invent catalog numbers — just name the supplier."
        ),
    )
    quantity: str = Field(
        ...,
        description="Quantity needed for this experiment (e.g. '1 kit', '500 mL', '1 vial', '100 reactions').",
    )
    unit_cost_eur: float = Field(
        ...,
        ge=0.0,
        description=(
            "Estimated unit cost in EUR based on typical academic lab pricing (2024-2025). "
            "If you are uncertain, provide a conservative estimate and set confidence to 'low'."
        ),
    )
    total_cost_eur: float = Field(
        ...,
        ge=0.0,
        description="Total cost for the stated quantity in EUR.",
    )
    confidence: Literal["low", "medium", "high"] = Field(
        ...,
        description=(
            "low = rough estimate, wide range possible; "
            "medium = reasonable estimate for planning; "
            "high = well-known commodity item with stable pricing."
        ),
    )
    uncertainty_note: str = Field(
        ...,
        description="One sentence explaining pricing uncertainty or what to verify before ordering.",
    )


class _BudgetLLMOutput(BaseModel):
    materials: list[_BudgetMaterialLLM] = Field(
        ...,
        min_length=2,
        description=(
            "Complete list of materials needed, covering all four categories "
            "(instrument, consumable, chemical, control) as appropriate for "
            "the protocol steps."
        ),
    )
    uncertainty_notes: list[str] = Field(
        default_factory=list,
        description="2–3 overall notes on budget uncertainty (e.g. institutional discounts, quote variability).",
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a lab manager estimating the materials and costs for a planned experiment.

You will receive:
1. A structured hypothesis describing the experiment.
2. The experiment plan's protocol steps, grouped by sub-protocol name.

Your job is to:
1. Read the protocol steps carefully and identify ALL materials required.
2. Categorise every material as: instrument, consumable, chemical, or control.
3. Tag each material with the sub-protocol it belongs to (sub_protocol field).
4. Estimate typical academic lab pricing in EUR (2024-2025 pricing).

RULES:
- Cover all four categories where applicable:
    instrument  = shared equipment needed (list even if lab has it — costs matter)
    consumable  = single-use items (pipette tips, tubes, plates, gloves)
    chemical    = reagents, kits, buffers, media, stains, enzymes
    control     = materials specific to positive/negative controls
- sub_protocol must exactly match the sub-protocol name from the steps list.
  Use 'general' only when a material (e.g. gloves, pipette tips) is used across
  multiple sub-protocols and cannot be attributed to one.
- Do NOT invent catalog numbers. The catalog field will be set to
  "verify_before_ordering" by the system — you only provide item names and suppliers.
- Supplier names come from your training knowledge — do not hardcode. Use the
  most common supplier for each reagent type.
- Pricing should reflect academic/university pricing, not list price.
  Common items (pipette tips, agarose, ethanol) are well-known — be confident.
  Specialised kits or rare reagents — use low confidence with a wide estimate.
- quantity should reflect the experiment scale implied by the protocol steps.
- If a step mentions a specific instrument (thermocycler, plate reader, gel system),
  include it as an instrument with a typical daily-use or rental fee estimate.
"""


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _format_steps(plan: ExperimentPlan) -> str:
    """Format protocol steps, grouping by sub-protocol so the LLM can tag materials."""
    if not plan.step_by_step_protocol:
        return "(no steps available)"

    # Group steps by sub-protocol to make the structure explicit for the LLM
    groups: dict[str, list] = {}
    for step in plan.step_by_step_protocol:
        groups.setdefault(step.linked_to or "general", []).append(step)

    lines: list[str] = []
    for sub_protocol, steps in groups.items():
        lines.append(f"\n[Sub-protocol: {sub_protocol}]")
        for step in steps:
            lines.append(f"  Step {step.step_number}: {step.description}")
    return "\n".join(lines)


def _generate_budget_with_llm(
    hypothesis: StructuredHypothesis,
    plan: ExperimentPlan,
    scientist_feedback: str = "",
) -> _BudgetLLMOutput:
    client = get_client()

    feedback_block = ""
    if scientist_feedback.strip():
        feedback_block = (
            "\n=================================================================\n"
            "SCIENTIST FEEDBACK ON MATERIALS / BUDGET — YOU MUST ADDRESS:\n"
            "=================================================================\n"
            f"{scientist_feedback.strip()}\n"
            "Adjust supplier choices, quantities, item names, and cost estimates\n"
            "to address every point above. If you cannot fully address an item,\n"
            "state explicitly in uncertainty_notes what was addressed and what\n"
            "could not be addressed and why.\n"
        )

    user_message = (
        "HYPOTHESIS\n"
        f"- intervention: {hypothesis.intervention}\n"
        f"- biological_system: {hypothesis.biological_system}\n"
        f"- experiment_type: {hypothesis.experiment_type}\n\n"
        "PROTOCOL STEPS\n"
        f"{_format_steps(plan)}\n"
        f"{feedback_block}\n"
        "Generate a complete materials and cost estimate for this experiment."
    )

    return client.chat.completions.create(
        model=LLM_MODEL,
        response_model=_BudgetLLMOutput,
        max_retries=LLM_MAX_RETRIES,
        temperature=1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _confidence_str_to_enum(conf: str) -> ConfidenceLevel:
    return {"low": ConfidenceLevel.low, "medium": ConfidenceLevel.medium, "high": ConfidenceLevel.high}.get(
        conf, ConfidenceLevel.low
    )


def _build_outputs(
    llm_output: _BudgetLLMOutput,
) -> tuple[list[MaterialItem], BudgetEstimate]:
    materials: list[MaterialItem] = []
    line_items: list[BudgetLineItem] = []

    for m in llm_output.materials:
        conf_enum = _confidence_str_to_enum(m.confidence)
        materials.append(
            MaterialItem(
                item_name=m.item_name,
                supplier=m.supplier,
                catalog_number="verify_before_ordering",
                quantity=m.quantity,
                confidence=conf_enum,
                uncertainty_note=m.uncertainty_note,
                linked_to=m.sub_protocol or "general",
            )
        )
        line_items.append(
            BudgetLineItem(
                item_name=m.item_name,
                quantity=m.quantity,
                unit_cost_estimate=m.unit_cost_eur,
                total_cost_estimate=m.total_cost_eur,
                confidence=conf_enum,
                uncertainty_note=m.uncertainty_note,
            )
        )

    total = round(sum(li.total_cost_estimate for li in line_items), 2)
    uncertainty_notes = llm_output.uncertainty_notes or [
        "All costs are estimates — verify with institutional procurement before ordering.",
        "Institutional discounts may reduce list prices by 20–40%.",
    ]

    estimate = BudgetEstimate(
        currency="EUR",
        line_items=line_items,
        estimated_total_cost=total,
        uncertainty_notes=uncertainty_notes,
    )
    return materials, estimate


# ---------------------------------------------------------------------------
# Stub mode
# ---------------------------------------------------------------------------


def _stub_budget(
    hypothesis: StructuredHypothesis,
    plan: ExperimentPlan,
) -> tuple[list[MaterialItem], BudgetEstimate]:
    intervention = hypothesis.intervention or "the intervention"
    bio_system = hypothesis.biological_system or "the model system"

    materials = [
        MaterialItem(
            item_name=f"{bio_system} sample",
            supplier="Supplier to be determined",
            catalog_number="verify_before_ordering",
            quantity="1 unit",
            confidence=ConfidenceLevel.medium,
            uncertainty_note="Exact catalog and lot to be confirmed by lab procurement.",
        ),
        MaterialItem(
            item_name=f"{intervention} (reagent grade)",
            supplier="Sigma-Aldrich (candidate supplier)",
            catalog_number="verify_before_ordering",
            quantity="As required by protocol",
            confidence=ConfidenceLevel.low,
            uncertainty_note="Pricing and grade are approximate pending protocol finalisation.",
        ),
        MaterialItem(
            item_name="Standard consumables (tips, tubes, plates)",
            supplier="Lab supplier",
            catalog_number="verify_before_ordering",
            quantity="1 package",
            confidence=ConfidenceLevel.medium,
            uncertainty_note="Stub estimate — verify against actual protocol scale.",
        ),
    ]

    line_items = [
        BudgetLineItem(
            item_name=f"{bio_system} sample",
            quantity="1 unit",
            unit_cost_estimate=300.0,
            total_cost_estimate=300.0,
            confidence=ConfidenceLevel.medium,
            uncertainty_note="Approximate — verify quotation.",
        ),
        BudgetLineItem(
            item_name=f"{intervention} (reagent grade)",
            quantity="As required",
            unit_cost_estimate=150.0,
            total_cost_estimate=150.0,
            confidence=ConfidenceLevel.low,
            uncertainty_note="Low confidence until exact grade and quantity are fixed.",
        ),
        BudgetLineItem(
            item_name="Standard consumables",
            quantity="1 package",
            unit_cost_estimate=200.0,
            total_cost_estimate=200.0,
            confidence=ConfidenceLevel.medium,
            uncertainty_note="Stub estimate.",
        ),
    ]

    estimate = BudgetEstimate(
        currency="EUR",
        line_items=line_items,
        estimated_total_cost=sum(li.total_cost_estimate for li in line_items),
        uncertainty_notes=[
            "Stub mode — all costs are placeholder estimates.",
            "Use verify_before_ordering before any procurement decisions.",
        ],
    )
    return materials, estimate


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def run(
    hypothesis: StructuredHypothesis | None = None,
    plan: ExperimentPlan | None = None,
    scientist_feedback: str = "",
) -> tuple[list[MaterialItem], BudgetEstimate]:
    """Generate a materials list and budget estimate for the experiment.

    Args:
        hypothesis: Structured hypothesis (required in live mode).
        plan: Experiment plan whose steps drive material inference.
        scientist_feedback: Free-text scientist corrections specifically
            targeting materials/budget. Injected into the LLM prompt with
            mandatory-address language. Empty string = no feedback.

    Returns:
        Tuple of (materials list, budget estimate).
    """
    if USE_STUB_AGENTS or hypothesis is None or plan is None:
        if hypothesis is not None and plan is not None:
            return _stub_budget(hypothesis, plan)
        # Minimal fallback when called without arguments (legacy)
        from app.schemas import ConfidenceLevel as CL  # noqa: PLC0415
        mat = MaterialItem(
            item_name="Placeholder material",
            supplier="TBD",
            catalog_number="verify_before_ordering",
            quantity="TBD",
            confidence=CL.low,
            uncertainty_note="No hypothesis or plan provided.",
        )
        li = BudgetLineItem(
            item_name="Placeholder material",
            quantity="TBD",
            unit_cost_estimate=0.0,
            total_cost_estimate=0.0,
            confidence=CL.low,
            uncertainty_note="No hypothesis or plan provided.",
        )
        return [mat], BudgetEstimate(
            currency="EUR",
            line_items=[li],
            estimated_total_cost=0.0,
            uncertainty_notes=["No hypothesis or plan provided."],
        )

    try:
        llm_output = _generate_budget_with_llm(hypothesis, plan, scientist_feedback=scientist_feedback)
        return _build_outputs(llm_output)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Budget agent LLM call failed, falling back to stub: %s", exc)
        return _stub_budget(hypothesis, plan)
