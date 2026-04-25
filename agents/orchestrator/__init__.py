"""Pipeline orchestrator. Risk runs BEFORE final assembly and mutates the plan."""
import asyncio
from core.schemas import DemoRunInput, DemoRunOutput
from agents import (
    intake_agent, literature_qc_agent, protocol_retrieval_agent,
    evidence_agent, plan_agent, risk_agent, budget_agent,
    timeline_agent, validation_agent,
)


async def run_pipeline(inp: DemoRunInput) -> DemoRunOutput:
    hypothesis = await intake_agent.run(inp.scientific_question, inp.constraints)

    # Lit QC and protocol retrieval in parallel — both depend only on hypothesis.
    qc, protocols = await asyncio.gather(
        literature_qc_agent.run(hypothesis),
        protocol_retrieval_agent.run(hypothesis),
    )

    evidence = await evidence_agent.run(hypothesis, qc.relevant_references, protocols)

    draft = await plan_agent.draft(hypothesis, qc, protocols, evidence)
    risks = await risk_agent.run(draft)
    plan = await plan_agent.revise(draft, risks)

    # Budget, timeline, validation in parallel — all read final plan only.
    budget, timeline, validation = await asyncio.gather(
        budget_agent.run(plan),
        timeline_agent.run(plan),
        validation_agent.run(plan),
    )
    plan.budget = budget
    plan.timeline = timeline
    plan.validation = validation

    return DemoRunOutput(
        hypothesis=hypothesis, literature_qc=qc, protocol_candidates=protocols,
        evidence_claims=evidence, risks=risks, plan=plan,
    )
