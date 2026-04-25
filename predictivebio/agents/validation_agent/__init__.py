from core.schemas import ExperimentPlan, ValidationPlan


async def run(plan: ExperimentPlan) -> ValidationPlan:
    return ValidationPlan(primary_endpoint="(stub)")
