from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from .candidates import BIBKEY_RE, get_candidate, load_candidates, save_candidates, update_candidate
from .metadata import metadata_from_candidate
from .paths import TopicPaths
from .util import first_author_lastname, first_title_word, rel_to, safe_int


ENTRY_RE = re.compile(r"@\w+\{([^,]+),(.*?)\n\}", re.DOTALL)
FIELD_RE = re.compile(r"\n\s*([A-Za-z]+)\s*=\s*\{(.*?)\}\s*,?", re.DOTALL)


def parse_bibtex(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for match in ENTRY_RE.finditer(path.read_text(encoding="utf-8")):
        fields = {key.lower(): " ".join(value.split()) for key, value in FIELD_RE.findall(match.group(2))}
        fields["bibkey"] = match.group(1).strip()
        entries.append(fields)
    return entries


def summarize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "bibkey": entry.get("bibkey"),
        "title": entry.get("title"),
        "year": entry.get("year"),
        "venue": entry.get("journal") or entry.get("booktitle") or entry.get("venue"),
        "doi": entry.get("doi"),
        "arxiv_id": entry.get("eprint"),
        "openalex_id": entry.get("openalexid"),
    }


def list_library(root: str | Path, limit: int | None = None) -> list[dict[str, Any]]:
    entries = [summarize_entry(entry) for entry in parse_bibtex(TopicPaths.from_root(root).library_bib)]
    if limit is not None:
        return entries[: max(0, limit)]
    return entries


def find_library(root: str | Path, query: str, limit: int | None = None) -> list[dict[str, Any]]:
    needle = str(query or "").strip().lower()
    if not needle:
        return []
    matches: list[dict[str, Any]] = []
    for entry in parse_bibtex(TopicPaths.from_root(root).library_bib):
        summary = summarize_entry(entry)
        haystack = " ".join(str(summary.get(key) or "") for key in ["bibkey", "title", "year", "venue", "doi", "arxiv_id"]).lower()
        if needle in haystack:
            matches.append(summary)
            if limit is not None and len(matches) >= max(0, limit):
                break
    return matches


def existing_keys(root: str | Path) -> set[str]:
    return {entry["bibkey"] for entry in parse_bibtex(TopicPaths.from_root(root).library_bib)}


def metadata_matches_entry(meta: dict[str, Any], entry: dict[str, Any]) -> bool:
    if meta.get("doi") and entry.get("doi") and str(meta["doi"]).lower() == str(entry["doi"]).lower():
        return True
    if meta.get("arxiv_id") and entry.get("eprint") and str(meta["arxiv_id"]).lower() == str(entry["eprint"]).lower():
        return True
    if meta.get("openalex_id") and entry.get("openalexid") and str(meta["openalex_id"]).lower() == str(entry["openalexid"]).lower():
        return True
    if meta.get("semantic_scholar_id") and entry.get("semanticscholarid") and str(meta["semantic_scholar_id"]).lower() == str(entry["semanticscholarid"]).lower():
        return True
    if meta.get("dblp_key") and entry.get("dblpkey") and str(meta["dblp_key"]).lower() == str(entry["dblpkey"]).lower():
        return True
    return (
        str(meta.get("title") or "").strip().lower() == str(entry.get("title") or "").strip().lower()
        and str(meta.get("year") or "") == str(entry.get("year") or "")
    )


def find_existing_entry(root: str | Path, meta: dict[str, Any]) -> dict[str, Any] | None:
    for entry in parse_bibtex(TopicPaths.from_root(root).library_bib):
        if metadata_matches_entry(meta, entry):
            return entry
    return None


def make_bibkey(meta: dict[str, Any], used: set[str]) -> str:
    year = meta.get("year")
    base = f"{first_author_lastname(meta.get('authors'))}{year}{first_title_word(meta.get('title'))}"
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}{index}"
        index += 1
    return candidate


def format_bibtex(meta: dict[str, Any]) -> str:
    authors = " and ".join(meta.get("authors") or ["Unknown"])
    fields = [
        ("author", authors),
        ("title", meta.get("title")),
        ("year", meta.get("year")),
        ("journal", meta.get("venue") or "unknown"),
    ]
    if meta.get("doi"):
        fields.append(("doi", meta["doi"]))
    if meta.get("arxiv_id"):
        fields.append(("eprint", meta["arxiv_id"]))
        fields.append(("archivePrefix", "arXiv"))
    if meta.get("openalex_id"):
        fields.append(("openalexId", meta["openalex_id"]))
    if meta.get("semantic_scholar_id"):
        fields.append(("semanticScholarId", meta["semantic_scholar_id"]))
    if meta.get("dblp_key"):
        fields.append(("dblpKey", meta["dblp_key"]))
    if meta.get("issn"):
        fields.append(("issn", meta["issn"]))
    if meta.get("isbn"):
        fields.append(("isbn", meta["isbn"]))
    if meta.get("url"):
        fields.append(("url", meta["url"]))
    if meta.get("file"):
        fields.append(("file", meta["file"]))
    if meta.get("metadata_status"):
        fields.append(("batteryMetadataStatus", meta["metadata_status"]))
    if meta.get("verified_sources"):
        fields.append(("batteryVerifiedSource", "; ".join(str(item) for item in meta["verified_sources"] if item)))
    if meta.get("metadata_source_note"):
        fields.append(("batteryMetadataNote", meta["metadata_source_note"]))
    rendered = "\n".join(f"  {key} = {{{value}}}," for key, value in fields if value not in (None, ""))
    return f"@article{{{meta['bibkey']},\n{rendered}\n}}\n"


def write_metadata(root: str | Path, bibkey: str, meta: dict[str, Any]) -> None:
    paths = TopicPaths.from_root(root)
    paper_dir = paths.paper_dir(bibkey)
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "metadata.yml").write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _load_metadata_file(path: str | Path) -> dict[str, Any]:
    metadata_path = Path(path)
    text = metadata_path.read_text(encoding="utf-8")
    if metadata_path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("metadata file must contain an object")
    return data


def _normalize_update_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    authors = raw.get("authors") or raw.get("author") or []
    if isinstance(authors, str):
        authors = [part.strip() for part in authors.replace(";", " and ").split(" and ") if part.strip()]
    year = safe_int(raw.get("year"))
    meta = {
        "title": str(raw.get("title") or "").strip(),
        "authors": authors,
        "year": year,
        "venue": str(raw.get("venue") or raw.get("journal") or raw.get("booktitle") or "unknown").strip() or "unknown",
        "doi": str(raw.get("doi")).strip() if raw.get("doi") else None,
        "arxiv_id": str(raw.get("arxiv_id") or raw.get("eprint") or "").strip() or None,
        "openalex_id": str(raw.get("openalex_id") or raw.get("openalexId") or "").strip() or None,
        "semantic_scholar_id": str(raw.get("semantic_scholar_id") or raw.get("semanticScholarId") or "").strip() or None,
        "dblp_key": str(raw.get("dblp_key") or raw.get("dblpKey") or "").strip() or None,
        "issn": str(raw.get("issn")).strip() if raw.get("issn") else None,
        "isbn": str(raw.get("isbn")).strip() if raw.get("isbn") else None,
        "url": raw.get("url"),
        "pdf_url": raw.get("pdf_url"),
        "metadata_status": "unverified",
        "metadata_source_note": str(
            raw.get("metadata_source_note")
            or raw.get("evidence_note")
            or "user_or_agent_supplied_metadata_not_verified_by_battery_lit"
        ),
    }
    missing = [name for name in ["title", "authors", "year"] if not meta.get(name)]
    if missing:
        raise ValueError(f"missing required metadata: {', '.join(missing)}")
    if not any(meta.get(field) for field in ["doi", "arxiv_id", "openalex_id", "semantic_scholar_id", "dblp_key", "url"]):
        raise ValueError("missing DOI, arXiv id, or verified work-level source")
    return meta


def _replace_bibtex_entry(path: Path, old_bibkey: str, new_entry: str) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    matches = [match for match in ENTRY_RE.finditer(text) if match.group(1).strip() == old_bibkey]
    if not matches:
        raise KeyError(f"bibkey not found: {old_bibkey}")
    if len(matches) > 1:
        raise ValueError(f"duplicate bibkey in library.bib: {old_bibkey}")
    match = matches[0]
    updated = text[: match.start()] + new_entry.rstrip() + "\n" + text[match.end() :]
    path.write_text(updated.strip() + "\n", encoding="utf-8")


def update_library_metadata(
    root: str | Path,
    bibkey: str,
    metadata_file: str | Path,
    new_bibkey: str | None = None,
) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    old_bibkey = str(bibkey or "").strip()
    target_bibkey = str(new_bibkey or old_bibkey).strip()
    if not BIBKEY_RE.match(old_bibkey):
        raise ValueError(f"invalid bibkey: {old_bibkey!r}")
    if not BIBKEY_RE.match(target_bibkey):
        raise ValueError(f"invalid new bibkey: {target_bibkey!r}")

    entries = parse_bibtex(paths.library_bib)
    old_matches = [entry for entry in entries if entry.get("bibkey") == old_bibkey]
    if not old_matches:
        raise KeyError(f"bibkey not found: {old_bibkey}")
    if len(old_matches) > 1:
        raise ValueError(f"duplicate bibkey in library.bib: {old_bibkey}")
    if target_bibkey != old_bibkey and target_bibkey in {entry.get("bibkey") for entry in entries}:
        raise ValueError(f"new bibkey already exists: {target_bibkey}")

    old_dir = paths.paper_dir(old_bibkey)
    new_dir = paths.paper_dir(target_bibkey)
    if target_bibkey != old_bibkey:
        if not old_dir.exists():
            raise FileNotFoundError(f"paper directory missing: {old_dir}")
        if new_dir.exists():
            raise FileExistsError(f"target paper directory already exists: {new_dir}")

    meta = _normalize_update_metadata(_load_metadata_file(metadata_file))
    meta["bibkey"] = target_bibkey
    effective_dir = new_dir if target_bibkey != old_bibkey else old_dir
    existing_pdf = old_dir / "paper.pdf"
    if existing_pdf.exists():
        meta["file"] = rel_to(effective_dir / "paper.pdf", paths.root)

    new_entry = format_bibtex(meta)
    if target_bibkey != old_bibkey:
        shutil.move(str(old_dir), str(new_dir))
    write_metadata(paths.root, target_bibkey, meta)
    _replace_bibtex_entry(paths.library_bib, old_bibkey, new_entry)

    candidates = load_candidates(paths.root)
    updated_candidates = []
    for candidate in candidates:
        if candidate.get("bibkey") == old_bibkey:
            candidate["bibkey"] = target_bibkey
            updated_candidates.append(str(candidate.get("candidate_id")))
    if updated_candidates:
        save_candidates(paths.root, candidates)

    return {
        "ok": True,
        "old_bibkey": old_bibkey,
        "bibkey": target_bibkey,
        "metadata_status": "unverified",
        "updated_candidates": updated_candidates,
        "paper_dir": rel_to(effective_dir, paths.root) if effective_dir.exists() else "",
    }


def promote_candidate(root: str | Path, candidate_id: str) -> dict[str, Any]:
    from .citation_guard import guard_metadata

    paths = TopicPaths.from_root(root)
    candidate = get_candidate(root, candidate_id)
    meta = metadata_from_candidate(candidate)
    existing = find_existing_entry(root, meta)
    if existing:
        update_candidate(root, candidate_id, status="in_library", bibkey=existing["bibkey"])
        return {"ok": True, "bibkey": existing["bibkey"], "status": "already_promoted"}

    guard_metadata(meta)
    bibkey = candidate.get("bibkey") or make_bibkey(meta, existing_keys(root))
    meta["bibkey"] = bibkey
    if not (meta.get("doi") or meta.get("arxiv_id")):
        meta.setdefault("metadata_status", "verified_no_doi")
    paper_dir = paths.paper_dir(bibkey)
    paper_dir.mkdir(parents=True, exist_ok=True)

    incoming_pdf = paths.incoming / f"{candidate_id}.pdf"
    final_pdf = paper_dir / "paper.pdf"
    if incoming_pdf.exists() and not final_pdf.exists():
        shutil.move(str(incoming_pdf), final_pdf)
    if final_pdf.exists():
        meta["file"] = rel_to(final_pdf, paths.root)

    write_metadata(root, bibkey, meta)
    with paths.library_bib.open("a", encoding="utf-8") as handle:
        handle.write("\n" + format_bibtex(meta))
    update_candidate(root, candidate_id, status="in_library", bibkey=bibkey)
    return {"ok": True, "bibkey": bibkey, "status": "promoted"}
