from __future__ import annotations

import ast
from pathlib import Path
import re
from typing import Any
import uuid

from .paths import TopicPaths
from .schemas import validate_with_schema
from .util import read_jsonl, safe_int, utc_now, write_jsonl

STATUSES = {"new", "relevant", "irrelevant", "dismissed", "downloaded", "in_library", "manual_pdf_needed"}
BIBKEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
RECORD_ID_RE = re.compile(r"^REC-[A-Fa-f0-9]{12}$")


def _extract_arxiv_id(*values: Any) -> str | None:
    for value in values:
        text = str(value or "")
        match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#\s]+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).removesuffix(".pdf")
        match = re.search(r"\barXiv:([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?|[A-Za-z.-]+/[0-9]{7}(?:v[0-9]+)?)", text)
        if match:
            return match.group(1)
    return None


def _year_from_arxiv_id(arxiv_id: str | None) -> int | None:
    if not arxiv_id:
        return None
    match = re.match(r"^([0-9]{2})([0-9]{2})\.[0-9]{4,5}", arxiv_id)
    if not match:
        return None
    year = int(match.group(1))
    return 2000 + year if year < 90 else 1900 + year


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text and text.lower() != "unknown":
                return text
        elif isinstance(value, list):
            text = _first_text(*value)
            if text:
                return text
    return None


def _extra_dict(raw: dict[str, Any]) -> dict[str, Any]:
    extra = raw.get("extra")
    if isinstance(extra, dict):
        return extra
    if isinstance(extra, str):
        try:
            parsed = ast.literal_eval(extra)
        except (SyntaxError, ValueError):
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _extract_venue(raw: dict[str, Any]) -> str:
    extra = _extra_dict(raw)
    venue = _first_text(
        raw.get("venue"),
        raw.get("journal"),
        raw.get("conference"),
        raw.get("source_title"),
        raw.get("sourceTitle"),
        raw.get("container_title"),
        raw.get("container-title"),
        raw.get("journal_title"),
        raw.get("journalTitle"),
        raw.get("booktitle"),
        raw.get("publication_venue"),
        extra.get("venue"),
        extra.get("journal"),
        extra.get("journal_name"),
        extra.get("journalTitle"),
        extra.get("conference"),
        extra.get("source_title"),
        extra.get("booktitle"),
        extra.get("publication_info"),
    )
    if venue:
        return venue

    source = str(raw.get("source") or "").lower()
    for name, label in {
        "arxiv": "arXiv",
        "biorxiv": "bioRxiv",
        "medrxiv": "medRxiv",
        "chemrxiv": "ChemRxiv",
        "ssrn": "SSRN",
    }.items():
        if name in source:
            return label
    return "unknown"


def load_candidates(root: str | Path) -> list[dict[str, Any]]:
    return read_jsonl(TopicPaths.from_root(root).candidates_jsonl)


def save_candidates(root: str | Path, records: list[dict[str, Any]]) -> None:
    for record in records:
        validate_candidate(record)
    write_jsonl(TopicPaths.from_root(root).candidates_jsonl, records)


def validate_candidate(record: dict[str, Any]) -> None:
    if record.get("status") not in STATUSES:
        raise ValueError(f"invalid candidate status: {record.get('status')}")
    validate_with_schema(record, "candidate.schema.json")


def next_candidate_id(records: list[dict[str, Any]]) -> str:
    max_id = 0
    for record in records:
        cid = str(record.get("candidate_id", ""))
        if cid.startswith("CAND-"):
            try:
                max_id = max(max_id, int(cid.split("-", 1)[1]))
            except ValueError:
                pass
    return f"CAND-{max_id + 1:03d}"


def new_record_id() -> str:
    return f"REC-{uuid.uuid4().hex[:12]}"


def ensure_record_ids(records: list[dict[str, Any]]) -> int:
    seen: set[str] = set()
    changed = 0
    for record in records:
        record_id = str(record.get("record_id") or "")
        if not RECORD_ID_RE.match(record_id) or record_id in seen:
            record["record_id"] = new_record_id()
            changed += 1
        seen.add(str(record["record_id"]))
    return changed


def normalize_candidate(raw: dict[str, Any], candidate_id: str | None = None) -> dict[str, Any]:
    now = utc_now()
    authors = raw.get("authors") or raw.get("author") or []
    if isinstance(authors, str):
        authors = [part.strip() for part in authors.replace(";", " and ").split(" and ") if part.strip()]
    arxiv_id = raw.get("arxiv_id") or raw.get("arxiv") or raw.get("eprint") or _extract_arxiv_id(raw.get("url"), raw.get("landing_url"), raw.get("pdf_url"), raw.get("pdf"))
    year = safe_int(raw.get("year") or raw.get("published_year") or raw.get("publication_year")) or _year_from_arxiv_id(str(arxiv_id) if arxiv_id else None)
    venue = _extract_venue(raw)
    doi = raw.get("doi")
    openalex_id = raw.get("openalex_id") or raw.get("openalex") or raw.get("openalexId")
    semantic_scholar_id = raw.get("semantic_scholar_id") or raw.get("semanticScholarId") or raw.get("corpus_id") or raw.get("corpusId")
    dblp_key = raw.get("dblp_key") or raw.get("dblp") or raw.get("dblpKey")
    if raw.get("status") is not None and raw.get("status") not in STATUSES:
        raise ValueError(f"invalid candidate status: {raw.get('status')}")
    record = {
        "record_id": str(raw.get("record_id") or new_record_id()),
        "candidate_id": candidate_id or raw.get("candidate_id") or "CAND-000",
        "title": str(raw.get("title") or "").strip(),
        "authors": authors,
        "year": year,
        "venue": str(venue or "unknown").strip() or "unknown",
        "abstract": str(raw.get("abstract") or raw.get("summary") or "").strip(),
        "doi": str(doi).strip() if doi else None,
        "arxiv_id": str(arxiv_id).strip() if arxiv_id else None,
        "openalex_id": str(openalex_id).strip() if openalex_id else None,
        "semantic_scholar_id": str(semantic_scholar_id).strip() if semantic_scholar_id else None,
        "dblp_key": str(dblp_key).strip() if dblp_key else None,
        "issn": str(raw.get("issn")).strip() if raw.get("issn") else None,
        "isbn": str(raw.get("isbn")).strip() if raw.get("isbn") else None,
        "url": raw.get("url") or raw.get("landing_url"),
        "pdf_url": raw.get("pdf_url") or raw.get("pdf") or raw.get("openAccessPdf"),
        "source": str(raw.get("source") or "unknown"),
        "score": float(raw.get("score") or 0.0),
        "score_status": raw.get("score_status") or "unscored",
        "status": raw.get("status") or "new",
        "decision": raw.get("decision"),
        "bibkey": raw.get("bibkey"),
        "created_at": raw.get("created_at") or now,
        "updated_at": raw.get("updated_at") or now,
    }
    if raw.get("verified_sources"):
        record["verified_sources"] = list(raw.get("verified_sources") or [])
    if raw.get("source_metadata"):
        record["source_metadata"] = dict(raw.get("source_metadata") or {})
    validate_candidate(record)
    return record


def append_candidates(root: str | Path, raw_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = load_candidates(root)
    added: list[dict[str, Any]] = []
    for raw in raw_records:
        candidate = normalize_candidate(raw, next_candidate_id(records))
        records.append(candidate)
        added.append(candidate)
    save_candidates(root, records)
    return added


def _matching_candidates(records: list[dict[str, Any]], candidate_id: str) -> list[dict[str, Any]]:
    return [record for record in records if record.get("candidate_id") == candidate_id]


def _require_unique_candidate(records: list[dict[str, Any]], candidate_id: str) -> dict[str, Any]:
    matches = _matching_candidates(records, candidate_id)
    if not matches:
        raise KeyError(f"candidate not found: {candidate_id}")
    if len(matches) > 1:
        raise ValueError(f"ambiguous candidate_id: {candidate_id}; run `battery_lit candidates repair --fix` first")
    return matches[0]


def get_candidate(root: str | Path, candidate_id: str) -> dict[str, Any]:
    return _require_unique_candidate(load_candidates(root), candidate_id)


def update_candidate(root: str | Path, candidate_id: str, **updates: Any) -> dict[str, Any]:
    records = load_candidates(root)
    record = _require_unique_candidate(records, candidate_id)
    record.update(updates)
    record["updated_at"] = utc_now()
    validate_candidate(record)
    save_candidates(root, records)
    return record


def mark_candidate(root: str | Path, candidate_id: str, decision: str) -> dict[str, Any]:
    mapping = {"relevant": "relevant", "irrelevant": "irrelevant", "dismissed": "dismissed", "none": "relevant"}
    if decision not in mapping:
        raise ValueError(f"unsupported decision: {decision}")
    return update_candidate(root, candidate_id, status=mapping[decision], decision=decision)


def _normalized_title(record: dict[str, Any]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(record.get("title") or "").lower()).strip()


def _same_paper(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for key in ("doi", "arxiv_id", "openalex_id", "semantic_scholar_id"):
        left_value = str(left.get(key) or "").strip().lower()
        right_value = str(right.get(key) or "").strip().lower()
        if left_value and right_value and left_value == right_value:
            return True
    return bool(_normalized_title(left) and _normalized_title(left) == _normalized_title(right))


def _candidate_rank(record: dict[str, Any]) -> tuple[int, int, int, str]:
    status_rank = {
        "in_library": 6,
        "downloaded": 5,
        "relevant": 4,
        "manual_pdf_needed": 3,
        "new": 2,
        "irrelevant": 1,
        "dismissed": 0,
    }.get(str(record.get("status") or ""), 0)
    scored_rank = 1 if record.get("score_status") == "scored" else 0
    completeness = sum(1 for key in ("title", "abstract", "doi", "arxiv_id", "pdf_url", "venue", "year") if record.get(key))
    return (status_rank, scored_rank, completeness, str(record.get("updated_at") or ""))


def _merge_candidate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    primary = max(records, key=_candidate_rank)
    merged = dict(primary)
    for record in records:
        for key, value in record.items():
            if key in {"candidate_id", "record_id", "created_at", "updated_at"}:
                continue
            if merged.get(key) in (None, "", [], {}, "unknown") and value not in (None, "", [], {}, "unknown"):
                merged[key] = value
        if record.get("score_status") == "scored" and merged.get("score_status") != "scored":
            for key in ("score", "score_status", "score_components", "score_confidence", "score_reasons", "scored_by", "scored_at", "score_version"):
                if key in record:
                    merged[key] = record[key]
    merged["candidate_id"] = str(primary.get("candidate_id"))
    merged["record_id"] = str(primary.get("record_id") or new_record_id())
    merged["updated_at"] = utc_now()
    return merged


def repair_candidate_records(root: str | Path, fix: bool = False) -> dict[str, Any]:
    records = load_candidates(root)
    working = [dict(record) for record in records]
    assigned_record_ids = ensure_record_ids(working)

    groups: dict[str, list[dict[str, Any]]] = {}
    for record in working:
        groups.setdefault(str(record.get("candidate_id") or ""), []).append(record)

    next_records: list[dict[str, Any]] = []
    existing_for_ids: list[dict[str, Any]] = [record for records_for_id in groups.values() for record in records_for_id]
    merged_groups: list[dict[str, Any]] = []
    renumbered: list[dict[str, str]] = []

    for candidate_id, group in groups.items():
        if len(group) == 1:
            next_records.append(group[0])
            continue
        if all(_same_paper(group[0], item) for item in group[1:]):
            merged = _merge_candidate_records(group)
            next_records.append(merged)
            kept_record_id = str(merged.get("record_id"))
            merged_groups.append(
                {
                    "candidate_id": candidate_id,
                    "kept_record_id": kept_record_id,
                    "merged_record_ids": [str(item.get("record_id")) for item in group if str(item.get("record_id")) != kept_record_id],
                    "removed_count": len(group) - 1,
                }
            )
            continue
        keep_first = True
        for record in group:
            if keep_first:
                next_records.append(record)
                keep_first = False
                continue
            old_id = str(record.get("candidate_id"))
            new_id = next_candidate_id(existing_for_ids)
            record["candidate_id"] = new_id
            record["updated_at"] = utc_now()
            existing_for_ids.append(record)
            next_records.append(record)
            renumbered.append({"record_id": str(record.get("record_id")), "old_candidate_id": old_id, "new_candidate_id": new_id})

    result = {
        "ok": True,
        "fix": fix,
        "assigned_record_ids": assigned_record_ids,
        "merged_groups": merged_groups,
        "renumbered": renumbered,
        "removed_count": sum(item["removed_count"] for item in merged_groups),
        "candidate_count_before": len(records),
        "candidate_count_after": len(next_records),
    }
    if fix and (assigned_record_ids or merged_groups or renumbered):
        save_candidates(root, next_records)
    return result


def remove_candidate_by_record_id(root: str | Path, record_id: str) -> dict[str, Any]:
    record_id = str(record_id or "").strip()
    if not RECORD_ID_RE.match(record_id):
        raise ValueError(f"invalid record_id: {record_id!r}")
    records = load_candidates(root)
    matched = [record for record in records if record.get("record_id") == record_id]
    if not matched:
        return {"ok": False, "record_id": record_id, "removed_count": 0, "error": f"candidate record not found: {record_id}"}
    if len(matched) > 1:
        return {"ok": False, "record_id": record_id, "removed_count": 0, "error": f"duplicate record_id found: {record_id}; run repair first"}
    kept = [record for record in records if record.get("record_id") != record_id]
    save_candidates(root, kept)
    removed = matched[0]
    return {
        "ok": True,
        "record_id": record_id,
        "removed_count": 1,
        "removed_candidate_id": removed.get("candidate_id"),
        "removed_title": removed.get("title"),
        "candidate_count": len(kept),
    }


def remove_candidates_by_bibkey(root: str | Path, bibkey: str) -> dict[str, Any]:
    bibkey = str(bibkey or "").strip()
    if not BIBKEY_RE.match(bibkey):
        raise ValueError(f"invalid bibkey: {bibkey!r}")

    records = load_candidates(root)
    matched = [record for record in records if record.get("bibkey") == bibkey]
    matched_ids = [str(record.get("candidate_id")) for record in matched]
    if not matched:
        return {
            "ok": False,
            "bibkey": bibkey,
            "removed_count": 0,
            "removed_candidate_ids": [],
            "matched_candidate_ids": [],
            "candidate_count": len(records),
            "error": f"no candidate queue item found for bibkey: {bibkey}",
        }
    if len(matched) > 1:
        return {
            "ok": False,
            "bibkey": bibkey,
            "removed_count": 0,
            "removed_candidate_ids": [],
            "matched_candidate_ids": matched_ids,
            "candidate_count": len(records),
            "error": f"multiple candidate queue items found for bibkey: {bibkey}; run dedup or remove by candidate_id first",
        }

    kept = [record for record in records if record.get("bibkey") != bibkey]
    save_candidates(root, kept)
    return {
        "ok": True,
        "bibkey": bibkey,
        "removed_count": 1,
        "removed_candidate_ids": matched_ids,
        "matched_candidate_ids": matched_ids,
        "candidate_count": len(kept),
    }
