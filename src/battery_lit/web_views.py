from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .bib import list_library
from .candidates import load_candidates
from .paths import TopicPaths, repo_root
from .pdf import is_pdf
from .status import topic_status
from .topic import load_topic


READING_RESULT_NAME = "reading_result.html"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(repo_root() / "templates" / "web")),
        autoescape=select_autoescape(["html"]),
    )


def _job_state_dir(root: str | Path, state_dir: str | Path | None = None) -> Path:
    return Path(state_dir).expanduser().resolve() if state_dir else TopicPaths.from_root(root).root / ".battery"


def active_job(root: str | Path, state_dir: str | Path | None = None) -> dict[str, Any] | None:
    path = _job_state_dir(root, state_dir) / "active_job.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    except json.JSONDecodeError:
        return {"job_id": "unknown", "action": "invalid active job file"}
    return data if isinstance(data, dict) else None


def recent_jobs(root: str | Path, limit: int = 5, state_dir: str | Path | None = None) -> list[dict[str, Any]]:
    path = _job_state_dir(root, state_dir) / "jobs.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            rows.append(data)
    return rows[-limit:][::-1]


def job_detail(root: str | Path, job_id: str, state_dir: str | Path | None = None) -> dict[str, Any] | None:
    job_dir = _job_state_dir(root, state_dir) / "jobs" / job_id
    summary = job_dir / "summary.json"
    if not summary.exists():
        return None
    try:
        data = json.loads(summary.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"job_id": job_id, "ok": False, "error": "invalid summary.json"}
    return data if isinstance(data, dict) else {"job_id": job_id, "ok": False, "error": "invalid summary.json"}


def job_events(root: str | Path, job_id: str, limit: int = 200, state_dir: str | Path | None = None) -> list[dict[str, Any]] | None:
    job_dir = _job_state_dir(root, state_dir) / "jobs" / job_id
    events_path = job_dir / "events.jsonl"
    if not events_path.exists():
        return None
    rows: list[dict[str, Any]] = []
    for line in _tail_lines(events_path, limit=max(limit, 0)):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            rows.append(data)
    return rows


def _tail_lines(path: Path, limit: int, max_bytes: int = 1_000_000, chunk_size: int = 8192) -> list[str]:
    if limit <= 0:
        return []
    size = path.stat().st_size
    if size == 0:
        return []
    remaining = min(size, max_bytes)
    chunks: list[bytes] = []
    newline_count = 0
    with path.open("rb") as handle:
        while remaining > 0 and newline_count <= limit:
            read_size = min(chunk_size, remaining)
            remaining -= read_size
            handle.seek(size - (min(size, max_bytes) - remaining))
            chunk = handle.read(read_size)
            chunks.append(chunk)
            newline_count += chunk.count(b"\n")
    data = b"".join(reversed(chunks))
    return data.decode("utf-8", errors="replace").splitlines()[-limit:]


def web_context(root: str | Path) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    topic = load_topic(paths.root)
    raw_candidates = load_candidates(paths.root) if paths.candidates_jsonl.exists() else []
    candidates = [_candidate_view(paths.root, candidate) for candidate in raw_candidates]
    papers = _library_view(paths.root)
    _attach_candidate_modules(papers, raw_candidates)
    status = topic_status(paths.root)
    research_modules = _research_module_views(topic, raw_candidates, papers)
    research_module_by_id = {str(module.get("id")): module for module in research_modules}
    return {
        "root": str(paths.root),
        "title": topic.get("title") or paths.root.name,
        "direction": topic.get("direction") or "",
        "scope_guidance": topic.get("scope_guidance") or {},
        "status": status,
        "candidates": candidates,
        "papers": papers,
        "research_modules": research_modules,
        "research_module_by_id": research_module_by_id,
        "cross_module_papers": _cross_module_paper_views(candidates, papers),
        "candidate_years": sorted({str(item.get("year")) for item in candidates if item.get("year")}, reverse=True),
        "candidate_venues": sorted({str(item.get("venue")) for item in candidates if item.get("venue")}),
        "candidate_sources": sorted({str(item.get("source")) for item in candidates if item.get("source")}),
        "active_job": active_job(paths.root),
        "recent_jobs": recent_jobs(paths.root),
        "sandbox_warning": codex_sandbox_warning(),
        "bootstrap_mode": False,
    }


def _research_module_views(
    topic: dict[str, Any], candidates: list[dict[str, Any]], papers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    paper_by_bibkey = {str(paper.get("bibkey") or ""): paper for paper in papers}
    views: list[dict[str, Any]] = []
    for module in topic.get("research_modules") or []:
        if not isinstance(module, dict) or not module.get("id"):
            continue
        module_id = str(module["id"])
        matches = [
            candidate
            for candidate in candidates
            if module_id in {str(value) for value in candidate.get("module_ids") or []}
        ]
        library_matches = [candidate for candidate in matches if candidate.get("status") == "in_library"]
        read_count = sum(
            1
            for candidate in library_matches
            if paper_by_bibkey.get(str(candidate.get("bibkey") or ""), {}).get("has_knowledge")
        )
        view = dict(module)
        view.update(
            {
                "candidate_count": len(matches),
                "library_count": len(library_matches),
                "read_count": read_count,
                "coverage_percent": round((read_count / len(library_matches)) * 100) if library_matches else 0,
            }
        )
        views.append(view)
    return sorted(views, key=lambda item: (int(item.get("order") or 999), str(item.get("id"))))


def _attach_candidate_modules(papers: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> None:
    modules_by_bibkey: dict[str, set[str]] = {}
    for candidate in candidates:
        bibkey = str(candidate.get("bibkey") or "")
        if not bibkey:
            continue
        modules_by_bibkey.setdefault(bibkey, set()).update(str(value) for value in candidate.get("module_ids") or [])
    for paper in papers:
        module_ids = sorted(modules_by_bibkey.get(str(paper.get("bibkey") or ""), set()))
        paper["module_ids"] = module_ids
        paper["cross_module"] = len(module_ids) > 1


def _cross_module_paper_views(candidates: list[dict[str, Any]], papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    paper_by_bibkey = {str(paper.get("bibkey") or ""): paper for paper in papers}
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        module_ids = list(candidate.get("module_ids") or [])
        if len(module_ids) < 2:
            continue
        row = dict(candidate)
        paper = paper_by_bibkey.get(str(candidate.get("bibkey") or ""), {})
        row["has_knowledge"] = bool(paper.get("has_knowledge"))
        rows.append(row)
    return sorted(rows, key=lambda item: (-float(item.get("score") or 0.0), str(item.get("title") or "")))[:12]


def _candidate_view(root: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    view = dict(candidate)
    candidate_id = str(view.get("candidate_id") or "")
    bibkey = str(view.get("bibkey") or "")

    if bibkey:
        final_pdf = paths.paper_dir(bibkey) / "paper.pdf"
        if is_pdf(final_pdf):
            view["has_pdf"] = True
            view["pdf_href"] = f"/papers/{bibkey}/paper.pdf"
            return view

    if candidate_id:
        incoming_pdf = paths.incoming / f"{candidate_id}.pdf"
        if is_pdf(incoming_pdf):
            view["has_pdf"] = True
            view["pdf_href"] = f"/incoming/{candidate_id}.pdf"
            return view

    view["has_pdf"] = False
    view["pdf_href"] = ""
    return view


def _library_view(root: Path) -> list[dict[str, Any]]:
    paths = TopicPaths.from_root(root)
    papers = list_library(paths.root)
    for paper in papers:
        bibkey = str(paper.get("bibkey") or "")
        paper_dir = paths.paper_dir(bibkey)
        pdf = paper_dir / "paper.pdf"
        note = paper_dir / "note.md"
        deep_read = paper_dir / "deep_read.json"
        reading_result = paper_dir / READING_RESULT_NAME
        paper["has_pdf"] = pdf.exists()
        paper["pdf_href"] = f"/papers/{bibkey}/paper.pdf" if pdf.exists() else ""
        paper["has_knowledge"] = note.exists() or deep_read.exists()
        paper["knowledge_href"] = f"/papers/{bibkey}/{READING_RESULT_NAME}" if paper["has_knowledge"] else ""
    return papers


def render_web_page(root: str | Path, page: str) -> str:
    page_name = page.removesuffix(".html").strip("/") or "dashboard"
    if page_name.startswith("papers/"):
        paper_path = page_name.split("/", 1)[1]
        bibkey = paper_path.removesuffix(".html").split("/", 1)[0]
        context = web_context(root)
        paper = next((item for item in context["papers"] if item.get("bibkey") == bibkey), None)
        if not paper:
            raise KeyError(f"unknown paper: {bibkey}")
        return _env().get_template("paper.html").render(**context, paper=paper)
    templates = {
        "dashboard": "dashboard.html",
        "candidates": "candidates.html",
        "library": "library.html",
    }
    template_name = templates.get(page_name)
    if not template_name:
        raise KeyError(f"unknown web page: {page}")
    return _env().get_template(template_name).render(**web_context(root))


def render_bootstrap_page(base_dir: str | Path, state_dir: str | Path) -> str:
    base = Path(base_dir).expanduser().resolve()
    return _env().get_template("bootstrap.html").render(
        title="Create Topic",
        direction="",
        base_dir=str(base),
        active_job=active_job(base, state_dir=state_dir),
        recent_jobs=recent_jobs(base, state_dir=state_dir),
        sandbox_warning=codex_sandbox_warning(),
        bootstrap_mode=True,
    )


@lru_cache(maxsize=1)
def codex_sandbox_warning() -> str:
    if os.environ.get("BATTERY_LIT_HIDE_SANDBOX_WARNING"):
        return ""
    if not shutil.which("unshare"):
        return ""
    try:
        proc = subprocess.run(["unshare", "-U", "true"], text=True, capture_output=True, timeout=2, check=False)
    except Exception as exc:
        return f"Codex sandbox preflight could not run: {exc}"
    if proc.returncode == 0:
        return ""
    reason = (proc.stderr or proc.stdout or "user namespace is unavailable").strip()
    return (
        "Codex sandbox namespace is unavailable in this container; Codex may need approval/escalation for file "
        f"inspection and image-view steps. Detail: {reason}"
    )
