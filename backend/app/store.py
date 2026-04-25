from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import ScientistFeedback


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PLANS_DIR = DATA_DIR / "plans"
FEEDBACK_FILE = DATA_DIR / "feedback.json"


def ensure_data_dirs() -> None:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not FEEDBACK_FILE.exists():
        FEEDBACK_FILE.write_text("[]", encoding="utf-8")


def save_plan_run(plan_id: str, payload: dict[str, Any]) -> None:
    ensure_data_dirs()
    target = PLANS_DIR / f"{plan_id}.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_plan_run(plan_id: str) -> dict[str, Any] | None:
    ensure_data_dirs()
    target = PLANS_DIR / f"{plan_id}.json"
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def add_feedback(feedback: ScientistFeedback) -> None:
    ensure_data_dirs()
    existing = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
    existing.append(feedback.model_dump())
    FEEDBACK_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def get_feedback_for_plan(plan_id: str) -> list[ScientistFeedback]:
    ensure_data_dirs()
    existing = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
    matched = [item for item in existing if item.get("plan_id") == plan_id]
    return [ScientistFeedback.model_validate(item) for item in matched]

