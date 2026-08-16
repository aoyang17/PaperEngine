from __future__ import annotations

from pathlib import Path
from typing import Any

from .candidates import get_candidate, update_candidate
from .paths import TopicPaths
from .pdf import arxiv_pdf_url, copy_pdf, download_pdf, is_pdf


def acquire_pdf(root: str | Path, candidate_id: str, manual_pdf: str | Path | None = None) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    candidate = get_candidate(root, candidate_id)
    if candidate.get("bibkey"):
        final_pdf = paths.paper_dir(candidate["bibkey"]) / "paper.pdf"
        if is_pdf(final_pdf):
            return {"ok": True, "candidate_id": candidate_id, "status": "skipped_existing", "pdf": str(final_pdf)}
    paths.incoming.mkdir(parents=True, exist_ok=True)
    target = paths.incoming / f"{candidate_id}.pdf"

    if target.exists() and is_pdf(target):
        return {"ok": True, "candidate_id": candidate_id, "status": "skipped_existing", "pdf": str(target)}

    if manual_pdf:
        copy_pdf(manual_pdf, target)
        update_candidate(root, candidate_id, status="downloaded")
        return {"ok": True, "candidate_id": candidate_id, "status": "downloaded", "pdf": str(target)}

    url = candidate.get("pdf_url")
    if not url and candidate.get("arxiv_id"):
        url = arxiv_pdf_url(candidate["arxiv_id"])
    if not url:
        update_candidate(root, candidate_id, status="manual_pdf_needed")
        return {"ok": False, "candidate_id": candidate_id, "status": "manual_pdf_needed", "error": "no open PDF URL"}

    try:
        download_pdf(str(url), target)
    except Exception as exc:
        update_candidate(root, candidate_id, status="manual_pdf_needed")
        return {"ok": False, "candidate_id": candidate_id, "status": "manual_pdf_needed", "error": str(exc)}
    update_candidate(root, candidate_id, status="downloaded")
    return {"ok": True, "candidate_id": candidate_id, "status": "downloaded", "pdf": str(target)}


def check_pdfs(root: str | Path) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    errors: list[str] = []
    count = 0
    for pdf in paths.papers.glob("*/paper.pdf"):
        count += 1
        if not is_pdf(pdf):
            errors.append(str(pdf.relative_to(paths.root)))
    for pdf in paths.incoming.glob("*.pdf") if paths.incoming.exists() else []:
        count += 1
        if not is_pdf(pdf):
            errors.append(str(pdf.relative_to(paths.root)))
    return {"ok": not errors, "pdfs": count, "errors": errors}
