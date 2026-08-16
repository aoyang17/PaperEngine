from __future__ import annotations

import json
import subprocess

import pytest

from conftest import ROOT
from battery_lit.candidates import append_candidates, get_candidate, load_candidates, normalize_candidate
from battery_lit.scoring import apply_candidate_scores, export_scoring_batch
from battery_lit.topic import init_topic
from battery_lit.util import write_jsonl


def _add_candidates(root):
    append_candidates(
        root,
        [
            {
                "title": "Relevant Flow Guidance",
                "authors": ["Ada Example"],
                "year": 2026,
                "venue": "arXiv",
                "abstract": "Test-time guidance for flow matching in engineering design.",
                "source": "fixture",
            },
            {
                "title": "Unrelated Education Chatbot",
                "authors": ["Ben Example"],
                "year": 2025,
                "venue": "Unknown Journal",
                "abstract": "A classroom chatbot deployment.",
                "source": "fixture",
            },
        ],
    )


def test_export_scoring_batch_uses_compact_candidate_records(tmp_path):
    init_topic(tmp_path, title="Test-time guidance", direction="Flow model guidance")
    _add_candidates(tmp_path)

    batch = export_scoring_batch(tmp_path, status="new", limit=1)

    assert batch["ok"] is True
    assert batch["topic"]["title"] == "Test-time guidance"
    assert len(batch["candidates"]) == 1
    candidate = batch["candidates"][0]
    assert candidate["candidate_id"] == "CAND-001"
    assert set(candidate) == {"record_id", "candidate_id", "title", "authors", "year", "venue", "abstract", "status", "score"}


def test_apply_candidate_scores_writes_score_metadata_atomically(tmp_path):
    init_topic(tmp_path)
    _add_candidates(tmp_path)
    scores = tmp_path / "scores.jsonl"
    scores.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "candidate_id": "CAND-001",
                        "content": 0.62,
                        "preference": 0.08,
                        "credibility": 0.05,
                        "score": 0.75,
                        "score_confidence": "high",
                        "reasons": ["Directly studies test-time guidance for flow models."],
                        "scored_by": "codex",
                    }
                ),
                json.dumps(
                    {
                        "candidate_id": "CAND-002",
                        "content": -0.55,
                        "preference": -0.1,
                        "credibility": 0.0,
                        "score": -0.65,
                        "score_confidence": "medium",
                        "reasons": ["Education chatbot paper is outside topic scope."],
                        "scored_by": "codex",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = apply_candidate_scores(tmp_path, scores)

    assert result["ok"] is True
    assert result["updated"] == 2
    first = get_candidate(tmp_path, "CAND-001")
    assert first["score"] == 0.75
    assert first["score_status"] == "scored"
    assert first["score_components"] == {"content": 0.62, "preference": 0.08, "credibility": 0.05}
    assert first["score_confidence"] == "high"
    assert first["score_reasons"] == ["Directly studies test-time guidance for flow models."]
    assert first["scored_by"] == "codex"
    assert first["score_version"] == "candidate-relevance-v1"
    assert "scored_at" in first


def test_apply_candidate_scores_rejects_invalid_score_without_partial_write(tmp_path):
    init_topic(tmp_path)
    _add_candidates(tmp_path)
    scores = tmp_path / "bad_scores.jsonl"
    scores.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "candidate_id": "CAND-001",
                        "content": 0.6,
                        "preference": 0.0,
                        "credibility": 0.0,
                        "score": 0.6,
                        "score_confidence": "medium",
                        "reasons": ["Valid first score."],
                    }
                ),
                json.dumps(
                    {
                        "candidate_id": "CAND-002",
                        "content": 0.1,
                        "preference": 0.0,
                        "credibility": 0.0,
                        "score": 1.2,
                        "score_confidence": "medium",
                        "reasons": ["Invalid final score."],
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="score must be between -1 and 1"):
        apply_candidate_scores(tmp_path, scores)

    assert [candidate["score"] for candidate in load_candidates(tmp_path)] == [0.0, 0.0]


def test_apply_candidate_scores_rejects_unknown_candidate(tmp_path):
    init_topic(tmp_path)
    _add_candidates(tmp_path)
    scores = tmp_path / "unknown_scores.jsonl"
    scores.write_text(
        json.dumps(
            {
                "candidate_id": "CAND-999",
                "content": 0.1,
                "preference": 0.0,
                "credibility": 0.0,
                "score": 0.1,
                "score_confidence": "low",
                "reasons": ["Unknown candidate."],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown candidate"):
        apply_candidate_scores(tmp_path, scores)


def test_apply_candidate_scores_requires_record_id_for_ambiguous_candidate_id(tmp_path):
    init_topic(tmp_path)
    first = normalize_candidate({"candidate_id": "CAND-001", "title": "First", "authors": [], "year": 2026, "venue": "X", "abstract": "", "source": "fixture"})
    second = normalize_candidate({"candidate_id": "CAND-001", "title": "Second", "authors": [], "year": 2026, "venue": "X", "abstract": "", "source": "fixture"})
    write_jsonl(tmp_path / "candidates.jsonl", [first, second])
    scores = tmp_path / "scores.jsonl"
    payload = {
        "candidate_id": "CAND-001",
        "content": 0.2,
        "preference": 0.0,
        "credibility": 0.0,
        "score": 0.2,
        "score_confidence": "medium",
        "reasons": ["Relevant enough."],
    }
    scores.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="ambiguous candidate_id"):
        apply_candidate_scores(tmp_path, scores)

    payload["record_id"] = second["record_id"]
    scores.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    result = apply_candidate_scores(tmp_path, scores)
    records = load_candidates(tmp_path)

    assert result["updated"] == 1
    assert records[0]["score_status"] == "unscored"
    assert records[1]["score_status"] == "scored"
    assert records[1]["score"] == 0.2


def test_scoring_cli_exports_applies_and_lists_by_score(tmp_path):
    init_topic(tmp_path, title="Guided generation", direction="test-time guidance")
    _add_candidates(tmp_path)
    batch_proc = subprocess.run(
        [
            str(ROOT / "bin" / "battery_lit"),
            "candidates",
            "scoring-batch",
            "--root",
            str(tmp_path),
            "--limit",
            "2",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    batch = json.loads(batch_proc.stdout)
    assert [candidate["candidate_id"] for candidate in batch["candidates"]] == ["CAND-001", "CAND-002"]

    scores = tmp_path / "scores.jsonl"
    scores.write_text(
        json.dumps(
            {
                "candidate_id": "CAND-001",
                "content": 0.6,
                "preference": 0.1,
                "credibility": 0.0,
                "score": 0.7,
                "score_confidence": "high",
                "reasons": ["Relevant to guided generation."],
            }
        )
        + "\n"
        + json.dumps(
            {
                "candidate_id": "CAND-002",
                "content": -0.5,
                "preference": -0.1,
                "credibility": 0.0,
                "score": -0.6,
                "score_confidence": "medium",
                "reasons": ["Outside topic."],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    apply_proc = subprocess.run(
        [str(ROOT / "bin" / "battery_lit"), "candidates", "apply-scores", "--root", str(tmp_path), "--scores", str(scores)],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(apply_proc.stdout)["updated"] == 2

    list_proc = subprocess.run(
        [
            str(ROOT / "bin" / "battery_lit"),
            "candidates",
            "list",
            "--root",
            str(tmp_path),
            "--sort",
            "score",
            "--min-score",
            "0",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    listed = json.loads(list_proc.stdout)
    assert [candidate["candidate_id"] for candidate in listed] == ["CAND-001"]
