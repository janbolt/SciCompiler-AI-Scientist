"""Pipeline orchestrator. Risk assessment runs before final plan assembly,
and risk output must change the plan, not merely annotate it."""
from core.schemas import DemoRunInput, DemoRunOutput
from agents import (
    intake_agent, literature_qc_agent, protocol_retrieval_agent,
    evidence_agent, plan_agent, risk_agent, budget_agent,
    timeline_agent, validation_agent,
)


async def run_pipeline(inp: DemoRunInput) -> DemoRunOutput:
    hypothesis = await intake_agent.run(inp.scientific_question, inp.constraints)
    qc = await literature_qc_agent.run(hypothesis)
    protocols = await protocol_retrieval_agent.run(hypothesis)
    evidence = await evidence_agent.run(hypothesis, qc.relevant_references, protocols)

    draft = await plan_agent.draft(hypothesis, qc, protocols, evidence)
    risks = await risk_agent.run(draft)
    plan = await plan_agent.revise(draft, risks)

    plan.budget = await budget_agent.run(plan)
    plan.timeline = await timeline_agent.run(plan)
    plan.validation = await validation_agent.run(plan)

    return DemoRunOutput(
        hypothesis=hypothesis,
        literature_qc=qc,
        protocol_candidates=protocols,
        evidence_claims=evidence,
        risks=risks,
        plan=plan,
    )
