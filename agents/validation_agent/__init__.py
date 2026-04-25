"""Define how success/failure are measured."""
import json
from core.schemas import ExperimentPlan, ValidationPlan
from core.llm import chat_json, FAST_MODEL

SYSTEM = """You define validation criteria for an experiment. Return JSON:
{
  "primary_endpoint": str,
  "secondary_endpoints": [str],
  "positive_control": str|null,
  "negative_control": str|null,
  "statistical_test": str|null,
  "success_threshold": str,
  "failure_conditions": [str]
}"""

USER = """Plan:
title = {title}
objective = {obj}
controls = {ctrls}
steps = {steps}

Define validation."""


async def run(plan: ExperimentPlan) -> ValidationPlan:
    out = await chat_json(
        SYSTEM,
        USER.format(
            title=plan.title, obj=plan.objective,
            ctrls=json.dumps(plan.controls),
            steps=json.dumps([s.title for s in plan.protocol_steps]),
        ),
        model=FAST_MODEL,
    )
    return ValidationPlan(
        primary_endpoint=out.get("primary_endpoint", "(unspecified)"),
        secondary_endpoints=out.get("secondary_endpoints", []) or [],
        positive_control=out.get("positive_control"),
        negative_control=out.get("negative_control"),
        statistical_test=out.get("statistical_test"),
        success_threshold=out.get("success_threshold"),
        failure_conditions=out.get("failure_conditions", []) or [],
    )
