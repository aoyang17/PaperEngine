from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import threading
import uuid
from urllib.parse import parse_qs, unquote, urlparse

from .acquire import acquire_pdf
from .bib import promote_candidate
from .codex_session import AppServerCodexSessionManager, CodexSessionManager
from .codex_worker import CodexRunner
from .candidates import mark_candidate
from .html import build_html
from .jobs import JobAlreadyActive, JobManager
from .metadata import enrich_candidate
from .preferences import mark_candidate_with_feedback
from .paths import TopicPaths, repo_root
from .prompt_contracts import (
    acquire_candidate_task,
    build_bootstrap_init_prompt,
    chat_task,
    collect_candidates_task,
    dismiss_candidate_task,
    health_check_task,
    html_build_task,
    mark_candidate_task,
    read_paper_task,
    score_candidates_task,
)
from .topic import init_topic, root_from_title
from .web_views import active_job, job_detail, job_events, recent_jobs, render_bootstrap_page, render_web_page
from .status import topic_status

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
SAFE_JOB_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$")
SAFE_QUERY_RE = re.compile(r"^[^\n\r`$]{0,500}$")
ALLOWED_CODEX_MODELS = {
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-5.5",
    "gpt-5.3-codex-spark",
}
ALLOWED_CODEX_EFFORTS = {"low", "medium", "high", "xhigh"}


@dataclass(frozen=True)
class WebResponse:
    status: int
    body: str | bytes
    content_type: str = "text/html; charset=utf-8"


class WebApp:
    def __init__(
        self,
        topic_root: str | Path | None = None,
        runner: CodexRunner | None = None,
        project_root: str | Path | None = None,
        base_dir: str | Path | None = None,
        session_manager: CodexSessionManager | None = None,
    ) -> None:
        self.topic_root = Path(topic_root).expanduser().resolve() if topic_root is not None else None
        self.base_dir = Path(base_dir).expanduser().resolve() if base_dir is not None else None
        self.runner = runner
        self.project_root = Path(project_root).expanduser().resolve() if project_root else None
        self.session_manager = session_manager
        self._session_manager_lock = threading.Lock()
        self.pending_init: dict[str, object] | None = None

    def handle(self, raw_path: str, method: str = "GET", body: str = "") -> WebResponse:
        parsed = urlparse(raw_path)
        path = parsed.path
        bound_root = self._maybe_bind_bootstrap_topic()
        if method.upper() == "GET" and path == "/api/status":
            if not self.topic_root:
                return _json_response(409, {"ok": False, "error": "topic is not initialized yet"})
            return _json_response(200, topic_status(self.topic_root))
        if method.upper() == "GET" and path == "/api/jobs":
            payload = {
                "active_job": active_job(self._job_root(), state_dir=self._job_state_dir()),
                "recent_jobs": recent_jobs(self._job_root(), state_dir=self._job_state_dir()),
            }
            if bound_root:
                payload["bound_root"] = str(bound_root)
                payload["redirect"] = "/dashboard.html"
            return _json_response(200, payload)
        if method.upper() == "POST" and path == "/api/session/start":
            return self._session_start_action(body)
        if method.upper() == "GET" and path == "/api/session/state":
            return self._session_state_action()
        if method.upper() == "GET" and path == "/api/session/transcript":
            return self._session_transcript_action()
        if method.upper() == "GET" and path == "/api/session/events":
            return self._session_events_action(parsed.query)
        if method.upper() == "POST" and path == "/api/session/message":
            return self._session_message_action(body)
        if method.upper() == "POST" and path == "/api/session/action":
            return self._session_action_action(body)
        if method.upper() == "POST" and path == "/api/session/stop":
            return self._session_stop_action()
        if method.upper() == "GET" and path.startswith("/api/jobs/"):
            return self._job_api(path)
        if method.upper() == "POST" and path == "/api/codex/init-topic":
            return self._bootstrap_init_action(body)
        if not self.topic_root and method.upper() == "POST" and path.startswith(("/api/codex/", "/actions/")):
            return _json_response(409, {"ok": False, "error": "topic is not initialized yet"})
        if method.upper() == "POST" and path == "/actions/collect":
            return self._collect_action(body)
        if method.upper() == "POST" and path == "/api/codex/search":
            return self._collect_action(body)
        if method.upper() == "POST" and path == "/api/codex/candidates/score":
            return self._candidate_score_action(body)
        if method.upper() == "POST" and path == "/api/codex/health-check":
            return self._health_check_action(body)
        if method.upper() == "POST" and path == "/api/codex/html-build":
            return self._html_build_action(body)
        if method.upper() == "POST" and path == "/api/codex/chat":
            return self._chat_action(body)
        if method.upper() == "POST" and path == "/actions/candidate/mark":
            return self._candidate_mark_action(body)
        if method.upper() == "POST" and path == "/api/codex/candidates/mark":
            return self._candidate_mark_action(body)
        if method.upper() == "POST" and path == "/api/codex/candidates/dismiss":
            return self._candidate_dismiss_action(body)
        if method.upper() == "POST" and path == "/api/codex/candidates/download":
            return self._candidate_acquire_action(body)
        if method.upper() == "POST" and path == "/actions/candidate/acquire":
            return self._candidate_acquire_action(body)
        if method.upper() == "POST" and path == "/actions/library/read":
            return self._library_read_action(body)
        if method.upper() == "POST" and path == "/api/codex/library/read":
            return self._library_read_action(body)
        if method.upper() == "POST" and path == "/api/codex/library/rebuild-html":
            return self._library_rebuild_html_action(body)
        if not self.topic_root and self.base_dir and path in {"/", "/dashboard", "/dashboard.html", "/candidates", "/candidates.html", "/library", "/library.html"}:
            return WebResponse(200, render_bootstrap_page(self.base_dir, self._job_state_dir()))
        if not self.topic_root and self.base_dir and path.startswith("/papers/") and path.endswith(".html"):
            return WebResponse(200, render_bootstrap_page(self.base_dir, self._job_state_dir()))
        if path in {"/", "/dashboard", "/dashboard.html"}:
            assert self.topic_root is not None
            return WebResponse(200, render_web_page(self.topic_root, "dashboard"))
        if path in {"/candidates", "/candidates.html"}:
            assert self.topic_root is not None
            return WebResponse(200, render_web_page(self.topic_root, "candidates"))
        if path in {"/library", "/library.html"}:
            assert self.topic_root is not None
            return WebResponse(200, render_web_page(self.topic_root, "library"))
        if path.startswith("/papers/") and path.endswith(".html") and len(path.strip("/").split("/")) == 2:
            assert self.topic_root is not None
            try:
                return WebResponse(200, render_web_page(self.topic_root, path.strip("/")))
            except KeyError:
                return WebResponse(404, "Not found", "text/plain; charset=utf-8")
        if method.upper() == "GET" and path.startswith("/papers/"):
            asset_response = self._paper_asset(path)
            if asset_response is not None:
                return asset_response
        if method.upper() == "GET" and path.startswith("/incoming/"):
            incoming_response = self._incoming_asset(path)
            if incoming_response is not None:
                return incoming_response
        if method.upper() == "GET" and path.startswith("/html/"):
            html_response = self._html_asset(path)
            if html_response is not None:
                return html_response
        if path == "/static/style.css":
            body = (repo_root() / "templates" / "web" / "static" / "style.css").read_text(encoding="utf-8")
            return WebResponse(200, body, "text/css; charset=utf-8")
        if path == "/static/app.js":
            body = (repo_root() / "templates" / "web" / "static" / "app.js").read_text(encoding="utf-8")
            return WebResponse(200, body, "application/javascript; charset=utf-8")
        return WebResponse(404, "Not found", "text/plain; charset=utf-8")

    def _job_root(self) -> Path:
        if self.topic_root:
            return self.topic_root
        if self.base_dir:
            return self.base_dir
        raise RuntimeError("topic root or base dir is required")

    def _job_state_dir(self) -> Path | None:
        if self.topic_root:
            return None
        if self.base_dir:
            return self.base_dir / ".battery_serverlet"
        return None

    def _paper_asset(self, path: str) -> WebResponse | None:
        if not self.topic_root:
            return WebResponse(409, "topic is not initialized yet", "text/plain; charset=utf-8")
        parts = path.strip("/").split("/")
        if len(parts) < 2 or parts[0] != "papers" or not _safe_id(parts[1]):
            return WebResponse(404, "Not found", "text/plain; charset=utf-8")
        if len(parts) == 2 and parts[1].endswith(".html") and _safe_id(parts[1].removesuffix(".html")):
            return WebResponse(200, render_web_page(self.topic_root, path.strip("/")))
        if len(parts) < 3:
            return None
        rel_parts = parts[2:]
        if any(part in {"", ".", ".."} or "/" in part or "\\" in part for part in rel_parts):
            return WebResponse(404, "Not found", "text/plain; charset=utf-8")
        allowed = {
            ("paper.pdf",): "application/pdf",
            ("note.md",): "text/markdown; charset=utf-8",
            ("parsed.md",): "text/markdown; charset=utf-8",
            ("visual_index.md",): "text/markdown; charset=utf-8",
            ("reading_result.html",): "text/html; charset=utf-8",
        }
        content_type = allowed.get(tuple(rel_parts))
        if content_type is None and len(rel_parts) == 2 and rel_parts[0] == "page_images":
            content_type = _image_content_type(rel_parts[1])
        if content_type is None and len(rel_parts) == 2 and rel_parts[0] == "math_pages":
            content_type = _image_content_type(rel_parts[1])
        if content_type is None:
            return WebResponse(404, "Not found", "text/plain; charset=utf-8")
        asset = TopicPaths.from_root(self.topic_root).paper_dir(parts[1]).joinpath(*rel_parts)
        root = TopicPaths.from_root(self.topic_root).paper_dir(parts[1]).resolve()
        try:
            asset.resolve().relative_to(root)
        except ValueError:
            return WebResponse(404, "Not found", "text/plain; charset=utf-8")
        if not asset.exists() or not asset.is_file():
            return WebResponse(404, "Not found", "text/plain; charset=utf-8")
        if content_type.startswith(("text/", "application/javascript")):
            return WebResponse(200, asset.read_text(encoding="utf-8"), content_type)
        return WebResponse(200, asset.read_bytes(), content_type)

    def _incoming_asset(self, path: str) -> WebResponse | None:
        if not self.topic_root:
            return WebResponse(409, "topic is not initialized yet", "text/plain; charset=utf-8")
        parts = path.strip("/").split("/")
        if len(parts) != 2 or parts[0] != "incoming" or not parts[1].endswith(".pdf"):
            return WebResponse(404, "Not found", "text/plain; charset=utf-8")
        candidate_id = parts[1].removesuffix(".pdf")
        if not _safe_id(candidate_id):
            return WebResponse(404, "Not found", "text/plain; charset=utf-8")
        asset = TopicPaths.from_root(self.topic_root).incoming / f"{candidate_id}.pdf"
        if not asset.exists() or not asset.is_file():
            return WebResponse(404, "Not found", "text/plain; charset=utf-8")
        return WebResponse(200, asset.read_bytes(), "application/pdf")

    def _html_asset(self, path: str) -> WebResponse | None:
        if not self.topic_root:
            return WebResponse(409, "topic is not initialized yet", "text/plain; charset=utf-8")
        name = path.removeprefix("/html/")
        if name == "style.css":
            candidates = [
                TopicPaths.from_root(self.topic_root).html / "style.css",
                repo_root() / "templates" / "html" / "style.css",
            ]
            for css_path in candidates:
                if css_path.exists() and css_path.is_file():
                    return WebResponse(200, css_path.read_text(encoding="utf-8"), "text/css; charset=utf-8")
            return WebResponse(404, "Not found", "text/plain; charset=utf-8")
        page_map = {
            "dashboard.html": "dashboard",
            "candidates.html": "candidates",
            "library.html": "library",
        }
        page = page_map.get(name)
        if page is None:
            return WebResponse(404, "Not found", "text/plain; charset=utf-8")
        static_page = TopicPaths.from_root(self.topic_root).html / name
        if static_page.exists() and static_page.is_file():
            return WebResponse(200, static_page.read_text(encoding="utf-8"), "text/html; charset=utf-8")
        return WebResponse(200, render_web_page(self.topic_root, page), "text/html; charset=utf-8")

    def _session(self) -> CodexSessionManager:
        if self.session_manager is None:
            with self._session_manager_lock:
                if self.session_manager is None:
                    self.session_manager = AppServerCodexSessionManager(project_root=self.project_root or repo_root())
        return self.session_manager

    def _maybe_bind_bootstrap_topic(self) -> Path | None:
        if self.topic_root or not self.base_dir or not self.pending_init:
            return None
        job_id = str(self.pending_init.get("job_id") or "")
        expected = Path(str(self.pending_init.get("expected_root") or "")).expanduser().resolve()
        summary_path = self.base_dir / ".battery_serverlet" / "jobs" / job_id / "summary.json"
        if not summary_path.exists():
            return None
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if not summary.get("ok"):
            return None
        try:
            resolved_base = self.base_dir.resolve()
            resolved_expected = expected.resolve()
            resolved_expected.relative_to(resolved_base)
        except ValueError:
            return None
        required = ["topic.yml", "policy.yml", "preferences.yml"]
        if not all((resolved_expected / name).exists() for name in required):
            return None
        self.topic_root = resolved_expected
        self.pending_init = None
        return resolved_expected

    def _collect_action(self, body: str) -> WebResponse:
        params = parse_qs(body, keep_blank_values=True)
        options = _codex_options(params)
        if isinstance(options, WebResponse):
            return options
        target_new = _int_param(params, "target_new", 20)
        score_threshold = _float_param(params, "score_threshold")
        query = _text_param(params, "query")
        if query and not SAFE_QUERY_RE.match(query):
            return _json_response(400, {"ok": False, "error": "query contains unsupported characters"})
        task = collect_candidates_task(target_new=target_new, score_threshold=score_threshold, query=query)
        return self._run_job(task, action="collect", codex_model=options[0], codex_effort=options[1])

    def _candidate_score_action(self, body: str) -> WebResponse:
        params = parse_qs(body, keep_blank_values=True)
        options = _codex_options(params)
        if isinstance(options, WebResponse):
            return options
        limit = _int_param(params, "limit", 20)
        return self._run_job(score_candidates_task(limit=limit), action="candidate-score", codex_model=options[0], codex_effort=options[1])

    def _health_check_action(self, body: str) -> WebResponse:
        params = parse_qs(body, keep_blank_values=True)
        options = _codex_options(params)
        if isinstance(options, WebResponse):
            return options
        return self._run_job(health_check_task(), action="health-check", codex_model=options[0], codex_effort=options[1])

    def _html_build_action(self, body: str) -> WebResponse:
        params = parse_qs(body, keep_blank_values=True)
        options = _codex_options(params)
        if isinstance(options, WebResponse):
            return options
        bibkey = _text_param(params, "bibkey")
        if bibkey and not _safe_id(bibkey):
            return _json_response(400, {"ok": False, "error": "bibkey is invalid"})
        return self._run_job(html_build_task(bibkey), action="html-build", codex_model=options[0], codex_effort=options[1])

    def _chat_action(self, body: str) -> WebResponse:
        params = parse_qs(body, keep_blank_values=True)
        options = _codex_options(params)
        if isinstance(options, WebResponse):
            return options
        message = _text_param(params, "message")
        if not _safe_chat_message(message):
            return _json_response(400, {"ok": False, "error": "message contains unsupported characters"})
        return self._run_job(chat_task(message), action="chat", codex_model=options[0], codex_effort=options[1])

    def _bootstrap_init_action(self, body: str) -> WebResponse:
        if self.topic_root:
            return _json_response(409, {"ok": False, "error": "topic is already initialized"})
        if not self.base_dir:
            return _json_response(409, {"ok": False, "error": "bootstrap base_dir is not configured"})
        params = parse_qs(body, keep_blank_values=True)
        options = _codex_options(params)
        if isinstance(options, WebResponse):
            return options
        title = _text_param(params, "title")
        direction = _text_param(params, "direction")
        seed_papers = _list_param(params, "seed_paper")
        if not _safe_text_field(title, 200):
            return _json_response(400, {"ok": False, "error": "title is required"})
        if not _safe_text_field(direction, 4000):
            return _json_response(400, {"ok": False, "error": "direction is required"})
        seed_papers = [paper for paper in seed_papers if _safe_text_field(paper, 500, required=False)]
        expected_root = root_from_title(self.base_dir, title or "")

        if self.runner is None:
            try:
                result = self._direct_bootstrap_init(expected_root, title or "", direction or "", seed_papers)
            except FileExistsError as exc:
                return _json_response(409, {"ok": False, "error": str(exc)})
            except Exception as exc:
                return _json_response(500, {"ok": False, "error": str(exc)})
            self.topic_root = expected_root
            self.pending_init = None
            result["redirect"] = "/dashboard.html"
            return _json_response(202, result)

        def prompt_builder(project_root: Path, work_root: Path, task: str) -> str:
            return build_bootstrap_init_prompt(project_root, work_root, title or "", direction or "", seed_papers)

        manager = JobManager(
            self.base_dir,
            runner=self.runner,
            project_root=self.project_root,
            state_dir=self.base_dir / ".battery_serverlet",
            prompt_builder=prompt_builder,
            codex_model=options[0],
            codex_effort=options[1],
        )
        try:
            result = manager.start_job("Initialize topic", action="topic-init")
        except JobAlreadyActive as exc:
            return _json_response(409, {"ok": False, "error": str(exc)})
        self.pending_init = {"job_id": result["job_id"], "expected_root": str(expected_root)}
        result["expected_root"] = str(expected_root)
        return _json_response(202, result)

    def _direct_bootstrap_init(self, expected_root: Path, title: str, direction: str, seed_papers: list[str]) -> dict[str, object]:
        assert self.base_dir is not None
        project_root = self.project_root or repo_root()
        state_dir = self.base_dir / ".battery_serverlet"
        jobs_dir = state_dir / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        job_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc).isoformat()
        job_dir = jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        prompt = build_bootstrap_init_prompt(project_root, self.base_dir, title, direction, seed_papers)
        (job_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        active_path = state_dir / "active_job.json"
        if active_path.exists():
            raise FileExistsError(f"job already active: {active_path}")
        active_path.write_text(json.dumps({"job_id": job_id, "action": "topic-init", "started_at": started_at}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            result = init_topic(expected_root, title=title, direction=direction, seed_papers=seed_papers)
            from .html import build_html

            build_html(expected_root)
            summary = {
                "ok": True,
                "job_id": job_id,
                "action": "topic-init",
                "started_at": started_at,
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "summary": f"created topic at {expected_root}",
                "root": str(expected_root),
                "created": result.get("created", []),
            }
            (job_dir / "events.jsonl").write_text(
                json.dumps({"kind": "result", "payload": summary}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            summary = {
                "ok": False,
                "job_id": job_id,
                "action": "topic-init",
                "started_at": started_at,
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            }
            (job_dir / "stderr.log").write_text(str(exc) + "\n", encoding="utf-8")
        finally:
            if active_path.exists():
                active_path.unlink()
        (job_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
        with (state_dir / "jobs.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")
        if not summary["ok"]:
            raise RuntimeError(str(summary.get("error") or "topic init failed"))
        return {"ok": True, "queued": False, "job_id": job_id, "action": "topic-init", "expected_root": str(expected_root)}

    def _candidate_mark_action(self, body: str) -> WebResponse:
        params = parse_qs(body, keep_blank_values=True)
        options = _codex_options(params)
        if isinstance(options, WebResponse):
            return options
        candidate_id = _text_param(params, "candidate_id")
        decision = _text_param(params, "decision") or ""
        if not _safe_id(candidate_id) or decision not in {"relevant", "irrelevant", "none"}:
            return _json_response(400, {"ok": False, "error": "candidate_id and valid decision are required"})
        return self._run_job(mark_candidate_task(candidate_id, decision), action="candidate-mark", codex_model=options[0], codex_effort=options[1])

    def _candidate_acquire_action(self, body: str) -> WebResponse:
        params = parse_qs(body, keep_blank_values=True)
        options = _codex_options(params)
        if isinstance(options, WebResponse):
            return options
        candidate_ids = _list_param(params, "candidate_id")
        if not candidate_ids or not all(_safe_id(candidate_id) for candidate_id in candidate_ids):
            return _json_response(400, {"ok": False, "error": "candidate_id is required"})
        return self._run_job(acquire_candidate_task(candidate_ids if len(candidate_ids) > 1 else candidate_ids[0]), action="candidate-acquire", codex_model=options[0], codex_effort=options[1])

    def _candidate_dismiss_action(self, body: str) -> WebResponse:
        params = parse_qs(body, keep_blank_values=True)
        options = _codex_options(params)
        if isinstance(options, WebResponse):
            return options
        candidate_id = _text_param(params, "candidate_id")
        if not _safe_id(candidate_id):
            return _json_response(400, {"ok": False, "error": "candidate_id is required"})
        return self._run_job(dismiss_candidate_task(candidate_id), action="candidate-dismiss", codex_model=options[0], codex_effort=options[1])

    def _library_read_action(self, body: str) -> WebResponse:
        params = parse_qs(body, keep_blank_values=True)
        options = _codex_options(params)
        if isinstance(options, WebResponse):
            return options
        bibkeys = _list_param(params, "bibkey")
        if not bibkeys or not all(_safe_id(bibkey) for bibkey in bibkeys):
            return _json_response(400, {"ok": False, "error": "bibkey is required"})
        return self._run_job(read_paper_task(bibkeys if len(bibkeys) > 1 else bibkeys[0]), action="library-read", codex_model=options[0], codex_effort=options[1])

    def _library_rebuild_html_action(self, body: str) -> WebResponse:
        params = parse_qs(body, keep_blank_values=True)
        options = _codex_options(params)
        if isinstance(options, WebResponse):
            return options
        bibkey = _text_param(params, "bibkey")
        if bibkey and not _safe_id(bibkey):
            return _json_response(400, {"ok": False, "error": "bibkey is invalid"})
        return self._run_job(html_build_task(bibkey), action="library-rebuild-html", codex_model=options[0], codex_effort=options[1])

    def _run_job(self, task: str, action: str, codex_model: str | None = None, codex_effort: str | None = None) -> WebResponse:
        if not self.topic_root:
            return _json_response(409, {"ok": False, "error": "topic is not initialized yet"})
        manager = JobManager(
            self.topic_root,
            runner=self.runner,
            project_root=self.project_root,
            codex_model=codex_model,
            codex_effort=codex_effort,
        )
        try:
            result = manager.start_job(task, action=action)
        except JobAlreadyActive as exc:
            return _json_response(409, {"ok": False, "error": str(exc)})
        return _json_response(202, result)

    def _session_start_action(self, body: str) -> WebResponse:
        if not self.topic_root:
            return _json_response(409, {"ok": False, "error": "topic is not initialized yet"})
        payload = _payload_from_body(body)
        options = _codex_options_from_payload(payload)
        if isinstance(options, WebResponse):
            return options
        result = self._session().ensure_session(self.topic_root, model=options[0], effort=options[1])
        return _json_response(200 if result.get("ok") else 503, result)

    def _session_state_action(self) -> WebResponse:
        state = self._session().state()
        payload = {"ok": not state.get("blocker"), **state}
        return _json_response(200, payload)

    def _session_transcript_action(self) -> WebResponse:
        return _json_response(200, self._session().transcript())

    def _session_events_action(self, query: str) -> WebResponse:
        params = parse_qs(query, keep_blank_values=True)
        cursor = _int_param(params, "cursor", 0)
        limit = _int_param(params, "limit", 200)
        return _json_response(200, self._session().events_since(cursor=cursor, limit=limit))

    def _session_message_action(self, body: str) -> WebResponse:
        if not self.topic_root:
            return _json_response(409, {"ok": False, "error": "topic is not initialized yet"})
        payload = _payload_from_body(body)
        message = str(payload.get("message") or "").strip()
        if not _safe_chat_message(message):
            return _json_response(400, {"ok": False, "error": "message contains unsupported characters"})
        started = self._ensure_session_from_payload(payload)
        if isinstance(started, WebResponse):
            return started
        busy = self._session().state()
        if busy.get("status") == "running":
            return _json_response(409, {"ok": False, "error": "session turn is already running"})
        result = self._session().send_message(message)
        return _json_response(202 if result.get("ok") else 503, result)

    def _session_action_action(self, body: str) -> WebResponse:
        if not self.topic_root:
            return _json_response(409, {"ok": False, "error": "topic is not initialized yet"})
        payload = _payload_from_body(body)
        action = str(payload.get("action") or "").strip()
        action_payload = payload.get("payload") or {}
        if not _safe_id(action) or not isinstance(action_payload, dict):
            return _json_response(400, {"ok": False, "error": "action and object payload are required"})
        direct = self._direct_session_action(action, action_payload)
        if direct is not None:
            return direct
        started = self._ensure_session_from_payload(payload)
        if isinstance(started, WebResponse):
            return started
        busy = self._session().state()
        if busy.get("status") == "running":
            return _json_response(409, {"ok": False, "error": "session turn is already running"})
        result = self._session().send_action(action, action_payload)
        return _json_response(202 if result.get("ok") else 503, result)

    def _direct_session_action(self, action: str, payload: dict[str, object]) -> WebResponse | None:
        if action == "candidate_download_selected":
            return self._direct_candidate_download(payload)
        if action not in {"candidate_mark_relevant", "candidate_mark_irrelevant", "candidate_dismissed"}:
            return None
        if not self.topic_root:
            return _json_response(409, {"ok": False, "error": "topic is not initialized yet"})
        candidate_id = str(payload.get("candidate_id") or "").strip()
        if not _safe_id(candidate_id):
            return _json_response(400, {"ok": False, "error": "candidate_id is required"})
        decision = {
            "candidate_mark_relevant": "relevant",
            "candidate_mark_irrelevant": "irrelevant",
            "candidate_dismissed": "dismissed",
        }[action]
        try:
            if decision in {"relevant", "irrelevant"}:
                candidate = mark_candidate_with_feedback(self.topic_root, candidate_id, decision)
            else:
                candidate = mark_candidate(self.topic_root, candidate_id, decision)
        except KeyError as exc:
            return _json_response(404, {"ok": False, "error": str(exc)})
        return _json_response(200, {"ok": True, "action": action, "candidate": candidate})

    def _direct_candidate_download(self, payload: dict[str, object]) -> WebResponse:
        if not self.topic_root:
            return _json_response(409, {"ok": False, "error": "topic is not initialized yet"})
        raw_ids = payload.get("candidate_ids") or payload.get("candidate_id") or []
        if isinstance(raw_ids, str):
            candidate_ids = [raw_ids]
        elif isinstance(raw_ids, list):
            candidate_ids = [str(candidate_id).strip() for candidate_id in raw_ids if str(candidate_id).strip()]
        else:
            candidate_ids = []
        if not candidate_ids or not all(_safe_id(candidate_id) for candidate_id in candidate_ids):
            return _json_response(400, {"ok": False, "error": "candidate_ids are required"})

        results: list[dict[str, object]] = []
        for candidate_id in candidate_ids:
            metadata = enrich_candidate(self.topic_root, candidate_id, live=True)
            acquired = acquire_pdf(self.topic_root, candidate_id)
            entry: dict[str, object] = {"candidate_id": candidate_id, "metadata": metadata, "acquire": acquired}
            if acquired.get("ok"):
                try:
                    entry["promote"] = promote_candidate(self.topic_root, candidate_id)
                except Exception as exc:
                    entry["promote"] = {"ok": False, "error": str(exc)}
            results.append(entry)
        if any(bool((result.get("promote") or {}).get("ok")) for result in results if isinstance(result.get("promote"), dict)):
            build_html(self.topic_root)
        ok = any(bool((result.get("promote") or {}).get("ok")) for result in results if isinstance(result.get("promote"), dict))
        return _json_response(200 if ok else 502, {"ok": ok, "action": "candidate_download_selected", "results": results})

    def _session_stop_action(self) -> WebResponse:
        result = self._session().stop_turn()
        return _json_response(200 if result.get("ok") else 503, result)

    def _ensure_session_from_payload(self, payload: dict[str, object]) -> WebResponse | None:
        assert self.topic_root is not None
        options = _codex_options_from_payload(payload)
        if isinstance(options, WebResponse):
            return options
        state = self._session().ensure_session(self.topic_root, model=options[0], effort=options[1])
        if not state.get("ok"):
            return _json_response(503, state)
        return None

    def _job_api(self, path: str) -> WebResponse:
        suffix = unquote(path.removeprefix("/api/jobs/"))
        is_events = suffix.endswith("/events")
        job_id = suffix.removesuffix("/events").strip("/")
        if not SAFE_JOB_ID_RE.match(job_id):
            return _json_response(400, {"ok": False, "error": "job_id is invalid"})
        if is_events:
            events = job_events(self._job_root(), job_id, state_dir=self._job_state_dir())
            if events is None:
                return _json_response(404, {"ok": False, "error": "job not found"})
            return _json_response(200, {"ok": True, "job_id": job_id, "events": events})
        detail = job_detail(self._job_root(), job_id, state_dir=self._job_state_dir())
        if detail is None:
            return _json_response(404, {"ok": False, "error": "job not found"})
        return _json_response(200, {"ok": True, "job": detail})


def _text_param(params: dict[str, list[str]], key: str) -> str | None:
    value = (params.get(key) or [""])[0].strip()
    return value or None


def _list_param(params: dict[str, list[str]], key: str) -> list[str]:
    return [value.strip() for value in params.get(key, []) if value.strip()]


def _codex_options(params: dict[str, list[str]]) -> tuple[str | None, str | None] | WebResponse:
    model = _text_param(params, "codex_model")
    effort = _text_param(params, "codex_effort")
    if model in {"", "default"}:
        model = None
    if effort in {"", "default"}:
        effort = None
    if model and model not in ALLOWED_CODEX_MODELS:
        return _json_response(400, {"ok": False, "error": f"unsupported codex model: {model}"})
    if effort and effort not in ALLOWED_CODEX_EFFORTS:
        return _json_response(400, {"ok": False, "error": f"unsupported codex effort: {effort}"})
    return model, effort


def _payload_from_body(body: str) -> dict[str, object]:
    if not body.strip():
        return {}
    if body.lstrip().startswith("{"):
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}
    params = parse_qs(body, keep_blank_values=True)
    payload: dict[str, object] = {}
    for key, values in params.items():
        cleaned = [value for value in values if value != ""]
        if not cleaned:
            continue
        payload[key] = cleaned if len(cleaned) > 1 else cleaned[0]
    return payload


def _codex_options_from_payload(payload: dict[str, object]) -> tuple[str | None, str | None] | WebResponse:
    model_value = payload.get("codex_model") or payload.get("model")
    effort_value = payload.get("codex_effort") or payload.get("effort")
    model = str(model_value).strip() if model_value is not None else None
    effort = str(effort_value).strip() if effort_value is not None else None
    if model in {"", "default"}:
        model = None
    if effort in {"", "default"}:
        effort = None
    if model and model not in ALLOWED_CODEX_MODELS:
        return _json_response(400, {"ok": False, "error": f"unsupported codex model: {model}"})
    if effort and effort not in ALLOWED_CODEX_EFFORTS:
        return _json_response(400, {"ok": False, "error": f"unsupported codex effort: {effort}"})
    return model, effort


def _int_param(params: dict[str, list[str]], key: str, default: int) -> int:
    try:
        return int((params.get(key) or [str(default)])[0] or default)
    except ValueError:
        return default


def _float_param(params: dict[str, list[str]], key: str) -> float | None:
    value = (params.get(key) or [""])[0].strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _json_response(status: int, data: dict[str, object]) -> WebResponse:
    return WebResponse(status, json.dumps(data, ensure_ascii=False), "application/json; charset=utf-8")


def _image_content_type(name: str) -> str | None:
    if not re.match(r"^[A-Za-z0-9_.:-]+$", name):
        return None
    suffix = Path(name).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix)


def _safe_id(value: str | None) -> bool:
    return bool(value and SAFE_ID_RE.match(value))


def _safe_chat_message(value: str | None) -> bool:
    if not value or len(value) > 4000:
        return False
    return all(char in {"\n", "\r", "\t"} or ord(char) >= 32 for char in value)


def _safe_text_field(value: str | None, max_length: int, required: bool = True) -> bool:
    if not value:
        return not required
    if len(value) > max_length:
        return False
    return all(char in {"\n", "\r", "\t"} or ord(char) >= 32 for char in value)


def serve_web(root: str | Path | None = None, host: str = "127.0.0.1", port: int = 10005, base_dir: str | Path | None = None) -> None:
    app = WebApp(root, base_dir=base_dir)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            response = app.handle(self.path)
            self._send(response)

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length).decode("utf-8") if length else ""
            response = app.handle(self.path, method="POST", body=body)
            self._send(response)

        def _send(self, response: WebResponse) -> None:
            body = response.body if isinstance(response.body, bytes) else response.body.encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, int(port)), Handler)
    print(f"serving web workbench at http://{host}:{port}/")
    server.serve_forever()
