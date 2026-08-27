from __future__ import annotations

import json
import subprocess

import pytest

from conftest import ROOT
from paper_engine.candidates import append_candidates, get_candidate, load_candidates, mark_candidate, normalize_candidate, remove_candidate_by_record_id, remove_candidates_by_bibkey, repair_candidate_records
from paper_engine.util import write_jsonl
from paper_engine.topic import init_topic


def test_candidate_jsonl_append_show_and_mark(tmp_path):
    init_topic(tmp_path)
    added = append_candidates(
        tmp_path,
        [
            {
                "title": "Useful Paper",
                "authors": ["Ada Example"],
                "year": 2026,
                "venue": "ICLR",
                "abstract": "agentic scientific discovery",
                "doi": "10.1/useful",
                "source": "fixture",
            }
        ],
    )

    assert added[0]["candidate_id"] == "CAND-001"
    assert added[0]["record_id"].startswith("REC-")
    assert get_candidate(tmp_path, "CAND-001")["title"] == "Useful Paper"
    marked = mark_candidate(tmp_path, "CAND-001", "relevant")
    assert marked["status"] == "relevant"
    assert load_candidates(tmp_path)[0]["decision"] == "relevant"


def test_get_and_mark_reject_ambiguous_candidate_id(tmp_path):
    init_topic(tmp_path)
    records = [
        normalize_candidate({"candidate_id": "CAND-001", "title": "First", "authors": [], "year": 2026, "venue": "X", "abstract": "", "source": "fixture"}),
        normalize_candidate({"candidate_id": "CAND-001", "title": "Second", "authors": [], "year": 2026, "venue": "X", "abstract": "", "source": "fixture"}),
    ]
    write_jsonl(tmp_path / "candidates.jsonl", records)

    with pytest.raises(ValueError, match="ambiguous candidate_id"):
        get_candidate(tmp_path, "CAND-001")
    with pytest.raises(ValueError, match="ambiguous candidate_id"):
        mark_candidate(tmp_path, "CAND-001", "relevant")


def test_candidate_validation_rejects_bad_status():
    with pytest.raises(ValueError):
        normalize_candidate({"candidate_id": "CAND-001", "title": "Bad", "authors": [], "year": 2026, "venue": "X", "abstract": "", "source": "x", "status": "bad"})


def test_candidate_extracts_arxiv_id_and_year_from_pdf_url():
    candidate = normalize_candidate(
        {
            "title": "Arxiv Paper",
            "authors": ["Ada Example"],
            "venue": "unknown",
            "abstract": "",
            "pdf_url": "https://arxiv.org/pdf/2601.16175v2",
            "source": "arxiv",
        },
        "CAND-001",
    )
    assert candidate["arxiv_id"] == "2601.16175v2"
    assert candidate["year"] == 2026


def test_candidate_extracts_venue_from_extra_dict():
    candidate = normalize_candidate(
        {
            "title": "Journal Paper",
            "authors": ["Ada Example"],
            "year": 2026,
            "abstract": "",
            "source": "unpaywall",
            "extra": {"journal_name": "Nature Machine Intelligence"},
        },
        "CAND-001",
    )
    assert candidate["venue"] == "Nature Machine Intelligence"


def test_candidate_extracts_venue_from_stringified_extra():
    candidate = normalize_candidate(
        {
            "title": "Conference Paper",
            "authors": ["Ada Example"],
            "year": 2026,
            "abstract": "",
            "source": "dblp",
            "extra": "{'venue': 'International Conference on Learning Representations'}",
        },
        "CAND-001",
    )
    assert candidate["venue"] == "International Conference on Learning Representations"


def test_candidate_uses_arxiv_as_venue_without_using_category_code():
    candidate = normalize_candidate(
        {
            "title": "Arxiv Paper",
            "authors": ["Ada Example"],
            "abstract": "",
            "source": "arxiv",
            "categories": "cs.LG; stat.ML",
            "url": "https://arxiv.org/abs/2601.16175",
        },
        "CAND-001",
    )
    assert candidate["venue"] == "arXiv"


def test_remove_candidates_by_bibkey_removes_queue_item_only(tmp_path):
    init_topic(tmp_path)
    bibkey = "Example2026Useful"
    append_candidates(
        tmp_path,
        [
            {
                "title": "Useful Paper",
                "authors": ["Ada Example"],
                "year": 2026,
                "venue": "ICLR",
                "abstract": "",
                "source": "fixture",
                "status": "in_library",
                "bibkey": bibkey,
            }
        ],
    )
    (tmp_path / "library.bib").write_text("@article{Example2026Useful,\n  title = {Useful Paper},\n}\n", encoding="utf-8")
    paper_dir = tmp_path / "papers" / bibkey
    paper_dir.mkdir(parents=True)
    (paper_dir / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    (paper_dir / "reading_result.html").write_text("<html></html>", encoding="utf-8")

    result = remove_candidates_by_bibkey(tmp_path, bibkey)

    assert result == {
        "ok": True,
        "bibkey": bibkey,
        "removed_count": 1,
        "removed_candidate_ids": ["CAND-001"],
        "matched_candidate_ids": ["CAND-001"],
        "candidate_count": 0,
    }
    assert load_candidates(tmp_path) == []
    assert "Example2026Useful" in (tmp_path / "library.bib").read_text(encoding="utf-8")
    assert (paper_dir / "paper.pdf").exists()
    assert (paper_dir / "reading_result.html").exists()


def test_remove_candidates_by_bibkey_missing_and_invalid_do_not_change_queue(tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [
            {
                "title": "Useful Paper",
                "authors": ["Ada Example"],
                "year": 2026,
                "venue": "ICLR",
                "abstract": "",
                "source": "fixture",
                "bibkey": "Example2026Useful",
            }
        ],
    )
    before = (tmp_path / "candidates.jsonl").read_text(encoding="utf-8")

    missing = remove_candidates_by_bibkey(tmp_path, "Missing2026Paper")

    assert missing["ok"] is False
    assert missing["removed_count"] == 0
    assert missing["matched_candidate_ids"] == []
    assert (tmp_path / "candidates.jsonl").read_text(encoding="utf-8") == before
    with pytest.raises(ValueError):
        remove_candidates_by_bibkey(tmp_path, "../Bad")
    assert (tmp_path / "candidates.jsonl").read_text(encoding="utf-8") == before


def test_remove_candidates_by_bibkey_rejects_multiple_matching_historical_records(tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [
            {"title": "First", "authors": ["Ada"], "year": 2026, "venue": "ICLR", "abstract": "", "source": "fixture", "bibkey": "Shared2026Paper"},
            {"title": "Second", "authors": ["Grace"], "year": 2026, "venue": "arXiv", "abstract": "", "source": "fixture", "bibkey": "Shared2026Paper"},
            {"title": "Third", "authors": ["Alan"], "year": 2025, "venue": "NeurIPS", "abstract": "", "source": "fixture", "bibkey": "Other2025Paper"},
        ],
    )

    result = remove_candidates_by_bibkey(tmp_path, "Shared2026Paper")

    assert result["ok"] is False
    assert result["removed_count"] == 0
    assert result["removed_candidate_ids"] == []
    assert result["matched_candidate_ids"] == ["CAND-001", "CAND-002"]
    assert [candidate["candidate_id"] for candidate in load_candidates(tmp_path)] == ["CAND-001", "CAND-002", "CAND-003"]


def test_remove_candidates_by_bibkey_cli_json_and_exit_codes(tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [
            {
                "title": "Useful Paper",
                "authors": ["Ada Example"],
                "year": 2026,
                "venue": "ICLR",
                "abstract": "",
                "source": "fixture",
                "bibkey": "Example2026Useful",
            }
        ],
    )

    removed = subprocess.run(
        [str(ROOT / "bin" / "paper_engine"), "candidates", "remove-by-bibkey", "--root", str(tmp_path), "Example2026Useful", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert removed.returncode == 0, removed.stderr
    payload = json.loads(removed.stdout)
    assert payload["ok"] is True
    assert payload["bibkey"] == "Example2026Useful"
    assert payload["removed_count"] == 1
    assert payload["removed_candidate_ids"] == ["CAND-001"]
    assert payload["matched_candidate_ids"] == ["CAND-001"]

    missing = subprocess.run(
        [str(ROOT / "bin" / "paper_engine"), "candidates", "remove-by-bibkey", "--root", str(tmp_path), "Example2026Useful", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing.returncode == 1
    missing_payload = json.loads(missing.stdout)
    assert missing_payload["ok"] is False
    assert missing_payload["removed_count"] == 0
    assert missing_payload["matched_candidate_ids"] == []


def test_repair_candidate_records_merges_same_paper_and_renumbers_different_papers(tmp_path):
    init_topic(tmp_path)
    same_unscored = normalize_candidate(
        {
            "candidate_id": "CAND-043",
            "title": "Zero-Shot Solving of Imaging Inverse Problems Via Noise-Refined Likelihood Guided Diffusion Models",
            "authors": [],
            "year": None,
            "venue": "unknown",
            "abstract": "",
            "doi": "10.2139/ssrn.5295204",
            "source": "crossref",
            "status": "relevant",
            "decision": "relevant",
        }
    )
    same_scored = normalize_candidate({**same_unscored, "record_id": None, "score": 0.51, "score_status": "scored"})
    dismissed = normalize_candidate(
        {
            "candidate_id": "CAND-063",
            "title": "Would I Lie To You? Inference Time Alignment of Language Models using Direct Preference Heads",
            "authors": [],
            "year": None,
            "venue": "unknown",
            "abstract": "",
            "doi": "10.52202/079017-3022",
            "source": "crossref",
            "status": "dismissed",
            "decision": "dismissed",
        }
    )
    new_paper = normalize_candidate(
        {
            "candidate_id": "CAND-063",
            "title": "Amplitude-Projected Diffusion Posterior Sampling for Speech Phase Reconstruction with Zero-Shot Measurement Guidance",
            "authors": [],
            "year": None,
            "venue": "unknown",
            "abstract": "",
            "doi": "10.2139/ssrn.6989335",
            "source": "crossref",
        }
    )
    write_jsonl(tmp_path / "candidates.jsonl", [same_unscored, same_scored, dismissed, new_paper])

    result = repair_candidate_records(tmp_path, fix=True)
    records = load_candidates(tmp_path)

    assert result["removed_count"] == 1
    assert len(result["renumbered"]) == 1
    assert len(records) == 3
    assert len({record["record_id"] for record in records}) == 3
    assert len({record["candidate_id"] for record in records}) == 3
    merged = [record for record in records if record["title"].startswith("Zero-Shot")][0]
    assert merged["candidate_id"] == "CAND-043"
    assert merged["score_status"] == "scored"
    assert merged["score"] == 0.51
    assert [record for record in records if record["title"].startswith("Amplitude")][0]["candidate_id"] != "CAND-063"


def test_remove_candidate_by_record_id_targets_one_record(tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [
            {"title": "First", "authors": ["Ada"], "year": 2026, "venue": "ICLR", "abstract": "", "source": "fixture"},
            {"title": "Second", "authors": ["Grace"], "year": 2026, "venue": "arXiv", "abstract": "", "source": "fixture"},
        ],
    )
    target = load_candidates(tmp_path)[1]

    result = remove_candidate_by_record_id(tmp_path, target["record_id"])

    assert result["ok"] is True
    assert result["removed_candidate_id"] == "CAND-002"
    assert [record["candidate_id"] for record in load_candidates(tmp_path)] == ["CAND-001"]
