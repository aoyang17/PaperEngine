from __future__ import annotations

from pathlib import Path
from typing import Any

from .bib import parse_bibtex
from .paths import TopicPaths
from .util import compact_id, normalize_title


class CitationGuardError(ValueError):
    pass


WORK_IDENTIFIER_FIELDS = ["doi", "arxiv_id", "openalex_id", "semantic_scholar_id", "dblp_key", "url"]


def has_work_identifier(meta: dict[str, Any]) -> bool:
    return any(bool(meta.get(field)) for field in WORK_IDENTIFIER_FIELDS)


def guard_metadata(meta: dict[str, Any]) -> None:
    missing = [name for name in ["title", "authors", "year"] if not meta.get(name)]
    if missing:
        raise CitationGuardError(f"missing required metadata: {', '.join(missing)}")
    if not has_work_identifier(meta):
        raise CitationGuardError("missing DOI, arXiv id, or verified work-level source")
    if not meta.get("verified_sources"):
        raise CitationGuardError("missing verified metadata sources")
    source_meta = meta.get("source_metadata") or {}
    if not source_meta:
        raise CitationGuardError("missing verified source metadata")
    if source_meta.get("title") and normalize_title(source_meta.get("title")) != normalize_title(meta.get("title")):
        raise CitationGuardError("title mismatch with verified source")
    if source_meta.get("year") and str(source_meta.get("year")) != str(meta.get("year")):
        raise CitationGuardError("year mismatch with verified source")
    if source_meta.get("doi") and meta.get("doi") and compact_id(source_meta.get("doi")) != compact_id(meta.get("doi")):
        raise CitationGuardError("DOI mismatch with verified source")
    if source_meta.get("arxiv_id") and meta.get("arxiv_id") and compact_id(source_meta.get("arxiv_id")) != compact_id(meta.get("arxiv_id")):
        raise CitationGuardError("arXiv id mismatch with verified source")
    for field, label in [
        ("openalex_id", "OpenAlex id"),
        ("semantic_scholar_id", "Semantic Scholar id"),
        ("dblp_key", "DBLP key"),
        ("url", "URL"),
    ]:
        if source_meta.get(field) and meta.get(field) and compact_id(source_meta.get(field)) != compact_id(meta.get(field)):
            raise CitationGuardError(f"{label} mismatch with verified source")
    if meta.get("venue") in (None, ""):
        meta["venue"] = "unknown"


def check_bib(root: str | Path) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    entries = parse_bibtex(paths.library_bib)
    seen: set[str] = set()
    errors: list[str] = []
    for entry in entries:
        key = entry.get("bibkey")
        if key in seen:
            errors.append(f"duplicate bibkey: {key}")
        seen.add(key)
        for field in ["author", "title", "year"]:
            if not entry.get(field):
                errors.append(f"{key}: missing {field}")
        if not _entry_has_work_identifier(entry):
            errors.append(f"{key}: missing DOI, arXiv eprint, or verified work-level source")
        if entry.get("file"):
            file_value = Path(entry["file"])
            pdf_path = paths.root / file_value
            if file_value.is_absolute() or not pdf_path.exists():
                errors.append(f"{key}: file path missing or not relative/existing: {entry['file']}")
    return {"ok": not errors, "entries": len(entries), "errors": errors}


def _entry_has_work_identifier(entry: dict[str, Any]) -> bool:
    return any(
        bool(entry.get(field))
        for field in ["doi", "eprint", "openalexid", "semanticscholarid", "dblpkey", "url"]
    )


def citation_guard_candidate(root: str | Path, candidate_id: str) -> dict[str, Any]:
    from .candidates import get_candidate
    from .metadata import metadata_from_candidate

    meta = metadata_from_candidate(get_candidate(root, candidate_id))
    try:
        guard_metadata(meta)
    except CitationGuardError as exc:
        return {"ok": False, "errors": [str(exc)]}
    return {"ok": True, "errors": []}
