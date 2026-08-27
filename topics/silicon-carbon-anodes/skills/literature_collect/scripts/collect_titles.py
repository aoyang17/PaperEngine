#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def _clean_title(line: str) -> str:
    text = line.strip()
    text = re.sub(r"^\s*[-*]\s+", "", text)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text)
    return text.strip().strip('"').strip()


def _read_titles(path: Path) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        title = _clean_title(line)
        if not title or title.startswith("#"):
            continue
        key = re.sub(r"\s+", " ", title).casefold()
        if key in seen:
            continue
        seen.add(key)
        titles.append(title)
    return titles


def _run(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    payload: dict = {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    try:
        parsed = json.loads(proc.stdout)
        if isinstance(parsed, dict):
            payload["json"] = parsed
    except json.JSONDecodeError:
        pass
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect a batch of exact paper titles using paper_engine collect.")
    parser.add_argument("--root", required=True, help="Topic repository root.")
    parser.add_argument("--titles-file", type=Path, required=True, help="One paper title per line.")
    parser.add_argument("--target-new", type=int, default=1, help="Candidates to add per exact title.")
    parser.add_argument("--paper-engine", default=os.environ.get("PAPER_ENGINE_BIN", "paper_engine"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    titles = _read_titles(args.titles_file)
    results: list[dict] = []
    total_added = 0
    failures = 0

    for title in titles:
        cmd = [
            args.paper_engine,
            "collect",
            "--root",
            args.root,
            "--query",
            f'"{title}"',
            "--target-new",
            str(args.target_new),
        ]
        result = _run(cmd)
        added = 0
        if isinstance(result.get("json"), dict):
            added = int(result["json"].get("added") or 0)
        total_added += added
        if result["returncode"] != 0:
            failures += 1
        results.append({"title": title, "added": added, "returncode": result["returncode"], "stderr": result["stderr"].strip()})

    dedup = _run([args.paper_engine, "tool", "dedup", "--root", args.root, "--fix", "--json"])
    summary = {
        "ok": failures == 0 and dedup["returncode"] == 0,
        "titles_seen": len(titles),
        "total_added": total_added,
        "failures": failures,
        "dedup_returncode": dedup["returncode"],
        "results": results,
    }
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"titles={len(titles)} added={total_added} failures={failures} dedup={dedup['returncode']}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
