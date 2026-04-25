from core.schemas import Hypothesis, EvidenceClaim, ProtocolCandidate, Reference


async def run(
    hypothesis: Hypothesis,
    refs: list[Reference],
    protocols: list[ProtocolCandidate],
) -> list[EvidenceClaim]:
    return []
