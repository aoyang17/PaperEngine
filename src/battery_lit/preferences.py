from __future__ import annotations

from pathlib import Path
from typing import Any

from .candidates import load_candidates, save_candidates
from .topic import load_preferences, save_preferences
from .util import normalize_text, utc_now

EFFECTIVE_DECISIONS = {"relevant", "irrelevant"}
LIST_FIELDS = [
    "positive_terms",
    "negative_terms",
    "venue_follows",
    "author_follows",
    "like",
    "dislike",
    "query_hints",
    "exclude_hints",
]


def record_label(root: str | Path, candidate: dict[str, Any], decision: str) -> dict[str, Any]:
    """Record one effective feedback count only.

    Preference extraction is intentionally LLM-driven in the topic-local
    preference_refresh skill. This function keeps the deterministic write path
    fast and side-effect-light.
    """
    prefs = load_preferences(root)
    if decision in EFFECTIVE_DECISIONS:
        prefs["effective_feedbacks"] = int(prefs.get("effective_feedbacks") or 0) + 1
    save_preferences(root, prefs)
    return prefs


def mark_candidate_with_feedback(root: str | Path, candidate_id: str, decision: str) -> dict[str, Any]:
    mapping = {"relevant": "relevant", "irrelevant": "irrelevant", "dismissed": "dismissed", "none": "relevant"}
    if decision not in mapping:
        raise ValueError(f"unsupported decision: {decision}")

    records = load_candidates(root)
    for record in records:
        if record.get("candidate_id") != candidate_id:
            continue
        previous_recorded = record.get("preference_recorded_decision")
        record["status"] = mapping[decision]
        record["decision"] = decision
        record["updated_at"] = utc_now()
        should_count = decision in EFFECTIVE_DECISIONS and previous_recorded != decision
        if should_count:
            record["preference_recorded_decision"] = decision
        save_candidates(root, records)
        if should_count:
            record_label(root, record, decision)
        return record
    raise KeyError(f"candidate not found: {candidate_id}")


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def check_preferences(root: str | Path) -> dict[str, Any]:
    prefs = load_preferences(root)
    errors: list[str] = []
    warnings: list[str] = []

    if prefs.get("schema_version") != "v2":
        errors.append("schema_version must be v2")

    for field in ["effective_feedbacks", "evidence_count"]:
        if field in prefs:
            value = prefs.get(field)
            if not isinstance(value, int) or value < 0:
                errors.append(f"{field} must be a non-negative integer")

    for field in LIST_FIELDS:
        if field not in prefs:
            continue
        value = prefs.get(field)
        if not _string_list(value):
            errors.append(f"{field} must be a list of strings")
            continue
        if len(value) > 50:
            errors.append(f"{field} must contain at most 50 items")
        for item in value:
            if len(item) > 160:
                errors.append(f"{field} contains an item longer than 160 characters")

    rationale = prefs.get("rationale")
    if rationale is not None:
        if not isinstance(rationale, str):
            errors.append("rationale must be a string")
        elif len(rationale) > 2000:
            errors.append("rationale must be at most 2000 characters")

    if not (prefs.get("like") or prefs.get("dislike") or prefs.get("query_hints") or prefs.get("exclude_hints")):
        warnings.append("preferences contain no LLM-synthesized like/dislike/query hints yet")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "effective_feedbacks": int(prefs.get("effective_feedbacks") or 0),
        "evidence_count": int(prefs.get("evidence_count") or 0),
    }


def score_candidate(candidate: dict[str, Any], preferences: dict[str, Any] | None = None) -> float:
    score = float(candidate.get("score") or 0.0)
    preferences = preferences or {}
    text = normalize_text(" ".join([str(candidate.get("title") or ""), str(candidate.get("abstract") or ""), str(candidate.get("venue") or "")]))
    positive_terms = list(preferences.get("positive_terms") or []) + list(preferences.get("like") or []) + list(preferences.get("query_hints") or [])
    negative_terms = list(preferences.get("negative_terms") or []) + list(preferences.get("dislike") or []) + list(preferences.get("exclude_hints") or [])
    for term in positive_terms:
        if normalize_text(str(term)) in text:
            score += 1.0
    for term in negative_terms:
        if normalize_text(str(term)) in text:
            score -= 1.0
    if candidate.get("doi") or candidate.get("arxiv_id"):
        score += 0.25
    if candidate.get("pdf_url"):
        score += 0.25
    return score
