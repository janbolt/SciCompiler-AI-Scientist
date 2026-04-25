from core.schemas import ExperimentPlan


async def run(plan: ExperimentPlan) -> dict:
    return {"objective": plan.objective, "scope_of_work": [], "questions_for_cro": []}
