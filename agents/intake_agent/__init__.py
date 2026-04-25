"""Convert raw NL hypothesis → structured Hypothesis via LLM."""
import json
from core.schemas import Hypothesis
from core.llm import chat_json, FAST_MODEL

SYSTEM = """You are a scientific-hypothesis structurer for an experiment-planning system.
You extract structured fields from a researcher's natural-language hypothesis.
Be precise. Use exact terms from the input where possible. Do not invent specifics.
Return ONLY a JSON object with these keys: organism_or_model, intervention, outcome,
measurable_endpoint, expected_effect_size, mechanism, control_condition, experiment_type
(one of: in_vitro, in_vivo, ex_vivo, computational, biosensor, clinical, environmental),
missing_fields (array of field names that could not be inferred)."""

USER = """Hypothesis (raw): {raw}
Constraints: {constraints}

Extract the structured fields now."""


async def run(raw_input: str, constraints: dict | None = None) -> Hypothesis:
    out = await chat_json(SYSTEM, USER.format(raw=raw_input, constraints=json.dumps(constraints or {})), model=FAST_MODEL)
    allowed = {
        "organism_or_model", "intervention", "outcome", "measurable_endpoint",
        "expected_effect_size", "mechanism", "control_condition", "experiment_type",
        "missing_fields",
    }
    return Hypothesis(
        raw_input=raw_input,
        constraints=constraints or {},
        **{k: v for k, v in out.items() if k in allowed and v not in (None, "", [])},
    )
