from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas import FeedbackRecord


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PLANS_DIR = DATA_DIR / "plans"
FEEDBACK_FILE = DATA_DIR / "feedback.json"


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    if not FEEDBACK_FILE.exists():
        FEEDBACK_FILE.write_text("[]", encoding="utf-8")


def save_plan(plan_id: str, payload: dict[str, Any]) -> None:
    ensure_storage()
    (PLANS_DIR / f"{plan_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_plan(plan_id: str) -> dict[str, Any] | None:
    ensure_storage()
    plan_file = PLANS_DIR / f"{plan_id}.json"
    if not plan_file.exists():
        return None
    return json.loads(plan_file.read_text(encoding="utf-8"))


def store_feedback(record: FeedbackRecord) -> None:
    ensure_storage()
    entries = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
    entries.append(record.model_dump(mode="json"))
    FEEDBACK_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def feedback_for_plan(plan_id: str) -> list[FeedbackRecord]:
    ensure_storage()
    entries = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
    matched = [entry for entry in entries if entry.get("plan_id") == plan_id]
    return [FeedbackRecord.model_validate(entry) for entry in matched]

