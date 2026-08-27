"""Import a completed knowledge-paper bundle from another PaperEngine topic.

This deliberately operates on paper-local artifacts only.  It is used by the
CLI layer, but contains no CLI or HTML concerns so it can also be used by jobs.
"""
from __future__ import annotations

import copy
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

import yaml

from .acquire import check_pdfs
from .bib import (
    find_existing_entry,
    format_bibtex,
    make_bibkey,
    metadata_matches_entry,
    parse_bibtex,
)
from .candidates import BIBKEY_RE, load_candidates, new_record_id, next_candidate_id, save_candidates, validate_candidate
from .citation_guard import check_bib, guard_metadata
from .paths import TopicPaths
from .pdf import is_pdf
from .read import audit_deep_read_quality, rebuild_note, validate_deep_read_report
from .util import compact_id, rel_to, utc_now


_FILES = (
    "paper.pdf",
    "metadata.yml",
    "parsed.md",
    "paper_index.json",
    "math_index.json",
    "formula_vision.json",
    "visual_index.md",
    "source_map.json",
    "note_plan.json",
    "deep_read.json",
)
_DIRECTORIES = ("page_images", "math_pages")
_REQUIRED = ("paper.pdf", "parsed.md", "paper_index.json", "source_map.json", "note_plan.json", "deep_read.json")
_SOURCE_CANDIDATE_FIELDS = (
    "abstract",
    "source",
    "url",
    "pdf_url",
    "issn",
    "isbn",
    "verified_sources",
    "source_metadata",
)


def _valid_topic(paths: TopicPaths) -> bool:
    return paths.root.is_dir() and paths.topic_yml.is_file() and paths.policy_yml.is_file() and paths.agents.is_file()


def _read_metadata(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid metadata.yml: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("metadata.yml must contain an object")
    return data


def _metadata_matches_source_entry(meta: dict[str, Any], entry: dict[str, Any]) -> bool:
    for meta_key, entry_key in (
        ("doi", "doi"),
        ("arxiv_id", "eprint"),
        ("openalex_id", "openalexid"),
        ("semantic_scholar_id", "semanticscholarid"),
        ("dblp_key", "dblpkey"),
    ):
        meta_value = compact_id(meta.get(meta_key))
        entry_value = compact_id(entry.get(entry_key))
        if meta_value and entry_value and meta_value != entry_value:
            return False
    return metadata_matches_entry(meta, entry)


def _validate_asset_boundaries(source_dir: Path) -> None:
    source_root = source_dir.resolve()
    for name in (*_FILES, *_DIRECTORIES):
        path = source_dir / name
        if not path.exists() and not path.is_symlink():
            continue
        candidates = [path]
        if path.is_dir() and not path.is_symlink():
            candidates.extend(path.rglob("*"))
        for candidate in candidates:
            if candidate.is_symlink():
                raise ValueError(f"source asset must not be a symlink: {candidate.relative_to(source_dir)}")
            try:
                candidate.resolve().relative_to(source_root)
            except ValueError as exc:
                raise ValueError(f"source asset escapes paper directory: {candidate}") from exc


def _candidate_matches(meta: dict[str, Any], candidate: dict[str, Any]) -> bool:
    # Adapt the candidate spelling to the library identity comparator.  Keeping
    # this aligned with metadata_matches_entry prevents a separate identity rule.
    entry = dict(candidate)
    entry["eprint"] = candidate.get("arxiv_id")
    entry["openalexid"] = candidate.get("openalex_id")
    entry["semanticscholarid"] = candidate.get("semantic_scholar_id")
    entry["dblpkey"] = candidate.get("dblp_key")
    return metadata_matches_entry(meta, entry)


def _unique_candidate(records: list[dict[str, Any]], meta: dict[str, Any], *, label: str) -> dict[str, Any] | None:
    matches = [record for record in records if _candidate_matches(meta, record)]
    if len(matches) > 1:
        raise ValueError(f"ambiguous {label} candidates match imported paper")
    return matches[0] if matches else None


def _rewrite_value(value: Any, old: str, new: str, *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {name: _rewrite_value(item, old, new, key=str(name)) for name, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_value(item, old, new) for item in value]
    if isinstance(value, str):
        if key == "bibkey" and value == old:
            return new
        # Only rewrite an explicit topic-relative paper path, never arbitrary
        # natural-language occurrences of the old key.
        return value.replace(f"papers/{old}/", f"papers/{new}/")
    return value


def _rewrite_staged_artifacts(paper_dir: Path, old: str, new: str) -> None:
    for path in paper_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            path.write_text(json.dumps(_rewrite_value(data, old, new), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        elif path.suffix in {".yml", ".yaml"}:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            path.write_text(yaml.safe_dump(_rewrite_value(data, old, new), sort_keys=False, allow_unicode=True), encoding="utf-8")
        elif path.name in {"parsed.md", "visual_index.md"}:
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace(f"papers/{old}/", f"papers/{new}/"), encoding="utf-8")

    deep_read_path = paper_dir / "deep_read.json"
    deep_read = json.loads(deep_read_path.read_text(encoding="utf-8"))
    deep_read.update(
        {
            "bibkey": new,
            "pdf_path": f"papers/{new}/paper.pdf",
            "parsed_markdown_path": f"papers/{new}/parsed.md",
            "source_map_path": f"papers/{new}/source_map.json",
        }
    )
    deep_read_path.write_text(json.dumps(deep_read, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    source_map_path = paper_dir / "source_map.json"
    source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
    paper = source_map.get("paper")
    if not isinstance(paper, dict):
        raise ValueError("source_map.json is missing paper metadata")
    paper.update(
        {
            "bibkey": new,
            "pdf_path": f"papers/{new}/paper.pdf",
            "parsed_markdown_path": f"papers/{new}/parsed.md",
        }
    )
    source_map_path.write_text(json.dumps(source_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _copy_assets(source_dir: Path, staged_dir: Path) -> list[str]:
    copied: list[str] = []
    staged_dir.mkdir(parents=True)
    for name in _FILES:
        source = source_dir / name
        if source.is_file():
            shutil.copy2(source, staged_dir / name)
            copied.append(name)
    for name in _DIRECTORIES:
        source = source_dir / name
        if source.is_dir():
            shutil.copytree(source, staged_dir / name)
            copied.extend(str(path.relative_to(staged_dir)) for path in (staged_dir / name).rglob("*") if path.is_file())
    return copied


def _candidate_import_fields(source_candidate: dict[str, Any] | None) -> dict[str, Any]:
    if not source_candidate:
        return {}
    return {
        key: copy.deepcopy(source_candidate[key])
        for key in _SOURCE_CANDIDATE_FIELDS
        if source_candidate.get(key) not in (None, "", [], {}, "unknown")
    }


def _import_candidate(
    target_records: list[dict[str, Any]], source_candidate: dict[str, Any] | None, target_candidate: dict[str, Any] | None,
    meta: dict[str, Any], bibkey: str, source_root: Path, source_bibkey: str,
) -> list[dict[str, Any]]:
    now = utc_now()
    provenance = {"kind": "topic_import", "source_root": str(source_root), "source_bibkey": source_bibkey, "imported_at": now}
    if target_candidate is not None:
        record = target_candidate
        previous_decision = record.get("decision")
        for key, value in _candidate_import_fields(source_candidate).items():
            if record.get(key) in (None, "", [], {}, "unknown"):
                record[key] = value
        record.update({"status": "in_library", "decision": "relevant", "bibkey": bibkey, "updated_at": now, "import_provenance": provenance})
        if previous_decision != "relevant":
            record.pop("preference_recorded_decision", None)
        validate_candidate(record)
        return target_records

    base = _candidate_import_fields(source_candidate)
    base.update({
        "record_id": new_record_id(), "candidate_id": next_candidate_id(target_records),
        "title": meta.get("title"), "authors": meta.get("authors") or [], "year": meta.get("year"),
        "venue": meta.get("venue") or "unknown", "doi": meta.get("doi"), "arxiv_id": meta.get("arxiv_id"),
        "openalex_id": meta.get("openalex_id"), "semantic_scholar_id": meta.get("semantic_scholar_id"), "dblp_key": meta.get("dblp_key"),
        "status": "in_library", "decision": "relevant", "bibkey": bibkey, "score": 0.0, "score_status": "unscored",
        "created_at": now, "updated_at": now, "import_provenance": provenance,
    })
    # Score details cannot describe an unscored imported record.
    for key in (
        "score_components",
        "score_reasons",
        "score_confidence",
        "scored_by",
        "scored_at",
        "score_version",
        "preference_recorded_decision",
    ):
        base.pop(key, None)
    base.setdefault("abstract", "")
    base.setdefault("source", "topic_import")
    validate_candidate(base)
    target_records.append(base)
    return target_records


def import_paper_from_topic(target_root: str | Path, source_root: str | Path, source_bibkey: str) -> dict[str, Any]:
    """Install one complete paper bundle, rolling back target mutations on failure."""
    target = TopicPaths.from_root(target_root)
    source = TopicPaths.from_root(source_root)
    if target.root == source.root:
        raise ValueError("source and target topic roots must be distinct")
    if not _valid_topic(source) or not _valid_topic(target):
        raise ValueError("source and target must be valid PaperEngine topic roots")
    source_bibkey = str(source_bibkey or "").strip()
    if not BIBKEY_RE.match(source_bibkey):
        raise ValueError(f"invalid bibkey: {source_bibkey!r}")
    entries = [entry for entry in parse_bibtex(source.library_bib) if entry.get("bibkey") == source_bibkey]
    if len(entries) != 1:
        raise ValueError(f"source library must contain exactly one entry for {source_bibkey}")
    source_dir = source.paper_dir(source_bibkey)
    metadata_path = source_dir / "metadata.yml"
    if not metadata_path.is_file():
        raise ValueError(f"missing metadata.yml for {source_bibkey}")
    meta = _read_metadata(metadata_path)
    if meta.get("bibkey") != source_bibkey:
        raise ValueError("metadata.yml bibkey does not match source bibkey")
    if not _metadata_matches_source_entry(meta, entries[0]):
        raise ValueError("metadata.yml does not match the source BibTeX entry")

    existing = find_existing_entry(target.root, meta)
    if existing:
        return {"ok": True, "status": "already_exists", "bibkey": existing["bibkey"], "existing_bibkey": existing["bibkey"], "message": "Skipped import: this paper already exists in the target library."}

    # All validations which can fail without mutation are intentionally before
    # staging/snapshots, including target-candidate ambiguity.
    for name in _REQUIRED:
        path = source_dir / name
        if not path.is_file():
            raise ValueError(f"missing required source asset: {name}")
    if not is_pdf(source_dir / "paper.pdf"):
        raise ValueError("source paper.pdf is invalid")
    _validate_asset_boundaries(source_dir)
    guard_metadata(meta)
    for check in (validate_deep_read_report(source.root, source_bibkey), audit_deep_read_quality(source.root, source_bibkey)):
        if not check.get("ok"):
            raise ValueError("source deep-read validation failed: " + "; ".join(str(item) for item in check.get("errors") or []))
    source_candidate = _unique_candidate(load_candidates(source.root), meta, label="source")
    target_records = load_candidates(target.root)
    target_candidate = _unique_candidate(target_records, meta, label="target")

    used = {entry.get("bibkey") for entry in parse_bibtex(target.library_bib)}
    target_bibkey = source_bibkey if source_bibkey not in used else make_bibkey(meta, {str(key) for key in used if key})
    target_dir = target.paper_dir(target_bibkey)
    if target_dir.exists():
        raise FileExistsError(f"target paper directory already exists: {target_dir}")

    run_dir = target.root / ".tmp" / "topic_import" / uuid.uuid4().hex
    staged_dir = run_dir / "paper"
    library_snapshot = run_dir / "library.bib.snapshot"
    candidates_snapshot = run_dir / "candidates.jsonl.snapshot"
    installed = False
    try:
        run_dir.mkdir(parents=True)
        shutil.copy2(target.library_bib, library_snapshot)
        shutil.copy2(target.candidates_jsonl, candidates_snapshot)
        copied = _copy_assets(source_dir, staged_dir)
        _rewrite_staged_artifacts(staged_dir, source_bibkey, target_bibkey)
        imported_meta = _read_metadata(staged_dir / "metadata.yml")
        imported_meta["bibkey"] = target_bibkey
        imported_meta["file"] = rel_to(target_dir / "paper.pdf", target.root)
        (staged_dir / "metadata.yml").write_text(yaml.safe_dump(imported_meta, sort_keys=False, allow_unicode=True), encoding="utf-8")
        shutil.move(str(staged_dir), str(target_dir))
        installed = True
        with target.library_bib.open("a", encoding="utf-8") as handle:
            if target.library_bib.stat().st_size:
                handle.write("\n")
            handle.write(format_bibtex(imported_meta))
        save_candidates(target.root, _import_candidate(target_records, source_candidate, target_candidate, imported_meta, target_bibkey, source.root, source_bibkey))
        checks = {
            "validate_deep_read_report": validate_deep_read_report(target.root, target_bibkey),
            "audit_deep_read_quality": audit_deep_read_quality(target.root, target_bibkey),
            "rebuild_note": rebuild_note(target.root, target_bibkey),
            "check_bib": check_bib(target.root),
            "check_pdfs": check_pdfs(target.root),
        }
        failed = [name for name, result in checks.items() if not result.get("ok")]
        if failed:
            raise ValueError("target import validation failed: " + ", ".join(failed))
        return {"ok": True, "status": "imported", "bibkey": target_bibkey, "source_bibkey": source_bibkey, "copied_assets": copied, "checks": checks}
    except Exception:
        if library_snapshot.exists():
            shutil.copy2(library_snapshot, target.library_bib)
        if candidates_snapshot.exists():
            shutil.copy2(candidates_snapshot, target.candidates_jsonl)
        if installed and target_dir.exists():
            shutil.rmtree(target_dir)
        raise
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
