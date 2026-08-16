from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .bib import parse_bibtex
from .candidates import load_candidates, next_candidate_id, normalize_candidate, save_candidates
from .dedup import candidates_match, deduplicate_candidates
from .metadata import enrich_openalex_pdf_signals
from .paths import TopicPaths, repo_root
from .topic import load_topic


def _extract_results(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["results", "papers", "items"]:
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def load_search_fixture(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return _extract_results(data)


def backend_command() -> list[str]:
    override = os.environ.get("BATTERY_LIT_SEARCH_CMD")
    if override:
        return shlex.split(override)
    return [str(repo_root() / "bin" / "paper-search")]


def run_backend_search(query: str, max_results: int = 20, sources: str = "arxiv,openalex,crossref,semantic", enrich_semantic_pdf: bool = True) -> list[dict[str, Any]]:
    cmd = backend_command() + ["search", query, "-n", str(max_results), "-s", sources]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"paper-search backend failed with exit code {proc.returncode}: {proc.stderr or proc.stdout}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"paper-search backend returned non-JSON output: {proc.stdout[:500]}") from exc
    records = _extract_results(data)
    if enrich_semantic_pdf:
        records, _ = enrich_openalex_pdf_signals(records)
    return records


def _library_as_candidates(root: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entry in parse_bibtex(TopicPaths.from_root(root).library_bib):
        records.append(
            {
                "title": entry.get("title"),
                "year": entry.get("year"),
                "doi": entry.get("doi"),
                "arxiv_id": entry.get("eprint"),
            }
        )
    return records


def collect(
    root: str | Path,
    query: str | None = None,
    fixture: str | Path | None = None,
    target_new: int = 20,
    score_threshold: float | None = None,
) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    topic = load_topic(root)
    query = query or str(topic.get("direction") or topic.get("title") or "")
    raw_results = load_search_fixture(fixture) if fixture else run_backend_search(query, max_results=target_new, enrich_semantic_pdf=False)
    raw_results, enrichment_stats = enrich_openalex_pdf_signals(raw_results)

    existing = load_candidates(root)
    existing_for_dedup = _library_as_candidates(root)
    normalized: list[dict[str, Any]] = []
    skipped_invalid = 0
    for raw in raw_results:
        raw = dict(raw)
        raw.setdefault("source", "fixture" if fixture else "paper-search")
        try:
            candidate = normalize_candidate(raw, next_candidate_id(existing + normalized))
        except Exception:
            skipped_invalid += 1
            continue
        if fixture:
            candidate["verified_sources"] = [f"fixture:{Path(fixture).name}"]
            candidate["source_metadata"] = {
                "title": candidate.get("title"),
                "year": candidate.get("year"),
                "doi": candidate.get("doi"),
                "arxiv_id": candidate.get("arxiv_id"),
            }
        candidate["score"] = 0.0
        candidate["score_status"] = "unscored"
        normalized.append(candidate)

    pre_count = len(existing)
    library_duplicate_ids = set()
    for candidate in normalized:
        if any(candidates_match(candidate, item) for item in existing_for_dedup):
            library_duplicate_ids.add(candidate.get("candidate_id"))
    admitted = [candidate for candidate in normalized if candidate.get("candidate_id") not in library_duplicate_ids]
    all_records = existing + admitted[:target_new]
    save_candidates(root, all_records)
    dedup_result = deduplicate_candidates(root, fix=True)
    final_count = len(load_candidates(root))
    paths.reports.mkdir(parents=True, exist_ok=True)
    report = {
        "ok": True,
        "query": query,
        "seen": len(raw_results),
        "added": max(0, final_count - pre_count),
        "skipped_invalid": skipped_invalid,
        "skipped_library_duplicates": len(library_duplicate_ids),
        "duplicates_merged": dedup_result.get("merged", 0),
        "duplicates_removed": dedup_result.get("removed", 0),
        "duplicate_groups": dedup_result.get("duplicate_groups", []),
        "score_threshold": score_threshold,
        "score_filter_applied": False,
        **enrichment_stats,
    }
    (paths.reports / "last_collect.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def resolve_paper(root: str | Path, title_or_query: str) -> dict[str, Any]:
    records = run_backend_search(title_or_query, max_results=5)
    if not records:
        return {"ok": False, "error": "no candidates found", "query": title_or_query}
    candidate = normalize_candidate(records[0], "CAND-000")
    return {"ok": True, "candidate": candidate}
