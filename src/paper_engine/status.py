from __future__ import annotations

from pathlib import Path

from .acquire import check_pdfs
from .bib import parse_bibtex
from .candidates import load_candidates
from .citation_guard import check_bib
from .paths import TopicPaths


def topic_status(root: str | Path) -> dict[str, object]:
    paths = TopicPaths.from_root(root)
    candidates = load_candidates(root) if paths.candidates_jsonl.exists() else []
    papers = parse_bibtex(paths.library_bib) if paths.library_bib.exists() else []
    bib = check_bib(root) if paths.library_bib.exists() else {"ok": True, "entries": 0, "errors": []}
    pdf = check_pdfs(root) if paths.papers.exists() else {"ok": True, "pdfs": 0, "errors": []}
    read_papers = 0
    for paper in papers:
        bibkey = str(paper.get("bibkey") or "")
        paper_dir = paths.paper_dir(bibkey)
        if (
            (paper_dir / "note.md").exists()
            or (paper_dir / "deep_read.json").exists()
            or (paper_dir / "reading_result.html").exists()
            or (paths.html / "papers" / f"{bibkey}.html").exists()
        ):
            read_papers += 1
    return {
        "ok": bib["ok"] and pdf["ok"],
        "root": str(paths.root),
        "total_papers": len(papers),
        "candidates": len(candidates),
        "candidate_queue": sum(1 for candidate in candidates if candidate.get("status") == "new"),
        "unscored_candidates": sum(1 for candidate in candidates if candidate.get("score_status") != "scored"),
        "papers": len(papers),
        "pdfs": pdf["pdfs"],
        "read_papers": read_papers,
        "bib_ok": bib["ok"],
        "pdf_ok": pdf["ok"],
        "errors": list(bib.get("errors", [])) + list(pdf.get("errors", [])),
    }
