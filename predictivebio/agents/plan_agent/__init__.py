from core.schemas import (
    Hypothesis, LiteratureQCResult, ProtocolCandidate, EvidenceClaim,
    RiskItem, ExperimentPlan,
)


async def draft(
    hypothesis: Hypothesis,
    qc: LiteratureQCResult,
    protocols: list[ProtocolCandidate],
    evidence: list[EvidenceClaim],
) -> ExperimentPlan:
    return ExperimentPlan(title="(stub)", objective=hypothesis.raw_input)


async def revise(plan: ExperimentPlan, risks: list[RiskItem]) -> ExperimentPlan:
    plan.risks = risks
    return plan
