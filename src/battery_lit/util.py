from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.read_text(encoding="utf-8").strip() == "":
        return []
    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{lineno}: {exc}") from exc
    return records


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalize_title(title: str | None) -> str:
    return normalize_text(title)


def slugify_path_component(value: str | None, fallback: str = "untitled-topic") -> str:
    text = normalize_text(value)
    slug = re.sub(r"\s+", "-", text).strip("-")
    return slug or fallback


def compact_id(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def first_author_lastname(authors: list[str] | str | None) -> str:
    if not authors:
        return "Unknown"
    first = authors[0] if isinstance(authors, list) else authors.split(" and ")[0]
    first = first.strip()
    if "," in first:
        last = first.split(",", 1)[0]
    else:
        parts = re.findall(r"[A-Za-z0-9]+", first)
        last = parts[-1] if parts else "Unknown"
    return re.sub(r"[^A-Za-z0-9]", "", last).capitalize() or "Unknown"


def first_title_word(title: str | None) -> str:
    words = re.findall(r"[A-Za-z0-9]+", title or "")
    return (words[0].capitalize() if words else "Paper")


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def rel_to(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
