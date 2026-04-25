from core.schemas import ExperimentPlan, Timeline


async def run(plan: ExperimentPlan) -> Timeline:
    return Timeline()
