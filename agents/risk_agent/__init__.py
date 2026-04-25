from core.schemas import ExperimentPlan, RiskItem


async def run(plan: ExperimentPlan) -> list[RiskItem]:
    """Identify failure modes. Every risk maps to a plan_action."""
    return []
