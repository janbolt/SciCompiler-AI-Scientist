from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path
from typing import Any

from app.schemas import FeedbackRecord, ScientistReview, StructuredHypothesis


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
PLANS_DIR = DATA_DIR / "plans"
FEEDBACK_FILE = DATA_DIR / "feedback.json"
MEMORY_FILE = DATA_DIR / "feedback_memory.json"


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    if not FEEDBACK_FILE.exists():
        FEEDBACK_FILE.write_text("[]", encoding="utf-8")
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text("{}", encoding="utf-8")


def save_plan(plan_id: str, payload: dict[str, Any]) -> None:
    ensure_storage()
    (PLANS_DIR / f"{plan_id}.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def load_plan(plan_id: str) -> dict[str, Any] | None:
    ensure_storage()
    plan_file = PLANS_DIR / f"{plan_id}.json"
    if not plan_file.exists():
        return None
    return json.loads(plan_file.read_text(encoding="utf-8"))


def _read_feedback_entries() -> list[dict[str, Any]]:
    ensure_storage()
    try:
        data = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = []
    return data if isinstance(data, list) else []


def _write_feedback_entries(entries: list[dict[str, Any]]) -> None:
    FEEDBACK_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def store_feedback(plan_id: str, review: ScientistReview) -> None:
    entries = _read_feedback_entries()
    created_at = review.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
    for annotation in review.annotations:
        entries.append(
            {
                "plan_id": plan_id,
                "section": annotation.section.value,
                "feedback_text": annotation.feedback_text,
                "requested_changes": annotation.requested_changes,
                "severity": annotation.severity,
                "global_feedback": review.global_feedback,
                "created_at": created_at,
            }
        )
    _write_feedback_entries(entries)


def store_feedback_record(record: FeedbackRecord) -> None:
    entries = _read_feedback_entries()
    entries.append(record.model_dump(mode="json"))
    _write_feedback_entries(entries)


def get_feedback_for_plan(plan_id: str) -> list[dict[str, Any]]:
    entries = _read_feedback_entries()
    return [entry for entry in entries if entry.get("plan_id") == plan_id]


def feedback_for_plan(plan_id: str) -> list[FeedbackRecord]:
    matched = get_feedback_for_plan(plan_id)
    records: list[FeedbackRecord] = []
    for entry in matched:
        if "feedback" not in entry:
            continue
        try:
            records.append(FeedbackRecord.model_validate(entry))
        except Exception:
            continue
    return records


def store_to_memory(hypothesis: StructuredHypothesis, review: ScientistReview) -> None:
    ensure_storage()
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    fingerprint = _compute_fingerprint(hypothesis)
    experiment_type = fingerprint.split("__")[0]
    created_at = review.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z")

    bucket = data.setdefault(fingerprint, [])
    if not isinstance(bucket, list):
        bucket = []
        data[fingerprint] = bucket

    for annotation in review.annotations:
        bucket.append(
            {
                "fingerprint": fingerprint,
                "section": annotation.section.value,
                "feedback_text": annotation.feedback_text,
                "requested_changes": annotation.requested_changes,
                "experiment_type": experiment_type,
                "created_at": created_at,
                "applied_count": 0,
            }
        )

    MEMORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def retrieve_prior_feedback(
    hypothesis: StructuredHypothesis,
    section: str,
    max_results: int = 3,
) -> list[str]:
    if not MEMORY_FILE.exists():
        return []
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, dict) or not data:
        return []

    fingerprint = _compute_fingerprint(hypothesis)
    experiment_type = fingerprint.split("__")[0]

    all_entries = [
        (fp_key, entry)
        for fp_key, entries in data.items()
        if isinstance(entries, list)
        for entry in entries
        if isinstance(entry, dict)
    ]

    def tier(fp_key: str, entry: dict[str, Any]) -> int:
        et = fp_key.split("__")[0]
        s = str(entry.get("section", ""))
        if fp_key == fingerprint and s == section:
            return 0
        if et == experiment_type and s == section:
            return 1
        if fp_key == fingerprint:
            return 2
        if et == experiment_type:
            return 3
        return 99

    all_entries.sort(
        key=lambda x: (
            tier(x[0], x[1]),
            x[1].get("created_at", "")[::-1],
        )
    )

    results: list[str] = []
    seen: set[str] = set()
    used: list[tuple[str, dict[str, Any]]] = []

    for fp_key, entry in all_entries:
        if tier(fp_key, entry) == 99:
            continue
        if len(results) >= max_results:
            break
        contributed = False
        changes = entry.get("requested_changes", [])
        if isinstance(changes, list) and changes:
            for change in changes:
                if isinstance(change, str) and change not in seen and len(results) < max_results:
                    results.append(change)
                    seen.add(change)
                    contributed = True
        else:
            text = str(entry.get("feedback_text", "")).strip()
            if text and text not in seen and len(results) < max_results:
                results.append(text)
                seen.add(text)
                contributed = True
        if contributed:
            used.append((fp_key, entry))

    if used:
        for fp_key, used_entry in used:
            for entry in data.get(fp_key, []):
                if entry.get("created_at") == used_entry.get("created_at"):
                    entry["applied_count"] = entry.get("applied_count", 0) + 1
        MEMORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return results


def _compute_fingerprint(hypothesis: StructuredHypothesis) -> str:
    et = hypothesis.experiment_type or "unknown"
    if et == "missing_required_field":
        et = "unknown"
    intervention = hypothesis.intervention or ""
    if intervention == "missing_required_field":
        intervention = ""
    words = intervention.lower().split()[:2]
    ic = "_".join(words) if words else "unknown"
    return f"{et}__{ic}"

