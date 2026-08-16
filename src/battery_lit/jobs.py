from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .codex_worker import CodexEvent, CodexRunner, SubprocessCodexRunner
from .paths import repo_root
from .prompt_contracts import build_worker_prompt
from .util import ensure_dir


class JobAlreadyActive(RuntimeError):
    pass


def _now_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


class JobManager:
    def __init__(
        self,
        topic_root: str | Path,
        runner: CodexRunner | None = None,
        project_root: str | Path | None = None,
        state_dir: str | Path | None = None,
        prompt_builder: Callable[[Path, Path, str], str] | None = None,
        codex_model: str | None = None,
        codex_effort: str | None = None,
    ) -> None:
        self.topic_root = Path(topic_root).expanduser().resolve()
        self.project_root = Path(project_root).expanduser().resolve() if project_root else repo_root()
        self.runner = runner or SubprocessCodexRunner(
            model=codex_model,
            effort=codex_effort,
            project_bin=self.project_root / "bin",
        )
        self.prompt_builder = prompt_builder or build_worker_prompt
        self.state_dir = Path(state_dir).expanduser().resolve() if state_dir else self.topic_root / ".battery"
        self.jobs_dir = self.state_dir / "jobs"
        self.active_path = self.state_dir / "active_job.json"
        self.log_path = self.state_dir / "jobs.jsonl"

    def run_job(self, task: str, action: str = "manual") -> dict[str, object]:
        job = self._create_job(task, action)
        return self._execute_job(job)

    def start_job(self, task: str, action: str = "manual") -> dict[str, object]:
        job = self._create_job(task, action)
        thread = threading.Thread(target=self._execute_job, args=(job,), daemon=True)
        thread.start()
        return {
            "ok": True,
            "queued": True,
            "job_id": job["job_id"],
            "action": action,
            "started_at": job["started_at"],
        }

    def _create_job(self, task: str, action: str) -> dict[str, object]:
        ensure_dir(self.jobs_dir)
        job_id = _now_id()
        job_dir = self.jobs_dir / job_id
        ensure_dir(job_dir)
        started_at = datetime.now(timezone.utc).isoformat()
        prompt = self.prompt_builder(self.project_root, self.topic_root, task)
        (job_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        self._claim_active_job(job_id, action, started_at)
        return {
            "job_id": job_id,
            "job_dir": job_dir,
            "action": action,
            "started_at": started_at,
            "prompt": prompt,
        }

    def _claim_active_job(self, job_id: str, action: str, started_at: str) -> None:
        payload = json.dumps({"job_id": job_id, "action": action, "started_at": started_at}, indent=2, ensure_ascii=False) + "\n"
        try:
            fd = os.open(self.active_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError as exc:
            active_id = self._active_job_id()
            raise JobAlreadyActive(f"job already active: {active_id}") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)

    def _active_job_id(self) -> str:
        try:
            active = json.loads(self.active_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "unknown"
        return str(active.get("job_id") or "unknown")

    def _execute_job(self, job: dict[str, object]) -> dict[str, object]:
        job_id = str(job["job_id"])
        action = str(job["action"])
        started_at = str(job["started_at"])
        prompt = str(job["prompt"])
        job_dir = Path(job["job_dir"])
        events: list[CodexEvent] = []
        result: dict[str, object]
        try:
            with (job_dir / "events.jsonl").open("w", encoding="utf-8") as event_file:
                for event in self.runner.run(prompt, self.topic_root, job_dir):
                    events.append(event)
                    event_file.write(event.to_json() + "\n")
            result = self._success_summary(job_id, action, started_at, events)
        except Exception as exc:  # runner errors must still leave a useful artifact
            with (job_dir / "stderr.log").open("a", encoding="utf-8") as error_file:
                error_file.write(str(exc) + "\n")
            result = {
                "ok": False,
                "job_id": job_id,
                "action": action,
                "started_at": started_at,
                "ended_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            }
        finally:
            if self._active_job_id() == job_id and self.active_path.exists():
                self.active_path.unlink()

        _write_json(job_dir / "summary.json", result)
        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
        return result

    def _success_summary(
        self,
        job_id: str,
        action: str,
        started_at: str,
        events: list[CodexEvent],
    ) -> dict[str, object]:
        summary = ""
        for event in reversed(events):
            value = event.payload.get("summary") or event.payload.get("text")
            if value:
                summary = str(value)
                break
        return {
            "ok": True,
            "job_id": job_id,
            "action": action,
            "started_at": started_at,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "event_count": len(events),
            "summary": summary,
        }
