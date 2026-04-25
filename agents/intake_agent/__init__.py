from core.schemas import Hypothesis


async def run(raw_input: str, constraints: dict | None = None) -> Hypothesis:
    """Convert vague user input into a structured Hypothesis. Stub: fill in via LLM call."""
    return Hypothesis(raw_input=raw_input, constraints=constraints or {})
