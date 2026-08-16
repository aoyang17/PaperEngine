from __future__ import annotations

from battery_lit.citation_guard import CitationGuardError, check_bib, guard_metadata
from battery_lit.topic import init_topic


def test_guard_metadata_blocks_unverified_identifier():
    try:
        guard_metadata({"title": "Paper", "authors": ["A B"], "year": 2026, "venue": "unknown"})
    except CitationGuardError as exc:
        assert "verified work-level source" in str(exc)
    else:
        raise AssertionError("guard_metadata should fail")


def test_guard_metadata_accepts_openalex_work_id_without_doi_or_arxiv():
    guard_metadata(
        {
            "title": "Paper",
            "authors": ["A B"],
            "year": 2026,
            "venue": "Journal",
            "openalex_id": "https://openalex.org/W123",
            "issn": "1234-5678",
            "verified_sources": ["https://openalex.org/W123"],
            "source_metadata": {
                "title": "Paper",
                "year": 2026,
                "openalex_id": "https://openalex.org/W123",
            },
        }
    )


def test_guard_metadata_rejects_issn_without_work_identifier():
    try:
        guard_metadata(
            {
                "title": "Paper",
                "authors": ["A B"],
                "year": 2026,
                "venue": "Journal",
                "issn": "1234-5678",
                "verified_sources": ["issn:1234-5678"],
                "source_metadata": {"title": "Paper", "year": 2026},
            }
        )
    except CitationGuardError as exc:
        assert "verified work-level source" in str(exc)
    else:
        raise AssertionError("guard_metadata should fail")


def test_guard_metadata_requires_verified_sources():
    try:
        guard_metadata({"title": "Paper", "authors": ["A B"], "year": 2026, "venue": "unknown", "doi": "10.1/x"})
    except CitationGuardError as exc:
        assert "verified metadata sources" in str(exc)
    else:
        raise AssertionError("guard_metadata should fail")


def test_guard_metadata_blocks_title_year_mismatch():
    base = {
        "title": "Wrong Title",
        "authors": ["A B"],
        "year": 2025,
        "venue": "unknown",
        "doi": "10.1/x",
        "verified_sources": ["crossref"],
        "source_metadata": {"title": "Canonical Title", "year": 2026, "doi": "10.1/x"},
    }
    try:
        guard_metadata(base)
    except CitationGuardError as exc:
        assert "title mismatch" in str(exc)
    else:
        raise AssertionError("guard_metadata should fail")

    base["title"] = "Canonical Title"
    try:
        guard_metadata(base)
    except CitationGuardError as exc:
        assert "year mismatch" in str(exc)
    else:
        raise AssertionError("guard_metadata should fail")


def test_bib_check_catches_missing_relative_file(tmp_path):
    init_topic(tmp_path)
    (tmp_path / "library.bib").write_text(
        "@article{Bad2026Paper,\n"
        "  author = {Ada Example},\n"
        "  title = {Paper},\n"
        "  year = {2026},\n"
        "  doi = {10.1/bad},\n"
        "  file = {/tmp/paper.pdf},\n"
        "}\n",
        encoding="utf-8",
    )
    result = check_bib(tmp_path)
    assert result["ok"] is False
    assert "file path" in result["errors"][0]
