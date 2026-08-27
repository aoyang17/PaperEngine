#!/usr/bin/env python3
from __future__ import annotations

import argparse
import binascii
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from paper_engine.candidates import append_candidates, load_candidates  # noqa: E402
from paper_engine.topic import init_topic  # noqa: E402
from paper_engine.web_app import WebApp  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Check server-rendered workbench pages.")
    parser.add_argument("--root", required=True, help="Topic root to render; initialized if missing")
    parser.add_argument("--out", default=".tmp/render-checks", help="Directory for HTML artifacts")
    args = parser.parse_args()

    topic_root = Path(args.root).expanduser().resolve()
    if not (topic_root / "topic.yml").exists():
        init_topic(topic_root, "Render Check", "web render verification")
    _ensure_sample_candidates(topic_root)
    _ensure_sample_paper(topic_root)
    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    app = WebApp(topic_root)
    bootstrap_app = WebApp(base_dir=out / "bootstrap-parent")
    checks = {
        "dashboard-desktop.png": ("/dashboard.html", 1440, 900),
        "candidates-desktop.png": ("/candidates.html", 1440, 900),
        "library-desktop.png": ("/library.html", 1440, 900),
        "paper-detail-desktop.png": ("/papers/Render2026Check.html", 1440, 900),
        "dashboard-mobile.png": ("/dashboard.html", 390, 844),
    }
    bootstrap_checks = {
        "bootstrap-desktop.png": ("/dashboard.html", 1440, 900),
        "bootstrap-mobile.png": ("/dashboard.html", 390, 844),
    }
    failures: list[str] = []
    for name, (route, width, height) in checks.items():
        response = app.handle(route)
        if response.status != 200 or len(response.body) < 300 or "Traceback" in response.body:
            failures.append(route)
        (out / f"{name.removesuffix('.png')}.html").write_text(response.body, encoding="utf-8")
        _write_png(out / name, width, height, response.body)
    for name, (route, width, height) in bootstrap_checks.items():
        response = bootstrap_app.handle(route)
        if response.status != 200 or "Create Topic" not in response.body or "Traceback" in response.body:
            failures.append(f"bootstrap:{route}")
        (out / f"{name.removesuffix('.png')}.html").write_text(response.body, encoding="utf-8")
        _write_png(out / name, width, height, response.body)
    if failures:
        print({"ok": False, "failures": failures, "out": str(out)})
        return 1
    print({"ok": True, "out": str(out), "pages": len(checks) + len(bootstrap_checks)})
    return 0


def _ensure_sample_paper(topic_root: Path) -> None:
    library = topic_root / "library.bib"
    text = library.read_text(encoding="utf-8") if library.exists() else ""
    if "Render2026Check" not in text:
        with library.open("a", encoding="utf-8") as handle:
            handle.write(
                """
@article{Render2026Check,
  author = {Render, Ada},
  title = {Render Check Paper},
  year = {2026},
  journal = {Render Venue},
  doi = {10.1000/render-check},
}
"""
            )
    paper_dir = topic_root / "papers" / "Render2026Check"
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    (paper_dir / "note.md").write_text("# Render Check Paper\n", encoding="utf-8")


def _ensure_sample_candidates(topic_root: Path) -> None:
    if load_candidates(topic_root):
        return
    append_candidates(
        topic_root,
        [
            {
                "title": "Render Candidate Queue",
                "authors": ["Ada Render"],
                "year": 2026,
                "venue": "arXiv",
                "abstract": "A candidate used to verify abstract expansion and queue display.",
                "source": "arxiv",
                "status": "new",
                "score": 0.72,
            },
            {
                "title": "Render Candidate Relevant",
                "authors": ["Grace Render"],
                "year": 2025,
                "venue": "ICLR",
                "abstract": "A relevant candidate used to verify preference highlighting.",
                "source": "crossref",
                "status": "relevant",
                "decision": "relevant",
                "score": 0.88,
            },
            {
                "title": "Render Candidate Dismissed",
                "authors": ["Katherine Render"],
                "year": 2024,
                "venue": "Workshop",
                "abstract": "A dismissed candidate used to verify the neutral dismiss button.",
                "source": "openalex",
                "status": "dismissed",
                "decision": "dismissed",
                "score": 0.1,
            },
        ],
    )


def _write_png(path: Path, width: int, height: int, body: str) -> None:
    # Dependency-free viewport artifact: colored bands encode route health and content size.
    palette = [(246, 247, 249), (31, 41, 51), (217, 222, 231), (15, 118, 110)]
    rows = []
    body_factor = min(max(len(body) // 200, 1), 20)
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            if y < 48:
                color = palette[1]
            elif x < body_factor * 12 and y < 140:
                color = palette[3]
            elif (x // 160 + y // 80) % 2 == 0:
                color = palette[0]
            else:
                color = palette[2]
            row.extend(color)
        rows.append(bytes(row))
    compressed = zlib.compress(b"".join(rows), level=9)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00")
        + _chunk(b"IDAT", compressed)
        + _chunk(b"IEND", b"")
    )


def _chunk(kind: bytes, data: bytes) -> bytes:
    return len(data).to_bytes(4, "big") + kind + data + (binascii.crc32(kind + data) & 0xFFFFFFFF).to_bytes(4, "big")


if __name__ == "__main__":
    raise SystemExit(main())
