from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Any

from .candidates import load_candidates, save_candidates
from .paths import TopicPaths
from .pdf import is_pdf
from .util import compact_id, normalize_text, normalize_title, safe_int, utc_now


STATUS_PRIORITY = {
    "in_library": 60,
    "downloaded": 50,
    "manual_pdf_needed": 45,
    "relevant": 40,
    "new": 30,
    "irrelevant": 20,
    "dismissed": 10,
}


def canonical_arxiv_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^arxiv:", "", text)
    text = re.sub(r"\.pdf$", "", text)
    text = re.sub(r"v[0-9]+$", "", text)
    return compact_id(text)


def _year(value: Any) -> int | None:
    return safe_int(value)


def _years_compatible(left: Any, right: Any, max_delta: int = 1) -> bool:
    left_year = _year(left)
    right_year = _year(right)
    if left_year is None or right_year is None:
        return True
    return abs(left_year - right_year) <= max_delta


def _title(record: dict[str, Any]) -> str:
    return normalize_title(str(record.get("title") or ""))


def _author_tokens(record: dict[str, Any]) -> set[str]:
    authors = record.get("authors") or []
    if isinstance(authors, str):
        authors = [authors]
    tokens: set[str] = set()
    for author in authors:
        words = normalize_text(str(author)).split()
        if words:
            tokens.add(words[-1])
            tokens.update(word for word in words if len(word) >= 4)
    return tokens


def _authors_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_tokens = _author_tokens(left)
    right_tokens = _author_tokens(right)
    if not left_tokens or not right_tokens:
        return True
    return bool(left_tokens & right_tokens)


def _titles_similar(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_title = _title(left)
    right_title = _title(right)
    if not left_title or not right_title:
        return False
    if left_title == right_title:
        return True
    if min(len(left_title), len(right_title)) < 24:
        return False
    return SequenceMatcher(None, left_title, right_title).ratio() >= 0.94


def candidate_signature(record: dict[str, Any]) -> tuple[str, str]:
    if record.get("doi"):
        return ("doi", compact_id(record.get("doi")))
    if record.get("arxiv_id"):
        return ("arxiv", canonical_arxiv_id(record.get("arxiv_id")))
    return ("title_year", f"{normalize_title(record.get('title'))}:{record.get('year') or ''}")


def candidates_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_doi = compact_id(left.get("doi"))
    right_doi = compact_id(right.get("doi"))
    if left_doi and right_doi:
        return left_doi == right_doi

    left_arxiv = canonical_arxiv_id(left.get("arxiv_id"))
    right_arxiv = canonical_arxiv_id(right.get("arxiv_id"))
    if left_arxiv and right_arxiv:
        return left_arxiv == right_arxiv

    if _title(left) == _title(right) and _years_compatible(left.get("year"), right.get("year")):
        return True

    return (
        _titles_similar(left, right)
        and _years_compatible(left.get("year"), right.get("year"))
        and _authors_compatible(left, right)
    )


def is_duplicate(record: dict[str, Any], existing: list[dict[str, Any]]) -> bool:
    return any(candidates_match(record, item) for item in existing)


def unique_records(records: list[dict[str, Any]], existing: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    seen = list(existing or [])
    unique: list[dict[str, Any]] = []
    for record in records:
        if is_duplicate(record, seen):
            continue
        seen.append(record)
        unique.append(record)
    return unique


def duplicate_groups(records: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for record in records:
        matched: list[dict[str, Any]] | None = None
        for group in groups:
            if any(candidates_match(record, item) for item in group):
                matched = group
                break
        if matched is None:
            groups.append([record])
        else:
            matched.append(record)
    return [group for group in groups if len(group) > 1]


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() != "unknown"
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return True


def _completeness(record: dict[str, Any]) -> int:
    fields = ["doi", "arxiv_id", "year", "venue", "abstract", "url", "pdf_url", "source_metadata", "verified_sources"]
    score = sum(1 for field in fields if _is_present(record.get(field)))
    if record.get("score_status") == "scored":
        score += 2
    if record.get("bibkey"):
        score += 3
    return score


def _primary_sort_key(record: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        STATUS_PRIORITY.get(str(record.get("status") or ""), 0),
        1 if record.get("score_status") == "scored" else 0,
        _completeness(record),
        str(record.get("created_at") or ""),
    )


def choose_primary(group: list[dict[str, Any]]) -> dict[str, Any]:
    return max(group, key=_primary_sort_key)


def _merge_list_values(*values: Any) -> list[Any]:
    merged: list[Any] = []
    seen: set[str] = set()
    for value in values:
        items = value if isinstance(value, list) else [value]
        for item in items:
            if item in (None, ""):
                continue
            key = str(item)
            if key not in seen:
                merged.append(item)
                seen.add(key)
    return merged


def _best_text(primary: Any, duplicate: Any, prefer_longer: bool = False) -> Any:
    if not _is_present(primary):
        return duplicate
    if prefer_longer and isinstance(primary, str) and isinstance(duplicate, str) and len(duplicate.strip()) > len(primary.strip()):
        return duplicate
    return primary


def merge_candidate_records(primary: dict[str, Any], duplicates: list[dict[str, Any]]) -> dict[str, Any]:
    merged = dict(primary)
    merged_from = _merge_list_values(merged.get("merged_from"))
    sources_seen = _merge_list_values(merged.get("sources_seen"), merged.get("source"))
    for duplicate in duplicates:
        merged_from = _merge_list_values(merged_from, duplicate.get("candidate_id"), duplicate.get("merged_from"))
        sources_seen = _merge_list_values(sources_seen, duplicate.get("source"), duplicate.get("sources_seen"))
        for field in ["doi", "arxiv_id", "url", "pdf_url", "bibkey"]:
            merged[field] = _best_text(merged.get(field), duplicate.get(field))
        for field in ["title", "venue"]:
            merged[field] = _best_text(merged.get(field), duplicate.get(field))
        merged["abstract"] = _best_text(merged.get("abstract"), duplicate.get("abstract"), prefer_longer=True)
        if not _is_present(merged.get("authors")):
            merged["authors"] = duplicate.get("authors") or []
        if not _is_present(merged.get("year")):
            merged["year"] = duplicate.get("year")
        if merged.get("score_status") != "scored" and duplicate.get("score_status") == "scored":
            for field in [
                "score",
                "score_status",
                "score_components",
                "score_reasons",
                "score_confidence",
                "scored_by",
                "scored_at",
                "score_version",
            ]:
                if field in duplicate:
                    merged[field] = duplicate.get(field)
        if not _is_present(merged.get("source_metadata")) and _is_present(duplicate.get("source_metadata")):
            merged["source_metadata"] = dict(duplicate.get("source_metadata") or {})
        merged["verified_sources"] = _merge_list_values(merged.get("verified_sources"), duplicate.get("verified_sources"))

    if merged_from:
        merged["merged_from"] = merged_from
    if sources_seen:
        merged["sources_seen"] = sources_seen
    merged["updated_at"] = utc_now()
    return merged


def _has_final_pdf(paths: TopicPaths, record: dict[str, Any]) -> bool:
    bibkey = str(record.get("bibkey") or "")
    return bool(bibkey and is_pdf(paths.paper_dir(bibkey) / "paper.pdf"))


def _incoming_pdf(paths: TopicPaths, record: dict[str, Any]) -> Path:
    return paths.incoming / f"{record.get('candidate_id')}.pdf"


def _merge_incoming_pdfs(paths: TopicPaths, primary: dict[str, Any], duplicates: list[dict[str, Any]]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    target = _incoming_pdf(paths, primary)
    primary_has_pdf = target.exists() or _has_final_pdf(paths, primary)
    for duplicate in duplicates:
        source = _incoming_pdf(paths, duplicate)
        if not source.exists():
            continue
        if not primary_has_pdf:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
            primary_has_pdf = True
            actions.append({"action": "moved_pdf", "from": str(source), "to": str(target)})
        else:
            source.unlink()
            actions.append({"action": "removed_duplicate_pdf", "path": str(source)})
    return actions


def deduplicate_candidates(root: str | Path, fix: bool = False) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    records = load_candidates(paths.root)
    groups = duplicate_groups(records)
    planned: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    remove_ids: set[str] = set()
    replacements: dict[str, dict[str, Any]] = {}
    pdf_actions: list[dict[str, str]] = []

    for group in groups:
        library_bibkeys = sorted({str(record.get("bibkey")) for record in group if record.get("status") == "in_library" and record.get("bibkey")})
        if len(library_bibkeys) > 1:
            unresolved.append(
                {
                    "reason": "multiple_library_entries",
                    "candidate_ids": [str(record.get("candidate_id")) for record in group],
                    "bibkeys": library_bibkeys,
                }
            )
            continue
        primary = choose_primary(group)
        primary_id = str(primary.get("candidate_id") or "")
        duplicates = [record for record in group if record is not primary]
        duplicate_ids = [str(record.get("candidate_id")) for record in duplicates]
        group_ids = [str(record.get("candidate_id")) for record in group]
        kept_ids = [candidate_id for candidate_id in group_ids if candidate_id not in set(duplicate_ids)]
        if not primary_id or kept_ids != [primary_id]:
            unresolved.append(
                {
                    "reason": "unsafe_primary_selection",
                    "candidate_ids": group_ids,
                    "primary": primary_id,
                    "would_remove": duplicate_ids,
                    "would_keep": kept_ids,
                }
            )
            continue
        planned.append({"primary": primary_id, "kept": primary_id, "duplicates": duplicate_ids})
        if fix:
            replacements[primary_id] = merge_candidate_records(primary, duplicates)
            remove_ids.update(duplicate_ids)
            pdf_actions.extend(_merge_incoming_pdfs(paths, primary, duplicates))

    if fix and (remove_ids or replacements):
        merged_records: list[dict[str, Any]] = []
        for record in records:
            cid = str(record.get("candidate_id"))
            if cid in remove_ids:
                continue
            merged_records.append(replacements.get(cid, record))
        save_candidates(paths.root, merged_records)
        records = merged_records

    duplicate_ids = [duplicate_id for item in planned for duplicate_id in item["duplicates"]]
    kept_candidate_ids = [str(item["kept"]) for item in planned]
    return {
        "ok": not planned and not unresolved if not fix else not unresolved,
        "duplicate_groups": planned,
        "duplicates": duplicate_ids,
        "kept_candidate_ids": kept_candidate_ids,
        "merged": len(planned) if fix else 0,
        "removed": len(remove_ids) if fix else 0,
        "unresolved": unresolved,
        "pdf_actions": pdf_actions,
        "candidate_count": len(records),
    }
