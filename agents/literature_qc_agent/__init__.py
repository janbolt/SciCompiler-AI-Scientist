from core.schemas import Hypothesis, LiteratureQCResult


async def run(hypothesis: Hypothesis) -> LiteratureQCResult:
    """Stub. Wire to PubMed/Semantic Scholar/bioRxiv tools."""
    return LiteratureQCResult(
        novelty_signal="similar_work_exists",
        confidence=0.5,
        relevant_references=[],
        explanation="stub",
        recommended_action="combine related protocols and flag assumptions",
    )
