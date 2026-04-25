from core.schemas import ScientistFeedback


async def store(feedback: ScientistFeedback) -> None:
    pass


async def retrieve_similar(experiment_type: str | None) -> list[ScientistFeedback]:
    return []
