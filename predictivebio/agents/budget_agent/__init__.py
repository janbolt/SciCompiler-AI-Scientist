from core.schemas import ExperimentPlan, BudgetEstimate


async def run(plan: ExperimentPlan) -> BudgetEstimate:
    return BudgetEstimate()
