from __future__ import annotations

import json
import subprocess

from conftest import ROOT
from battery_lit.candidates import append_candidates, get_candidate
from battery_lit.preferences import check_preferences, mark_candidate_with_feedback, record_label, score_candidate
from battery_lit.topic import init_topic, load_preferences, save_preferences


def test_record_label_counts_without_rule_extraction(tmp_path):
    init_topic(tmp_path)
    candidate = {"title": "Agentic discovery system", "abstract": "self evolving scientist agents", "venue": "ICLR"}
    for _ in range(9):
        record_label(tmp_path, candidate, "relevant")
    prefs = load_preferences(tmp_path)
    assert prefs["effective_feedbacks"] == 9
    assert load_preferences(tmp_path).get("positive_terms", []) == []
    record_label(tmp_path, candidate, "relevant")
    prefs = load_preferences(tmp_path)
    assert prefs["effective_feedbacks"] == 10
    assert prefs.get("positive_terms", []) == []


def test_mark_candidate_with_feedback_counts_once_per_effective_decision(tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [
            {
                "title": "Useful Paper",
                "authors": ["Ada"],
                "year": 2026,
                "venue": "ICLR",
                "abstract": "optimal control",
                "source": "fixture",
            }
        ],
    )

    first = mark_candidate_with_feedback(tmp_path, "CAND-001", "relevant")
    second = mark_candidate_with_feedback(tmp_path, "CAND-001", "relevant")
    third = mark_candidate_with_feedback(tmp_path, "CAND-001", "irrelevant")

    assert first["preference_recorded_decision"] == "relevant"
    assert second["preference_recorded_decision"] == "relevant"
    assert third["preference_recorded_decision"] == "irrelevant"
    assert load_preferences(tmp_path)["effective_feedbacks"] == 2
    assert get_candidate(tmp_path, "CAND-001")["status"] == "irrelevant"


def test_dismissed_does_not_count_as_effective_feedback(tmp_path):
    init_topic(tmp_path)
    append_candidates(tmp_path, [{"title": "Dismissed Paper", "authors": [], "year": 2026, "venue": "X", "abstract": "", "source": "fixture"}])

    mark_candidate_with_feedback(tmp_path, "CAND-001", "dismissed")

    assert load_preferences(tmp_path)["effective_feedbacks"] == 0


def test_preference_terms_affect_score():
    candidate = {"title": "Agentic discovery", "abstract": "", "venue": "", "score": 0}
    assert score_candidate(candidate, {"positive_terms": ["agentic"], "negative_terms": []}) > 0
    assert score_candidate(candidate, {"positive_terms": [], "negative_terms": ["agentic"]}) < 0
    assert score_candidate(candidate, {"like": ["agentic"], "dislike": []}) > 0


def test_preferences_check_accepts_compact_llm_memory(tmp_path):
    init_topic(tmp_path)
    save_preferences(
        tmp_path,
        {
            "schema_version": "v2",
            "effective_feedbacks": 3,
            "evidence_count": 3,
            "like": ["multiple shooting optimal control"],
            "dislike": ["unrelated language model benchmark"],
            "query_hints": ["two point boundary value problem"],
            "exclude_hints": ["climate misinformation"],
            "rationale": "Labels prefer ODE optimal-control methods.",
        },
    )

    result = check_preferences(tmp_path)

    assert result["ok"] is True
    assert result["errors"] == []
    assert result["evidence_count"] == 3


def test_preferences_check_rejects_bad_shape(tmp_path):
    init_topic(tmp_path)
    save_preferences(tmp_path, {"schema_version": "v2", "effective_feedbacks": -1, "like": ["x" * 161]})

    result = check_preferences(tmp_path)

    assert result["ok"] is False
    assert "effective_feedbacks must be a non-negative integer" in result["errors"]
    assert "like contains an item longer than 160 characters" in result["errors"]


def test_preferences_check_cli(tmp_path):
    init_topic(tmp_path)

    completed = subprocess.run(
        [str(ROOT / "bin" / "battery_lit"), "preferences", "check", "--root", str(tmp_path), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    result = json.loads(completed.stdout)

    assert result["ok"] is True
    assert result["effective_feedbacks"] == 0
