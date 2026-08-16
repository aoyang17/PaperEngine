from __future__ import annotations

from pathlib import Path
from typing import Any

from .candidates import load_candidates, save_candidates
from .topic import load_preferences, load_topic
from .util import read_jsonl, utc_now

SCORE_VERSION = "candidate-module-relevance-v2"
CONFIDENCE_LEVELS = {"low", "medium", "high"}
COMPONENT_RANGES = {
    "content": (-0.70, 0.70),
    "preference": (-0.15, 0.15),
    "credibility": (-0.15, 0.15),
}


def _clamp_text(value: Any, limit: int = 1200) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _candidate_for_scoring(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": candidate.get("record_id"),
        "candidate_id": candidate.get("candidate_id"),
        "title": candidate.get("title"),
        "authors": candidate.get("authors") or [],
        "year": candidate.get("year"),
        "venue": candidate.get("venue"),
        "abstract": _clamp_text(candidate.get("abstract")),
        "status": candidate.get("status"),
        "score": candidate.get("score", 0.0),
    }


def export_scoring_batch(
    root: str | Path,
    status: str = "new",
    limit: int = 20,
    min_score: float | None = None,
) -> dict[str, Any]:
    candidates = load_candidates(root)
    selected = []
    for candidate in candidates:
        if status and candidate.get("status") != status:
            continue
        if min_score is not None and float(candidate.get("score") or 0.0) < float(min_score):
            continue
        selected.append(_candidate_for_scoring(candidate))
        if len(selected) >= max(int(limit), 0):
            break
    return {
        "ok": True,
        "score_version": SCORE_VERSION,
        "rubric": {
            "score": [-1.0, 1.0],
            "content": list(COMPONENT_RANGES["content"]),
            "preference": list(COMPONENT_RANGES["preference"]),
            "credibility": list(COMPONENT_RANGES["credibility"]),
        },
        "topic": load_topic(root),
        "preferences": load_preferences(root),
        "candidates": selected,
    }


def _require_number(record: dict[str, Any], key: str) -> float:
    value = record.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    return float(value)


def _validate_range(name: str, value: float, lower: float, upper: float) -> None:
    if value < lower or value > upper:
        raise ValueError(f"{name} must be between {lower:g} and {upper:g}")


def validate_score_record(record: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(record.get("candidate_id") or "").strip()
    record_id = str(record.get("record_id") or "").strip()
    if not candidate_id and not record_id:
        raise ValueError("candidate_id or record_id is required")
    score = _require_number(record, "score")
    _validate_range("score", score, -1.0, 1.0)

    components: dict[str, float] = {}
    for key, (lower, upper) in COMPONENT_RANGES.items():
        value = _require_number(record, key)
        _validate_range(key, value, lower, upper)
        components[key] = round(value, 3)

    confidence = str(record.get("score_confidence") or "medium").strip().lower()
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError("score_confidence must be low, medium, or high")

    reasons = record.get("reasons") or record.get("score_reasons") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    if not isinstance(reasons, list) or not all(isinstance(reason, str) for reason in reasons):
        raise ValueError("reasons must be a list of strings")

    module_ids = record.get("module_ids") or []
    if not isinstance(module_ids, list) or not all(isinstance(value, str) and value.strip() for value in module_ids):
        raise ValueError("module_ids must be a list of non-empty strings")
    module_ids = list(dict.fromkeys(value.strip() for value in module_ids))
    module_scores = record.get("module_scores") or {}
    if not isinstance(module_scores, dict):
        raise ValueError("module_scores must be an object")
    normalized_module_scores: dict[str, float] = {}
    for module_id, module_score in module_scores.items():
        if not isinstance(module_score, (int, float)):
            raise ValueError(f"module score for {module_id} must be a number")
        _validate_range(f"module score for {module_id}", float(module_score), 0.0, 1.0)
        normalized_module_scores[str(module_id)] = round(float(module_score), 3)
    if set(module_ids) != set(normalized_module_scores):
        raise ValueError("module_ids must match module_scores keys")
    primary_module_id = str(record.get("primary_module_id") or "").strip() or None
    if primary_module_id and primary_module_id not in module_ids:
        raise ValueError("primary_module_id must be included in module_ids")
    module_reasons = record.get("module_reasons") or {}
    if not isinstance(module_reasons, dict):
        raise ValueError("module_reasons must be an object")
    normalized_module_reasons: dict[str, list[str]] = {}
    for module_id, values in module_reasons.items():
        if module_id not in module_ids or not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise ValueError("module_reasons must contain string lists for assigned modules")
        normalized_module_reasons[module_id] = [value.strip() for value in values if value.strip()][:6]
    scope_evidence = record.get("scope_evidence") or []
    if not isinstance(scope_evidence, list) or not all(isinstance(value, str) for value in scope_evidence):
        raise ValueError("scope_evidence must be a list of strings")

    return {
        "record_id": record_id or None,
        "candidate_id": candidate_id,
        "score": round(score, 3),
        "score_components": components,
        "score_confidence": confidence,
        "score_reasons": [reason.strip() for reason in reasons if reason.strip()][:8],
        "scored_by": str(record.get("scored_by") or "codex").strip() or "codex",
        "score_version": str(record.get("score_version") or SCORE_VERSION),
        "module_ids": module_ids,
        "primary_module_id": primary_module_id,
        "module_scores": normalized_module_scores,
        "module_reasons": normalized_module_reasons,
        "cross_module": len(module_ids) > 1,
        "scope_evidence": [value.strip() for value in scope_evidence if value.strip()][:12],
    }


def apply_candidate_scores(root: str | Path, scores_path: str | Path) -> dict[str, Any]:
    incoming = read_jsonl(Path(scores_path))
    validated = [validate_score_record(record) for record in incoming]
    topic = load_topic(root)
    allowed_module_ids = {
        str(module.get("id"))
        for module in topic.get("research_modules") or []
        if isinstance(module, dict) and module.get("id")
    }
    for score in validated:
        unknown = set(score["module_ids"]) - allowed_module_ids
        if unknown:
            raise ValueError(f"unknown research module(s): {', '.join(sorted(unknown))}")
    records = load_candidates(root)
    by_record_id = {str(record.get("record_id")): record for record in records if record.get("record_id")}
    by_candidate_id: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_candidate_id.setdefault(str(record.get("candidate_id")), []).append(record)

    for score in validated:
        if score["record_id"]:
            if score["record_id"] not in by_record_id:
                raise ValueError(f"unknown candidate record: {score['record_id']}")
            continue
        matches = by_candidate_id.get(score["candidate_id"], [])
        if not matches:
            raise ValueError(f"unknown candidate: {score['candidate_id']}")
        if len(matches) > 1:
            raise ValueError(f"ambiguous candidate_id: {score['candidate_id']}; include record_id or run `battery_lit candidates repair --fix`")

    now = utc_now()
    for score in validated:
        record = by_record_id[score["record_id"]] if score["record_id"] else by_candidate_id[score["candidate_id"]][0]
        record["score"] = score["score"]
        record["score_status"] = "scored"
        record["score_components"] = score["score_components"]
        record["score_confidence"] = score["score_confidence"]
        record["score_reasons"] = score["score_reasons"]
        record["scored_by"] = score["scored_by"]
        record["scored_at"] = now
        record["score_version"] = score["score_version"]
        record["module_ids"] = score["module_ids"]
        record["primary_module_id"] = score["primary_module_id"]
        record["module_scores"] = score["module_scores"]
        record["module_reasons"] = score["module_reasons"]
        record["cross_module"] = score["cross_module"]
        record["scope_evidence"] = score["scope_evidence"]
        record["updated_at"] = now

    save_candidates(root, records)
    return {"ok": True, "updated": len(validated), "score_version": SCORE_VERSION}
