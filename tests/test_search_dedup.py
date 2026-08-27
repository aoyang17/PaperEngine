from __future__ import annotations

import json

from conftest import fixture_path
from paper_engine.candidates import load_candidates, normalize_candidate
from paper_engine.search import collect, resolve_paper, run_backend_search
from paper_engine.topic import init_topic
from paper_engine.util import write_jsonl


def test_fixture_collect_inserts_and_repeated_collect_dedups(tmp_path):
    init_topic(tmp_path, title="AI scientist")
    first = collect(tmp_path, fixture=fixture_path("search_results.json"), target_new=5)
    second = collect(tmp_path, fixture=fixture_path("search_results.json"), target_new=5)

    assert first["added"] == 1
    assert second["added"] == 0
    assert len(load_candidates(tmp_path)) == 1
    candidate = load_candidates(tmp_path)[0]
    assert candidate["score"] == 0.0
    assert candidate["score_status"] == "unscored"


def test_collect_allocates_candidate_id_from_max_existing_id_not_count(tmp_path):
    init_topic(tmp_path, title="AI scientist")
    legacy = normalize_candidate(
        {
            "candidate_id": "CAND-010",
            "title": "Legacy Paper",
            "authors": ["Ada Example"],
            "year": 2025,
            "venue": "arXiv",
            "abstract": "",
            "source": "fixture",
        }
    )
    write_jsonl(tmp_path / "candidates.jsonl", [legacy])

    result = collect(tmp_path, fixture=fixture_path("search_results.json"), target_new=5)
    candidates = load_candidates(tmp_path)

    assert result["added"] == 1
    assert [candidate["candidate_id"] for candidate in candidates] == ["CAND-010", "CAND-011"]


def test_score_threshold_filters_candidates(tmp_path):
    init_topic(tmp_path)
    result = collect(tmp_path, fixture=fixture_path("search_results.json"), score_threshold=99)
    assert result["added"] == 1
    assert load_candidates(tmp_path)[0]["score_status"] == "unscored"


def test_invalid_search_result_is_skipped(tmp_path):
    init_topic(tmp_path)
    fixture = tmp_path / "bad_results.json"
    fixture.write_text('{"results": [{"authors": [], "year": 2026, "source": "fixture"}]}', encoding="utf-8")

    result = collect(tmp_path, fixture=fixture)
    assert result["added"] == 0
    assert result["skipped_invalid"] == 1


def test_collect_preserves_venue_from_backend_extra(tmp_path):
    init_topic(tmp_path)
    fixture = tmp_path / "extra_venue_results.json"
    fixture.write_text(
        '{"results": [{"title": "Venue Paper", "authors": ["Ada Example"], '
        '"year": 2026, "abstract": "", "doi": "10.1234/venue.paper", '
        '"source": "unpaywall", "extra": {"journal_name": "Science Robotics"}}]}',
        encoding="utf-8",
    )

    result = collect(tmp_path, fixture=fixture)

    assert result["added"] == 1
    assert load_candidates(tmp_path)[0]["venue"] == "Science Robotics"


def test_existing_library_paper_is_skipped(tmp_path):
    init_topic(tmp_path)
    (tmp_path / "library.bib").write_text(
        "@article{Example2026A,\n"
        "  author = {Ada Example},\n"
        "  title = {A Paper},\n"
        "  year = {2026},\n"
        "  doi = {10.1234/example.paper},\n"
        "}\n",
        encoding="utf-8",
    )

    result = collect(tmp_path, fixture=fixture_path("search_results.json"))
    assert result["added"] == 0
    assert load_candidates(tmp_path) == []


def test_collect_dedups_against_large_library_without_user_context(tmp_path):
    init_topic(tmp_path)
    entries = []
    for index in range(200):
        doi = "10.1234/example.paper" if index == 137 else f"10.1234/other.{index}"
        entries.append(
            "@article{Key%03d,\n"
            "  author = {Ada Example},\n"
            "  title = {Large Library Paper %03d},\n"
            "  year = {2026},\n"
            "  doi = {%s},\n"
            "}\n" % (index, index, doi)
        )
    (tmp_path / "library.bib").write_text("\n".join(entries), encoding="utf-8")

    result = collect(tmp_path, fixture=fixture_path("search_results.json"))

    assert result["added"] == 0
    assert load_candidates(tmp_path) == []


def test_collect_enriches_openalex_results_with_semantic_pdf(monkeypatch, tmp_path):
    init_topic(tmp_path)
    fixture = tmp_path / "openalex_results.json"
    fixture.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "title": "OpenAlex Paper",
                        "authors": ["Ada Example"],
                        "year": 2026,
                        "venue": "OpenAlex Venue",
                        "abstract": "",
                        "source": "openalex",
                        "openalex_id": "W123",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "paper_engine.metadata._get_json",
        lambda url: {
            "paperId": "SEM-123",
            "title": "OpenAlex Paper",
            "year": 2026,
            "externalIds": {"ArXiv": "2601.12345", "OpenAlex": "W123"},
            "openAccessPdf": {"url": "https://arxiv.org/pdf/2601.12345.pdf"},
            "url": "https://www.semanticscholar.org/paper/SEM-123",
        },
    )

    result = collect(tmp_path, fixture=fixture)
    candidate = load_candidates(tmp_path)[0]

    assert result["semantic_pdf_enrichment_attempted"] == 1
    assert result["semantic_pdf_enrichment_updated"] == 1
    assert result["semantic_pdf_enrichment_failed"] == 0
    assert candidate["pdf_url"] == "https://arxiv.org/pdf/2601.12345.pdf"
    assert candidate["arxiv_id"] == "2601.12345"
    assert candidate["semantic_scholar_id"] == "SEM-123"


def test_collect_survives_semantic_pdf_enrichment_failure(monkeypatch, tmp_path):
    init_topic(tmp_path)
    fixture = tmp_path / "openalex_results.json"
    fixture.write_text(
        '{"results": [{"title": "OpenAlex Paper", "authors": ["Ada Example"], '
        '"year": 2026, "venue": "OpenAlex Venue", "abstract": "", '
        '"source": "openalex", "openalex_id": "W123"}]}',
        encoding="utf-8",
    )

    def raise_semantic(url):
        raise RuntimeError("rate limited")

    monkeypatch.setattr("paper_engine.metadata._get_json", raise_semantic)

    result = collect(tmp_path, fixture=fixture)
    candidate = load_candidates(tmp_path)[0]

    assert result["added"] == 1
    assert result["semantic_pdf_enrichment_attempted"] == 1
    assert result["semantic_pdf_enrichment_failed"] == 1
    assert candidate.get("pdf_url") is None


def test_resolve_paper_returns_semantic_pdf_enriched_candidate(monkeypatch, tmp_path):
    init_topic(tmp_path)
    monkeypatch.setattr(
        "paper_engine.search.run_backend_search",
        lambda query, max_results=5: [
            {
                "title": "OpenAlex Paper",
                "authors": ["Ada Example"],
                "year": 2026,
                "venue": "OpenAlex Venue",
                "source": "openalex",
                "openalex_id": "W123",
                "pdf_url": "https://arxiv.org/pdf/2601.12345.pdf",
                "arxiv_id": "2601.12345",
                "semantic_scholar_id": "SEM-123",
            }
        ],
    )

    result = resolve_paper(tmp_path, "OpenAlex Paper")

    assert result["ok"] is True
    assert result["candidate"]["pdf_url"] == "https://arxiv.org/pdf/2601.12345.pdf"
    assert result["candidate"]["arxiv_id"] == "2601.12345"


def test_backend_search_enriches_openalex_preview(monkeypatch):
    class Proc:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "results": [
                    {
                        "title": "OpenAlex Paper",
                        "authors": ["Ada Example"],
                        "year": 2026,
                        "venue": "OpenAlex Venue",
                        "source": "openalex",
                        "openalex_id": "W123",
                    }
                ]
            }
        )

    monkeypatch.setattr("paper_engine.search.backend_command", lambda: ["paper-search"])
    monkeypatch.setattr("paper_engine.search.subprocess.run", lambda *args, **kwargs: Proc())
    monkeypatch.setattr(
        "paper_engine.metadata._get_json",
        lambda url: {
            "paperId": "SEM-123",
            "title": "OpenAlex Paper",
            "year": 2026,
            "externalIds": {"ArXiv": "2601.12345", "OpenAlex": "W123"},
            "openAccessPdf": {"url": "https://arxiv.org/pdf/2601.12345.pdf"},
            "url": "https://www.semanticscholar.org/paper/SEM-123",
        },
    )

    records = run_backend_search("OpenAlex Paper")

    assert records[0]["pdf_url"] == "https://arxiv.org/pdf/2601.12345.pdf"
    assert records[0]["semantic_scholar_id"] == "SEM-123"
