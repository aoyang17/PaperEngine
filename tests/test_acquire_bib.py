from __future__ import annotations

import pytest

from conftest import fixture_path
from battery_lit.acquire import acquire_pdf
from battery_lit.bib import promote_candidate
from battery_lit.candidates import append_candidates, load_candidates
from battery_lit.citation_guard import check_bib
from battery_lit.metadata import enrich_candidate
from battery_lit.search import collect
from battery_lit.topic import init_topic


def test_manual_acquire_promote_and_repeated_promote(tmp_path):
    init_topic(tmp_path)
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquired = acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promoted = promote_candidate(tmp_path, "CAND-001")
    repeated = promote_candidate(tmp_path, "CAND-001")

    assert acquired["ok"] is True
    assert promoted["bibkey"] == "Example2026A"
    assert repeated["status"] == "already_promoted"
    assert (tmp_path / "papers" / "Example2026A" / "paper.pdf").exists()
    assert check_bib(tmp_path)["ok"] is True
    assert load_candidates(tmp_path)[0]["status"] == "in_library"


def test_repeated_acquire_skips_existing_pdf(tmp_path):
    init_topic(tmp_path)
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    first = acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    second = acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    assert first["status"] == "downloaded"
    assert second["status"] == "skipped_existing"


def test_acquire_skips_existing_promoted_pdf(tmp_path):
    init_topic(tmp_path)
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")
    result = acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    assert result["status"] == "skipped_existing"
    assert not (tmp_path / "papers" / "_incoming" / "CAND-001.pdf").exists()


def test_promote_requires_work_level_identifier_not_issn_only(tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [
            {
                "title": "No Paper Identifier",
                "authors": ["Ada Example"],
                "year": 2026,
                "venue": "Journal",
                "abstract": "",
                "source": "fixture",
                "issn": "1234-5678",
                "verified_sources": ["issn:1234-5678"],
                "source_metadata": {"title": "No Paper Identifier", "year": 2026},
            }
        ],
    )
    with pytest.raises(Exception, match="verified work-level source"):
        promote_candidate(tmp_path, "CAND-001")


def test_manual_pdf_promote_allows_openalex_verified_no_doi(tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [
            {
                "title": "Proceedings Paper Without DOI",
                "authors": ["Ada Example", "Ben Researcher"],
                "year": 2021,
                "venue": "Reliable Proceedings",
                "abstract": "",
                "source": "openalex",
                "openalex_id": "https://openalex.org/W123456789",
                "issn": "1234-5678",
                "url": "https://openalex.org/W123456789",
                "verified_sources": ["https://openalex.org/W123456789"],
                "source_metadata": {
                    "title": "Proceedings Paper Without DOI",
                    "year": 2021,
                    "openalex_id": "https://openalex.org/W123456789",
                    "url": "https://openalex.org/W123456789",
                },
            }
        ],
    )

    acquired = acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promoted = promote_candidate(tmp_path, "CAND-001")
    bib = (tmp_path / "library.bib").read_text(encoding="utf-8")
    metadata = (tmp_path / "papers" / promoted["bibkey"] / "metadata.yml").read_text(encoding="utf-8")

    assert acquired["status"] == "downloaded"
    assert promoted["status"] == "promoted"
    assert load_candidates(tmp_path)[0]["status"] == "in_library"
    assert (tmp_path / "papers" / promoted["bibkey"] / "paper.pdf").exists()
    assert "openalexId = {https://openalex.org/W123456789}" in bib
    assert "issn = {1234-5678}" in bib
    assert "batteryMetadataStatus = {verified_no_doi}" in bib
    assert "batteryVerifiedSource = {https://openalex.org/W123456789}" in bib
    assert "openalex_id: https://openalex.org/W123456789" in metadata
    assert check_bib(tmp_path)["ok"] is True


def test_promote_uses_enriched_canonical_metadata(monkeypatch, tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [
            {
                "title": "Old Title",
                "authors": ["Old Author"],
                "year": 2020,
                "venue": "unknown",
                "abstract": "",
                "doi": "10.1/canonical",
                "source": "fixture",
            }
        ],
    )
    monkeypatch.setattr(
        "battery_lit.metadata.enrich_by_doi",
        lambda doi: {
            "title": "Canonical Title",
            "authors": ["Ada Example"],
            "year": 2026,
            "venue": "ICLR",
            "doi": doi,
            "verified_sources": ["crossref"],
        },
    )

    enrich_candidate(tmp_path, "CAND-001", live=True)
    promoted = promote_candidate(tmp_path, "CAND-001")
    bib = (tmp_path / "library.bib").read_text(encoding="utf-8")
    metadata = (tmp_path / "papers" / promoted["bibkey"] / "metadata.yml").read_text(encoding="utf-8")

    assert promoted["bibkey"] == "Example2026Canonical"
    assert "Canonical Title" in bib
    assert "Old Title" not in bib
    assert "Ada Example" in metadata
