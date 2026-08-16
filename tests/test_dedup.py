from __future__ import annotations

import json
import subprocess

from conftest import ROOT
from battery_lit.candidates import append_candidates, load_candidates, mark_candidate
from battery_lit.dedup import candidates_match, deduplicate_candidates
from battery_lit.topic import init_topic


def test_candidates_match_arxiv_versions_and_missing_year_title():
    assert candidates_match(
        {"title": "D-Flow: Differentiating through Flows for Controlled Generation", "arxiv_id": "2501.12345v1"},
        {"title": "D-Flow: Differentiating through Flows for Controlled Generation", "arxiv_id": "2501.12345v2"},
    )
    assert candidates_match(
        {"title": "D-Flow: Differentiating through Flows for Controlled Generation", "year": 2025},
        {"title": "D Flow Differentiating through Flows for Controlled Generation", "year": None},
    )


def test_candidates_match_fuzzy_title_requires_author_or_year_support():
    assert candidates_match(
        {"title": "D-Flow: Differentiating through Flows for Controlled Generation", "authors": ["Jane Doe"], "year": 2025},
        {"title": "D Flow Differentiating Through Flows for Controlled Generation", "authors": ["J. Doe"], "year": 2025},
    )
    assert not candidates_match(
        {"title": "Controlled Generation with Flow Models", "authors": ["Jane Doe"], "year": 2025},
        {"title": "Controlled Generation with Diffusion Models", "authors": ["Jane Doe"], "year": 2025},
    )


def test_dedup_fix_keeps_relevant_candidate_and_merges_metadata_and_pdf(tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [
            {
                "title": "D-Flow: Differentiating through Flows for Controlled Generation",
                "authors": ["Ada Example"],
                "year": 2025,
                "venue": "arXiv",
                "abstract": "Short abstract.",
                "source": "arxiv",
                "arxiv_id": "2501.12345v1",
            },
            {
                "title": "D Flow Differentiating through Flows for Controlled Generation",
                "authors": ["Ada Example", "Ben Researcher"],
                "year": None,
                "venue": "ICLR",
                "abstract": "Longer abstract with controlled generation details.",
                "source": "openalex",
                "doi": "10.5555/dflow",
                "url": "https://example.org/dflow",
                "score": 0.72,
                "score_status": "scored",
            },
        ],
    )
    mark_candidate(tmp_path, "CAND-001", "relevant")
    incoming = tmp_path / "papers" / "_incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    (incoming / "CAND-002.pdf").write_bytes(b"%PDF-1.4\n")

    result = deduplicate_candidates(tmp_path, fix=True)
    records = load_candidates(tmp_path)

    assert result["ok"] is True
    assert result["merged"] == 1
    assert result["removed"] == 1
    assert result["kept_candidate_ids"] == ["CAND-001"]
    assert result["duplicate_groups"] == [{"primary": "CAND-001", "kept": "CAND-001", "duplicates": ["CAND-002"]}]
    assert [record["candidate_id"] for record in records] == ["CAND-001"]
    kept = records[0]
    assert kept["status"] == "relevant"
    assert kept["doi"] == "10.5555/dflow"
    assert kept["venue"] == "arXiv"
    assert kept["score_status"] == "scored"
    assert kept["score"] == 0.72
    assert kept["merged_from"] == ["CAND-002"]
    assert sorted(kept["sources_seen"]) == ["arxiv", "openalex"]
    assert (incoming / "CAND-001.pdf").exists()
    assert not (incoming / "CAND-002.pdf").exists()


def test_dedup_cli_reports_without_fix_and_fixes_with_flag(tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [
            {"title": "Same Paper", "authors": ["Ada"], "year": 2026, "venue": "arXiv", "abstract": "", "source": "arxiv"},
            {"title": "Same Paper", "authors": ["Ada"], "year": None, "venue": "unknown", "abstract": "", "source": "openalex"},
        ],
    )

    report = subprocess.run(
        [str(ROOT / "bin" / "battery_lit"), "tool", "dedup", "--root", str(tmp_path), "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert report.returncode == 1
    assert json.loads(report.stdout)["duplicates"] == ["CAND-002"]
    assert len(load_candidates(tmp_path)) == 2

    fixed = subprocess.run(
        [str(ROOT / "bin" / "battery_lit"), "tool", "dedup", "--root", str(tmp_path), "--fix", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert fixed.returncode == 0, fixed.stderr
    payload = json.loads(fixed.stdout)
    assert payload["removed"] == 1
    assert payload["kept_candidate_ids"] == ["CAND-001"]
    assert len(load_candidates(tmp_path)) == 1
