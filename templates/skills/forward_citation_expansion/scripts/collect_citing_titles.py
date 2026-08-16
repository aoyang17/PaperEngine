#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


USER_AGENT = "battery-paper-forward-citation/0.1"
OPENALEX_WORKS = "https://api.openalex.org/works"
SEMANTIC_GRAPH = "https://api.semanticscholar.org/graph/v1"


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object from {url}")
    return payload


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fixture must contain a JSON object: {path}")
    return data


def _norm_title(value: Any) -> str:
    text = str(value or "").casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _compact_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.removeprefix("https://doi.org/")
    text = text.removeprefix("http://doi.org/")
    text = text.removeprefix("doi:")
    text = text.removeprefix("arxiv:")
    return text.removesuffix(".pdf")


def _doi(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return text or None


def _looks_like_pdf(value: Any) -> bool:
    text = str(value or "").lower()
    return text.endswith(".pdf") or "/pdf/" in text or "download" in text and "pdf" in text


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


def _author_names_from_openalex(authorships: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(authorships, list):
        return names
    for item in authorships:
        if isinstance(item, dict):
            name = ((item.get("author") or {}).get("display_name") or "").strip()
            if name:
                names.append(name)
    return names


def _author_names_from_semantic(authors: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(authors, list):
        return names
    for item in authors:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            names.append(name)
    return names


def _abstract_from_openalex(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    words: list[tuple[int, str]] = []
    for word, positions in index.items():
        if isinstance(positions, list):
            for position in positions:
                if isinstance(position, int):
                    words.append((position, str(word)))
    return " ".join(word for _, word in sorted(words))


def _venue_from_openalex(item: dict[str, Any]) -> str:
    for loc_key in ["primary_location", "best_oa_location"]:
        loc = item.get(loc_key) or {}
        source = loc.get("source") or {}
        name = source.get("display_name") if isinstance(source, dict) else None
        if name:
            return str(name)
    return str(item.get("host_venue") or item.get("type") or "unknown")


def _pdf_from_openalex(item: dict[str, Any]) -> str | None:
    for key in ["primary_location", "best_oa_location"]:
        location = item.get(key) or {}
        if location.get("pdf_url"):
            return str(location["pdf_url"])
    for location in item.get("locations") or []:
        if isinstance(location, dict) and location.get("pdf_url"):
            return str(location["pdf_url"])
    oa_url = (item.get("open_access") or {}).get("oa_url")
    if _looks_like_pdf(oa_url):
        return str(oa_url)
    return None


def _openalex_id(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text.rsplit("/", 1)[-1]


def _openalex_record(item: dict[str, Any]) -> dict[str, Any]:
    doi = _doi(item.get("doi"))
    arxiv_id = _extract_arxiv_id(doi, item.get("id"), (item.get("primary_location") or {}).get("landing_page_url"))
    pdf_url = _pdf_from_openalex(item) or _arxiv_pdf_url(arxiv_id)
    title = item.get("display_name") or item.get("title") or ""
    return {
        "title": title,
        "authors": _author_names_from_openalex(item.get("authorships")),
        "year": item.get("publication_year"),
        "venue": _venue_from_openalex(item),
        "abstract": _abstract_from_openalex(item.get("abstract_inverted_index")),
        "doi": doi,
        "arxiv_id": arxiv_id,
        "openalex_id": _openalex_id(item.get("id")),
        "semantic_scholar_id": None,
        "url": item.get("id"),
        "pdf_url": pdf_url,
        "source": "forward-citation",
        "citation_count": item.get("cited_by_count"),
        "forward_sources": ["openalex"],
        "verified_sources": [str(item.get("id"))] if item.get("id") else ["openalex"],
        "source_metadata": {
            "title": title,
            "year": item.get("publication_year"),
            "doi": doi,
            "arxiv_id": arxiv_id,
            "openalex_id": _openalex_id(item.get("id")),
            "url": item.get("id"),
        },
    }


def _semantic_record(item: dict[str, Any]) -> dict[str, Any]:
    paper = item.get("citingPaper") if isinstance(item.get("citingPaper"), dict) else item
    external = paper.get("externalIds") or {}
    arxiv_id = external.get("ArXiv") or _extract_arxiv_id(paper.get("url"), external.get("DOI"))
    open_access_pdf = paper.get("openAccessPdf") or {}
    pdf_url = open_access_pdf.get("url") or _arxiv_pdf_url(arxiv_id)
    title = paper.get("title") or ""
    return {
        "title": title,
        "authors": _author_names_from_semantic(paper.get("authors")),
        "year": paper.get("year"),
        "venue": paper.get("venue") or "unknown",
        "abstract": paper.get("abstract") or "",
        "doi": _doi(external.get("DOI")),
        "arxiv_id": arxiv_id,
        "openalex_id": external.get("OpenAlex"),
        "semantic_scholar_id": paper.get("paperId") or external.get("CorpusId"),
        "url": paper.get("url"),
        "pdf_url": pdf_url,
        "source": "forward-citation",
        "citation_count": paper.get("citationCount"),
        "forward_sources": ["semantic"],
        "verified_sources": [paper.get("url") or f"semantic:{paper.get('paperId')}"],
        "source_metadata": {
            "title": title,
            "year": paper.get("year"),
            "doi": _doi(external.get("DOI")),
            "arxiv_id": arxiv_id,
            "openalex_id": external.get("OpenAlex"),
            "semantic_scholar_id": paper.get("paperId") or external.get("CorpusId"),
            "url": paper.get("url"),
        },
    }


def _merge_key(record: dict[str, Any]) -> tuple[str, str]:
    for key in ["doi", "arxiv_id", "openalex_id", "semantic_scholar_id"]:
        if record.get(key):
            return key, _compact_id(record[key])
    return "title", _norm_title(record.get("title"))


def _merge_record(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key in ["title", "year", "venue", "doi", "arxiv_id", "openalex_id", "semantic_scholar_id", "url", "pdf_url"]:
        if not merged.get(key) and right.get(key):
            merged[key] = right[key]
    if len(str(right.get("abstract") or "")) > len(str(merged.get("abstract") or "")):
        merged["abstract"] = right.get("abstract")
    if len(right.get("authors") or []) > len(merged.get("authors") or []):
        merged["authors"] = right.get("authors")
    sources = list(dict.fromkeys((merged.get("forward_sources") or []) + (right.get("forward_sources") or [])))
    merged["forward_sources"] = sources
    evidence = list(dict.fromkeys((merged.get("verified_sources") or []) + (right.get("verified_sources") or [])))
    merged["verified_sources"] = evidence
    source_meta = dict(merged.get("source_metadata") or {})
    for key, value in (right.get("source_metadata") or {}).items():
        if not source_meta.get(key) and value:
            source_meta[key] = value
    merged["source_metadata"] = source_meta
    if not merged.get("pdf_url") and merged.get("arxiv_id"):
        merged["pdf_url"] = _arxiv_pdf_url(str(merged["arxiv_id"]))
    return merged


def _dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        if not _norm_title(record.get("title")):
            continue
        key = _merge_key(record)
        if key in by_key:
            by_key[key] = _merge_record(by_key[key], record)
        else:
            by_key[key] = record
    return list(by_key.values())


def _load_openalex_records(path: Path | None) -> tuple[list[dict[str, Any]], int | None]:
    fixture = _load_json(path)
    if fixture is None:
        return [], None
    results = fixture.get("results") if isinstance(fixture.get("results"), list) else fixture.get("openalex")
    if not isinstance(results, list):
        results = []
    count = (fixture.get("meta") or {}).get("count")
    return [_openalex_record(item) for item in results if isinstance(item, dict)], count


def _load_semantic_records(path: Path | None) -> tuple[list[dict[str, Any]], int | None]:
    fixture = _load_json(path)
    if fixture is None:
        return [], None
    results = fixture.get("data") if isinstance(fixture.get("data"), list) else fixture.get("semantic")
    if not isinstance(results, list):
        results = []
    return [_semantic_record(item) for item in results if isinstance(item, dict)], len(results)


def _resolve_openalex_seed(args: argparse.Namespace) -> str | None:
    if args.seed_openalex:
        return str(args.seed_openalex).rsplit("/", 1)[-1]
    if args.seed_doi:
        query = "doi:" + _doi(args.seed_doi)
        data = _get_json(f"{OPENALEX_WORKS}/{urllib.parse.quote(query, safe=':')}")
        return _openalex_id(data.get("id"))
    if args.seed_title:
        params = urllib.parse.urlencode({"search": args.seed_title, "per_page": 1, "select": "id,display_name"})
        data = _get_json(f"{OPENALEX_WORKS}?{params}")
        results = data.get("results") or []
        if results:
            return _openalex_id(results[0].get("id"))
    return None


def _fetch_openalex(args: argparse.Namespace) -> tuple[list[dict[str, Any]], int | None]:
    seed_id = _resolve_openalex_seed(args)
    if not seed_id:
        return [], None
    fields = ",".join(
        [
            "id",
            "doi",
            "display_name",
            "publication_year",
            "cited_by_count",
            "abstract_inverted_index",
            "authorships",
            "primary_location",
            "best_oa_location",
            "locations",
            "open_access",
        ]
    )
    params = urllib.parse.urlencode(
        {
            "filter": f"cites:{seed_id}",
            "select": fields,
            "sort": "publication_year:desc",
            "per_page": min(args.limit, 200),
        }
    )
    data = _get_json(f"{OPENALEX_WORKS}?{params}")
    results = data.get("results") or []
    return [_openalex_record(item) for item in results if isinstance(item, dict)], (data.get("meta") or {}).get("count")


def _semantic_seed(args: argparse.Namespace) -> str | None:
    if args.seed_semantic:
        return args.seed_semantic
    if args.seed_doi:
        return "DOI:" + str(args.seed_doi)
    if args.seed_arxiv:
        return "ARXIV:" + str(args.seed_arxiv)
    return None


def _fetch_semantic(args: argparse.Namespace) -> tuple[list[dict[str, Any]], int | None]:
    seed = _semantic_seed(args)
    if not seed:
        return [], None
    fields = "title,year,venue,authors,abstract,externalIds,citationCount,openAccessPdf,url"
    params = urllib.parse.urlencode({"fields": fields, "limit": min(args.limit, 100)})
    url = f"{SEMANTIC_GRAPH}/paper/{urllib.parse.quote(seed, safe=':')}/citations?{params}"
    data = _get_json(url)
    results = data.get("data") or []
    return [_semantic_record(item) for item in results if isinstance(item, dict)], len(results)


def _write_tsv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["title", "year", "venue", "doi", "arxiv_id", "pdf_url", "citation_count", "forward_sources", "url"]
    lines = ["\t".join(columns)]
    for record in records:
        values = []
        for column in columns:
            value = record.get(column)
            if isinstance(value, list):
                value = ",".join(str(item) for item in value)
            values.append(str(value or "").replace("\t", " ").replace("\n", " "))
        lines.append("\t".join(values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_titles(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(str(record["title"]) for record in records if record.get("title")) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _scholar_only(args: argparse.Namespace) -> bool:
    return bool(args.scholar_url) and not any([args.seed_title, args.seed_doi, args.seed_arxiv, args.seed_openalex, args.seed_semantic])


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect papers that cite a seed paper using OpenAlex and Semantic Scholar.")
    parser.add_argument("--seed-title")
    parser.add_argument("--seed-doi")
    parser.add_argument("--seed-arxiv")
    parser.add_argument("--seed-openalex")
    parser.add_argument("--seed-semantic")
    parser.add_argument("--scholar-url", help="Accepted only as a hint; Google Scholar is not scraped.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--min-year", type=int)
    parser.add_argument("--only-acquirable", action="store_true")
    parser.add_argument("--openalex-fixture", type=Path)
    parser.add_argument("--semantic-fixture", type=Path)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-tsv", type=Path, required=True)
    parser.add_argument("--admitted-json", type=Path, required=True)
    parser.add_argument("--titles-out", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if _scholar_only(args):
        message = "Google Scholar cited-by pages are not scraped; provide a title, DOI, arXiv ID, OpenAlex ID, or Semantic Scholar ID."
        if args.json:
            print(json.dumps({"ok": False, "error": message}, indent=2))
        else:
            print(message, file=sys.stderr)
        return 2

    warnings: list[str] = []
    try:
        if args.openalex_fixture:
            openalex_records, openalex_count = _load_openalex_records(args.openalex_fixture)
        else:
            openalex_records, openalex_count = _fetch_openalex(args)
    except Exception as exc:
        openalex_records, openalex_count = [], None
        warnings.append(f"OpenAlex citation lookup failed: {type(exc).__name__}: {exc}")
    try:
        if args.semantic_fixture:
            semantic_records, semantic_count = _load_semantic_records(args.semantic_fixture)
        else:
            semantic_records, semantic_count = _fetch_semantic(args)
    except Exception as exc:
        semantic_records, semantic_count = [], None
        warnings.append(f"Semantic Scholar citation lookup failed: {type(exc).__name__}: {exc}")

    merged = _dedupe(openalex_records + semantic_records)
    filtered: list[dict[str, Any]] = []
    for record in merged:
        if args.min_year and record.get("year") and int(record["year"]) < args.min_year:
            continue
        acquirable = bool(record.get("pdf_url") or record.get("arxiv_id"))
        record["acquisition_status"] = "acquirable" if acquirable else "metadata_only"
        if args.only_acquirable and not acquirable:
            continue
        filtered.append(record)

    raw_payload = {
        "seed": {
            "title": args.seed_title,
            "doi": args.seed_doi,
            "arxiv_id": args.seed_arxiv,
            "openalex_id": args.seed_openalex,
            "semantic_scholar_id": args.seed_semantic,
            "scholar_url_hint": args.scholar_url,
        },
        "openalex_count": openalex_count if openalex_count is not None else len(openalex_records),
        "semantic_count": semantic_count if semantic_count is not None else len(semantic_records),
        "merged_count": len(merged),
        "admitted_count": len(filtered),
        "acquirable_count": sum(1 for record in filtered if record.get("acquisition_status") == "acquirable"),
        "metadata_only_count": sum(1 for record in filtered if record.get("acquisition_status") == "metadata_only"),
        "warnings": warnings,
        "records": merged,
    }
    _write_json(args.out_json, raw_payload)
    _write_json(args.admitted_json, filtered)
    _write_tsv(args.out_tsv, filtered)
    _write_titles(args.titles_out, filtered)

    summary = {
        "ok": bool(merged) or not warnings,
        "openalex_count": raw_payload["openalex_count"],
        "semantic_count": raw_payload["semantic_count"],
        "merged_count": len(merged),
        "admitted_count": len(filtered),
        "acquirable_count": raw_payload["acquirable_count"],
        "metadata_only_count": raw_payload["metadata_only_count"],
        "out_json": str(args.out_json),
        "out_tsv": str(args.out_tsv),
        "admitted_json": str(args.admitted_json),
        "titles_out": str(args.titles_out),
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(
            "merged={merged_count} admitted={admitted_count} acquirable={acquirable_count} metadata_only={metadata_only_count}".format(
                **summary
            )
        )
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
