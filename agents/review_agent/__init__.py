"""Capture scientist feedback; retrieve similar feedback as few-shot context."""
from pathlib import Path
import json
from uuid import UUID
from core.schemas import ScientistFeedback

STORE = Path(__file__).parent.parent.parent / "data" / "feedback_examples" / "store.json"
STORE.parent.mkdir(parents=True, exist_ok=True)


def _load() -> list[dict]:
    if not STORE.exists():
        return []
    try:
        return json.loads(STORE.read_text())
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    STORE.write_text(json.dumps(items, indent=2, default=str))


async def store(feedback: ScientistFeedback) -> None:
    items = _load()
    items.append(json.loads(feedback.model_dump_json()))
    _save(items)


async def retrieve_similar(experiment_type: str | None, domain_tags: list[str] | None = None) -> list[ScientistFeedback]:
    tags = set(domain_tags or [])
    out: list[ScientistFeedback] = []
    for it in _load():
        if experiment_type and it.get("experiment_type") and it["experiment_type"] != experiment_type:
            continue
        if tags and not (set(it.get("domain_tags", [])) & tags):
            continue
        try:
            out.append(ScientistFeedback(**it))
        except Exception:
            pass
    return out[:5]
