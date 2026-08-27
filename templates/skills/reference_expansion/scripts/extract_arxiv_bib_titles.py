#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen


def _load_candidate(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("candidate"), dict):
        return data["candidate"]
    if isinstance(data, dict):
        return data
    raise ValueError(f"candidate JSON must be an object: {path}")


def _candidate_arxiv_id(candidate: dict) -> str | None:
    for key in ["arxiv_id", "arxiv", "eprint"]:
        value = candidate.get(key)
        if value:
            return str(value).removesuffix(".pdf")
    for key in ["url", "pdf_url", "landing_url"]:
        value = str(candidate.get(key) or "")
        match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#\s]+)", value, re.IGNORECASE)
        if match:
            return match.group(1).removesuffix(".pdf")
    return None


def _download_source(arxiv_id: str, target: Path) -> None:
    url = f"https://arxiv.org/e-print/{arxiv_id}"
    with urlopen(url, timeout=60) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _safe_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    safe: list[tarfile.TarInfo] = []
    for member in archive.getmembers():
        name = Path(member.name)
        if name.is_absolute() or ".." in name.parts:
            raise ValueError(f"unsafe archive member path: {member.name}")
        safe.append(member)
    return safe


def _extract_archive(archive_path: Path, target_dir: Path) -> None:
    try:
        with tarfile.open(archive_path, "r:*") as archive:
            archive.extractall(target_dir, members=_safe_members(archive))
    except tarfile.TarError as exc:
        raise ValueError(f"cannot read arXiv source archive: {archive_path}") from exc


def _iter_entries(text: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    index = 0
    while True:
        start = text.find("@", index)
        if start < 0:
            break
        open_brace = text.find("{", start)
        if open_brace < 0:
            break
        kind = text[start + 1 : open_brace].strip().lower()
        depth = 0
        end = open_brace
        for pos in range(open_brace, len(text)):
            char = text[pos]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = pos
                    break
        else:
            break
        if kind and kind not in {"comment", "preamble", "string"}:
            entries.append((kind, text[open_brace + 1 : end]))
        index = end + 1
    return entries


def _clean_value(value: str) -> str:
    value = value.strip().strip("{}").strip('"').strip()
    value = re.sub(r"\s+", " ", value)
    return value.replace("{", "").replace("}", "").strip()


def _field(entry: str, name: str) -> str:
    pattern = re.compile(rf"\b{re.escape(name)}\s*=\s*", re.IGNORECASE)
    match = pattern.search(entry)
    if not match:
        return ""
    pos = match.end()
    while pos < len(entry) and entry[pos].isspace():
        pos += 1
    if pos >= len(entry):
        return ""
    if entry[pos] in {'"', "{"}:
        quote = entry[pos]
        close = '"' if quote == '"' else "}"
        start = pos + 1
        if quote == "{":
            depth = 1
            for idx in range(pos + 1, len(entry)):
                char = entry[idx]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return _clean_value(entry[start:idx])
        else:
            for idx in range(pos + 1, len(entry)):
                char = entry[idx]
                if char == close:
                    return _clean_value(entry[start:idx])
        return ""
    end = entry.find(",", pos)
    if end < 0:
        end = len(entry)
    return _clean_value(entry[pos:end])


def _parse_bib_files(root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for path in sorted(root.rglob("*.bib")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for _, entry in _iter_entries(text):
            comma = entry.find(",")
            bibkey = entry[:comma].strip() if comma >= 0 else ""
            body = entry[comma + 1 :] if comma >= 0 else entry
            title = _field(body, "title")
            if not title:
                continue
            records.append(
                {
                    "title": title,
                    "year": _field(body, "year"),
                    "authors": _field(body, "author"),
                    "bibkey": bibkey,
                    "source_bib": str(path.relative_to(root)),
                }
            )
    return records


def _write_tsv(path: Path, records: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("title\tyear\tauthors\tbibkey\tsource_bib\n")
        for record in records:
            row = [record.get(key, "").replace("\t", " ").strip() for key in ["title", "year", "authors", "bibkey", "source_bib"]]
            handle.write("\t".join(row) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract BibTeX reference titles from an arXiv source archive.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--candidate-json", type=Path)
    source.add_argument("--arxiv-id")
    source.add_argument("--source-archive", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="Output TSV path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="paper_engine_refs_") as tmp:
        tmp_path = Path(tmp)
        if args.source_archive:
            archive_path = args.source_archive
            arxiv_id = ""
        else:
            arxiv_id = args.arxiv_id or _candidate_arxiv_id(_load_candidate(args.candidate_json))
            if not arxiv_id:
                raise SystemExit("candidate has no arXiv ID or arXiv URL; reference expansion needs arXiv source")
            archive_path = tmp_path / "source.tar"
            _download_source(arxiv_id, archive_path)

        extract_dir = tmp_path / "source"
        extract_dir.mkdir()
        _extract_archive(archive_path, extract_dir)
        records = _parse_bib_files(extract_dir)
        if not records:
            raise SystemExit("no .bib files with titles found in arXiv source")
        _write_tsv(args.out, records)

    print(json.dumps({"ok": True, "out": str(args.out), "count": len(records), "arxiv_id": arxiv_id}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
