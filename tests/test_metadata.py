from __future__ import annotations

from paper_engine.candidates import append_candidates, get_candidate
from paper_engine.metadata import apply_semantic_pdf_enrichment, enrich_candidate, metadata_from_candidate
from paper_engine.topic import init_topic


def test_metadata_from_candidate_preserves_unknown_venue(tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [{"title": "Paper", "authors": ["Ada Example"], "year": 2026, "venue": "", "abstract": "", "doi": "10.1/x", "source": "fixture"}],
    )
    meta = metadata_from_candidate(get_candidate(tmp_path, "CAND-001"))
    assert meta["venue"] == "unknown"
    assert "doi:10.1/x" in meta["verified_sources"]


def test_doi_enrichment_updates_candidate(monkeypatch, tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [{"title": "Old", "authors": ["A B"], "year": 2020, "venue": "unknown", "abstract": "", "doi": "10.1/new", "source": "fixture"}],
    )

    def fake_enrich_by_doi(doi):
        return {"title": "New", "authors": ["Ada Example"], "year": 2026, "venue": "ICLR", "doi": doi, "verified_sources": ["crossref"]}

    monkeypatch.setattr("paper_engine.metadata.enrich_by_doi", fake_enrich_by_doi)
    meta = enrich_candidate(tmp_path, "CAND-001", live=True)
    assert meta["venue"] == "ICLR"
    candidate = get_candidate(tmp_path, "CAND-001")
    assert candidate["title"] == "New"
    assert candidate["authors"] == ["Ada Example"]
    assert candidate["year"] == 2026
    assert candidate["venue"] == "ICLR"
    assert candidate["verified_sources"] == ["crossref"]
    assert candidate["source_metadata"]["title"] == "New"
    assert candidate["source_metadata"]["year"] == 2026


def test_arxiv_enrichment_path(monkeypatch, tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [{"title": "Old", "authors": ["A B"], "year": 2020, "venue": "unknown", "abstract": "", "arxiv_id": "2601.00001", "source": "fixture"}],
    )

    monkeypatch.setattr(
        "paper_engine.metadata.enrich_by_arxiv",
        lambda arxiv_id: {"title": "Arxiv Paper", "authors": ["Ada Example"], "year": 2026, "venue": "arXiv", "arxiv_id": arxiv_id, "pdf_url": "https://arxiv.org/pdf/2601.00001.pdf", "verified_sources": ["arxiv"]},
    )
    meta = enrich_candidate(tmp_path, "CAND-001", live=True)
    assert meta["venue"] == "arXiv"
    assert meta["pdf_url"].endswith(".pdf")
    candidate = get_candidate(tmp_path, "CAND-001")
    assert candidate["title"] == "Arxiv Paper"
    assert candidate["source_metadata"]["arxiv_id"] == "2601.00001"


def test_title_enrichment_path_keeps_unknown_when_no_match(monkeypatch, tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [{"title": "Title Only", "authors": ["A B"], "year": 2020, "venue": "unknown", "abstract": "", "source": "fixture"}],
    )
    monkeypatch.setattr("paper_engine.metadata.enrich_by_openalex_title", lambda title: None)
    meta = enrich_candidate(tmp_path, "CAND-001", live=True)
    assert meta["venue"] == "unknown"


def test_semantic_pdf_enrichment_adds_pdf_and_arxiv_for_openalex(monkeypatch):
    def fake_get_json(url):
        assert "api.semanticscholar.org" in url
        return {
            "paperId": "SEM-123",
            "title": "OpenAlex Paper",
            "year": 2026,
            "venue": "arXiv.org",
            "abstract": "Semantic Scholar abstract.",
            "url": "https://www.semanticscholar.org/paper/SEM-123",
            "externalIds": {"ArXiv": "2601.12345", "OpenAlex": "W123"},
            "openAccessPdf": {"url": "https://arxiv.org/pdf/2601.12345.pdf"},
        }

    monkeypatch.setattr("paper_engine.metadata._get_json", fake_get_json)
    enriched, changed = apply_semantic_pdf_enrichment(
        {
            "title": "OpenAlex Paper",
            "authors": ["Ada"],
            "year": 2026,
            "source": "openalex",
            "openalex_id": "W123",
        }
    )

    assert changed is True
    assert enriched["pdf_url"] == "https://arxiv.org/pdf/2601.12345.pdf"
    assert enriched["arxiv_id"] == "2601.12345"
    assert enriched["semantic_scholar_id"] == "SEM-123"
    assert enriched["abstract"] == "Semantic Scholar abstract."


def test_semantic_pdf_enrichment_rejects_title_year_mismatch(monkeypatch):
    monkeypatch.setattr(
        "paper_engine.metadata._get_json",
        lambda url: {
            "paperId": "SEM-999",
            "title": "Different Paper",
            "year": 2018,
            "externalIds": {},
            "openAccessPdf": {"url": "https://example.org/wrong.pdf"},
        },
    )

    enriched, changed = apply_semantic_pdf_enrichment({"title": "OpenAlex Paper", "year": 2026, "source": "openalex", "openalex_id": "W123"})

    assert changed is False
    assert "pdf_url" not in enriched


def test_openalex_title_enrichment_also_adds_semantic_pdf(monkeypatch, tmp_path):
    init_topic(tmp_path)
    append_candidates(
        tmp_path,
        [{"title": "Title Only", "authors": ["A B"], "year": 2020, "venue": "unknown", "abstract": "", "source": "fixture"}],
    )
    monkeypatch.setattr(
        "paper_engine.metadata.enrich_by_openalex_title",
        lambda title: {
            "title": "Canonical OpenAlex Paper",
            "authors": ["Ada Example"],
            "year": 2026,
            "venue": "OpenAlex Venue",
            "openalex_id": "W123",
            "url": "https://openalex.org/W123",
            "verified_sources": ["https://openalex.org/W123"],
        },
    )
    monkeypatch.setattr(
        "paper_engine.metadata._get_json",
        lambda url: {
            "paperId": "SEM-123",
            "title": "Canonical OpenAlex Paper",
            "year": 2026,
            "externalIds": {"ArXiv": "2601.12345", "OpenAlex": "W123"},
            "openAccessPdf": {"url": "https://arxiv.org/pdf/2601.12345.pdf"},
            "url": "https://www.semanticscholar.org/paper/SEM-123",
        },
    )

    meta = enrich_candidate(tmp_path, "CAND-001", live=True)
    candidate = get_candidate(tmp_path, "CAND-001")

    assert meta["pdf_url"] == "https://arxiv.org/pdf/2601.12345.pdf"
    assert candidate["pdf_url"] == "https://arxiv.org/pdf/2601.12345.pdf"
    assert candidate["semantic_scholar_id"] == "SEM-123"
