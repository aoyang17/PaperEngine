from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from urllib.parse import quote
import xml.etree.ElementTree as ET

import requests

from .candidates import get_candidate, update_candidate
from .util import compact_id, normalize_title, safe_int

SEMANTIC_GRAPH = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_FIELDS = "title,year,venue,authors,abstract,externalIds,openAccessPdf,url,citationCount"


def source_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": meta.get("title"),
        "year": meta.get("year"),
        "doi": meta.get("doi"),
        "arxiv_id": meta.get("arxiv_id"),
        "openalex_id": meta.get("openalex_id"),
        "semantic_scholar_id": meta.get("semantic_scholar_id"),
        "dblp_key": meta.get("dblp_key"),
        "url": meta.get("url"),
    }


def metadata_from_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = list(candidate.get("verified_sources") or [])
    source_meta = candidate.get("source_metadata")
    if not evidence and candidate.get("source") == "fixture":
        evidence = ["fixture"]
        if candidate.get("doi"):
            evidence.append(f"doi:{candidate['doi']}")
        if candidate.get("arxiv_id"):
            evidence.append(f"arxiv:{candidate['arxiv_id']}")
        source_meta = source_metadata(candidate)
    meta = {
        "title": candidate.get("title"),
        "authors": candidate.get("authors") or [],
        "year": candidate.get("year"),
        "venue": candidate.get("venue") or "unknown",
        "doi": candidate.get("doi"),
        "arxiv_id": candidate.get("arxiv_id"),
        "openalex_id": candidate.get("openalex_id"),
        "semantic_scholar_id": candidate.get("semantic_scholar_id"),
        "dblp_key": candidate.get("dblp_key"),
        "issn": candidate.get("issn"),
        "isbn": candidate.get("isbn"),
        "url": candidate.get("url"),
        "pdf_url": candidate.get("pdf_url"),
        "verified_sources": evidence,
    }
    if source_meta:
        meta["source_metadata"] = dict(source_meta)
    return meta


def _get_json(url: str, timeout: int = 20) -> dict[str, Any]:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "paper-engine-v2/0.1"})
    response.raise_for_status()
    return response.json()


def _clean_doi(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:")
    return text or None


def _extract_arxiv_id(*values: Any) -> str | None:
    for value in values:
        text = str(value or "")
        match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#\s]+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).removesuffix(".pdf")
        match = re.search(r"\barxiv[:\s]([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?|[A-Za-z.-]+/[0-9]{7}(?:v[0-9]+)?)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r"10\.48550/arxiv\.([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _arxiv_pdf_url(arxiv_id: str | None) -> str | None:
    if not arxiv_id:
        return None
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"


def _semantic_paper_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(payload.get("data"), list):
        for item in payload["data"]:
            if isinstance(item, dict):
                return item
        return None
    if payload.get("paperId") or payload.get("title"):
        return payload
    return None


def _years_compatible(left: Any, right: Any) -> bool:
    left_year = safe_int(left)
    right_year = safe_int(right)
    if left_year is None or right_year is None:
        return True
    return abs(left_year - right_year) <= 1


def _semantic_matches(record: dict[str, Any], paper: dict[str, Any]) -> bool:
    external = paper.get("externalIds") or {}
    if record.get("doi") and external.get("DOI"):
        return compact_id(_clean_doi(record.get("doi"))) == compact_id(_clean_doi(external.get("DOI")))
    if record.get("arxiv_id") and external.get("ArXiv"):
        return compact_id(record.get("arxiv_id")) == compact_id(external.get("ArXiv"))
    if record.get("semantic_scholar_id") and (paper.get("paperId") or external.get("CorpusId")):
        return compact_id(record.get("semantic_scholar_id")) in {
            compact_id(paper.get("paperId")),
            compact_id(external.get("CorpusId")),
        }
    if record.get("openalex_id") and external.get("OpenAlex"):
        return compact_id(record.get("openalex_id")) == compact_id(external.get("OpenAlex"))
    return (
        bool(record.get("title") and paper.get("title"))
        and normalize_title(str(record.get("title"))) == normalize_title(str(paper.get("title")))
        and _years_compatible(record.get("year"), paper.get("year"))
    )


def _semantic_lookup(record: dict[str, Any]) -> dict[str, Any] | None:
    seeds: list[str] = []
    if record.get("semantic_scholar_id"):
        seeds.append(str(record["semantic_scholar_id"]))
    if record.get("doi"):
        seeds.append(f"DOI:{_clean_doi(record['doi'])}")
    if record.get("arxiv_id"):
        seeds.append(f"ARXIV:{record['arxiv_id']}")
    for seed in seeds:
        payload = _get_json(f"{SEMANTIC_GRAPH}/paper/{quote(seed, safe=':')}?fields={quote(SEMANTIC_FIELDS)}")
        paper = _semantic_paper_from_payload(payload)
        if paper and _semantic_matches(record, paper):
            return paper
    if record.get("title"):
        payload = _get_json(f"{SEMANTIC_GRAPH}/paper/search/match?query={quote(str(record['title']))}&fields={quote(SEMANTIC_FIELDS)}")
        paper = _semantic_paper_from_payload(payload)
        if paper and _semantic_matches(record, paper):
            return paper
    return None


def _semantic_enrichment_from_paper(paper: dict[str, Any]) -> dict[str, Any]:
    external = paper.get("externalIds") or {}
    arxiv_id = external.get("ArXiv") or _extract_arxiv_id(paper.get("url"), external.get("DOI"))
    open_access_pdf = paper.get("openAccessPdf") or {}
    pdf_url = open_access_pdf.get("url") or _arxiv_pdf_url(arxiv_id)
    paper_id = paper.get("paperId")
    return {
        "abstract": paper.get("abstract") or "",
        "arxiv_id": arxiv_id,
        "pdf_url": pdf_url,
        "semantic_scholar_id": paper_id or external.get("CorpusId"),
        "openalex_id": external.get("OpenAlex"),
        "verified_sources": [paper.get("url") or f"{SEMANTIC_GRAPH}/paper/{paper_id}"],
        "source_metadata": {
            "title": paper.get("title"),
            "year": paper.get("year"),
            "doi": _clean_doi(external.get("DOI")),
            "arxiv_id": arxiv_id,
            "openalex_id": external.get("OpenAlex"),
            "semantic_scholar_id": paper_id or external.get("CorpusId"),
            "url": paper.get("url"),
        },
    }


def should_semantic_pdf_enrich(record: dict[str, Any]) -> bool:
    if record.get("pdf_url") or record.get("arxiv_id"):
        return False
    source = str(record.get("source") or "").lower()
    sources_seen = " ".join(str(item).lower() for item in (record.get("sources_seen") or []))
    return bool(record.get("openalex_id") or "openalex" in source or "openalex" in sources_seen)


def apply_semantic_pdf_enrichment(record: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    paper = _semantic_lookup(record)
    if not paper:
        return dict(record), False
    enrichment = _semantic_enrichment_from_paper(paper)
    updated = dict(record)
    changed = False
    for field in ["pdf_url", "arxiv_id", "semantic_scholar_id", "openalex_id", "abstract"]:
        if not updated.get(field) and enrichment.get(field):
            updated[field] = enrichment[field]
            changed = True
    if enrichment.get("verified_sources"):
        merged_sources = list(dict.fromkeys((updated.get("verified_sources") or []) + enrichment["verified_sources"]))
        if merged_sources != (updated.get("verified_sources") or []):
            updated["verified_sources"] = merged_sources
            changed = True
    source_meta = dict(updated.get("source_metadata") or {})
    for key, value in (enrichment.get("source_metadata") or {}).items():
        if not source_meta.get(key) and value:
            source_meta[key] = value
            changed = True
    if source_meta:
        updated["source_metadata"] = source_meta
    return updated, changed


def enrich_openalex_pdf_signals(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    enriched: list[dict[str, Any]] = []
    stats = {"semantic_pdf_enrichment_attempted": 0, "semantic_pdf_enrichment_updated": 0, "semantic_pdf_enrichment_failed": 0}
    for record in records:
        if not should_semantic_pdf_enrich(record):
            enriched.append(record)
            continue
        stats["semantic_pdf_enrichment_attempted"] += 1
        try:
            updated, changed = apply_semantic_pdf_enrichment(record)
        except Exception:
            stats["semantic_pdf_enrichment_failed"] += 1
            enriched.append(record)
            continue
        if changed:
            stats["semantic_pdf_enrichment_updated"] += 1
        enriched.append(updated)
    return enriched, stats


def enrich_by_doi(doi: str) -> dict[str, Any] | None:
    if not doi:
        return None
    data = _get_json(f"https://api.crossref.org/works/{doi}")
    message = data.get("message") or {}
    authors = []
    for author in message.get("author") or []:
        name = " ".join(part for part in [author.get("given"), author.get("family")] if part)
        if name:
            authors.append(name)
    year = None
    for key in ["published-print", "published-online", "created"]:
        parts = (((message.get(key) or {}).get("date-parts")) or [[]])[0]
        if parts:
            year = parts[0]
            break
    titles = message.get("title") or []
    venues = message.get("container-title") or []
    return {
        "title": titles[0] if titles else None,
        "authors": authors,
        "year": year,
        "venue": venues[0] if venues else "unknown",
        "doi": message.get("DOI") or doi,
        "url": message.get("URL"),
        "verified_sources": [f"https://api.crossref.org/works/{doi}"],
    }


def enrich_by_arxiv(arxiv_id: str) -> dict[str, Any] | None:
    if not arxiv_id:
        return None
    clean = arxiv_id.replace("arXiv:", "").strip()
    response = requests.get(f"https://export.arxiv.org/api/query?id_list={quote(clean)}", timeout=20)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        return None
    title = " ".join((entry.findtext("atom:title", default="", namespaces=ns) or "").split())
    authors = [author.findtext("atom:name", default="", namespaces=ns) for author in entry.findall("atom:author", ns)]
    published = entry.findtext("atom:published", default="", namespaces=ns)
    doi = entry.findtext("arxiv:doi", default="", namespaces=ns) or None
    return {
        "title": title,
        "authors": [name for name in authors if name],
        "year": int(published[:4]) if published[:4].isdigit() else None,
        "venue": "arXiv",
        "doi": doi,
        "arxiv_id": clean,
        "url": f"https://arxiv.org/abs/{clean}",
        "pdf_url": f"https://arxiv.org/pdf/{clean}.pdf",
        "verified_sources": [f"https://export.arxiv.org/api/query?id_list={clean}"],
    }


def enrich_by_openalex_title(title: str) -> dict[str, Any] | None:
    if not title:
        return None
    data = _get_json(f"https://api.openalex.org/works?search={quote(title)}&per-page=1")
    results = data.get("results") or []
    if not results:
        return None
    item = results[0]
    authors = []
    for authorship in item.get("authorships") or []:
        author = authorship.get("author") or {}
        if author.get("display_name"):
            authors.append(author["display_name"])
    venue = ((item.get("primary_location") or {}).get("source") or {}).get("display_name") or "unknown"
    source = ((item.get("primary_location") or {}).get("source") or {})
    openalex_id = item.get("id")
    issn_values = source.get("issn") or []
    if source.get("issn_l") and source["issn_l"] not in issn_values:
        issn_values = [source["issn_l"], *issn_values]
    return {
        "title": item.get("title"),
        "authors": authors,
        "year": item.get("publication_year"),
        "venue": venue,
        "doi": (item.get("doi") or "").replace("https://doi.org/", "") or None,
        "openalex_id": openalex_id,
        "issn": ";".join(str(value) for value in issn_values if value) or None,
        "url": openalex_id,
        "verified_sources": [openalex_id or "https://api.openalex.org/works"],
    }


def enrich_candidate(root: str | Path, candidate_id: str, live: bool = False) -> dict[str, Any]:
    candidate = get_candidate(root, candidate_id)
    meta = metadata_from_candidate(candidate)
    if live and candidate.get("doi"):
        try:
            enriched = enrich_by_doi(candidate["doi"])
        except Exception as exc:  # live metadata errors should be explicit, not fatal.
            enriched = {"error": str(exc)}
    elif live and candidate.get("arxiv_id"):
        try:
            enriched = enrich_by_arxiv(candidate["arxiv_id"])
        except Exception as exc:
            enriched = {"error": str(exc)}
    elif live and candidate.get("title"):
        try:
            enriched = enrich_by_openalex_title(candidate["title"])
        except Exception as exc:
            enriched = {"error": str(exc)}
    else:
        enriched = None
    if live:
        if enriched and "error" not in enriched:
            meta.update({k: v for k, v in enriched.items() if v not in (None, [], "")})
            meta["verified_sources"] = sorted(set((meta.get("verified_sources") or []) + (enriched.get("verified_sources") or [])))
            if should_semantic_pdf_enrich(meta):
                try:
                    meta, _ = apply_semantic_pdf_enrichment(meta)
                except Exception:
                    pass
            meta["source_metadata"] = source_metadata(meta)
    update_candidate(
        root,
        candidate_id,
        title=meta.get("title") or "",
        authors=meta.get("authors") or [],
        year=meta.get("year"),
        venue=meta.get("venue") or "unknown",
        doi=meta.get("doi"),
        arxiv_id=meta.get("arxiv_id"),
        openalex_id=meta.get("openalex_id"),
        semantic_scholar_id=meta.get("semantic_scholar_id"),
        dblp_key=meta.get("dblp_key"),
        issn=meta.get("issn"),
        isbn=meta.get("isbn"),
        url=meta.get("url"),
        pdf_url=meta.get("pdf_url"),
        verified_sources=meta.get("verified_sources") or [],
        source_metadata=meta.get("source_metadata"),
    )
    return meta
