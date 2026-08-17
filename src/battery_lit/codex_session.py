from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Protocol

from .codex_paths import codex_env, resolve_codex_bin
from .paths import repo_root
from .prompt_contracts import build_operation_prompt, session_action_task


@dataclass(frozen=True)
class SessionEvent:
    cursor: int
    kind: str
    created_at: str
    data: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "cursor": self.cursor,
            "kind": self.kind,
            "created_at": self.created_at,
            **self.data,
        }


class CodexSessionManager(Protocol):
    def ensure_session(self, topic_root: Path, model: str | None, effort: str | None) -> dict[str, object]:
        ...

    def send_message(self, message: str) -> dict[str, object]:
        ...

    def send_message_until_outputs(
        self,
        message: str,
        required_outputs: list[Path],
        *,
        stable_seconds: float = 5.0,
        timeout_seconds: float | None = None,
        require_output_updates: bool = False,
    ) -> dict[str, object]:
        ...

    def send_action(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        ...

    def events_since(self, cursor: int = 0, limit: int = 200) -> dict[str, object]:
        ...

    def transcript(self) -> dict[str, object]:
        ...

    def state(self) -> dict[str, object]:
        ...

    def stop_turn(self) -> dict[str, object]:
        ...


class FakeCodexSessionManager:
    def __init__(self, fail_messages: bool = False, blocker: str | None = None) -> None:
        self.topic_root: Path | None = None
        self.model: str | None = None
        self.effort: str | None = None
        self.fail_messages = fail_messages
        self.blocker = blocker
        self.status = "blocked" if blocker else "idle"
        self._events: list[SessionEvent] = []
        self._next_cursor = 1

    def ensure_session(self, topic_root: Path, model: str | None, effort: str | None) -> dict[str, object]:
        root = Path(topic_root).expanduser().resolve()
        if self.topic_root is not None and root != self.topic_root:
            raise ValueError(f"session already bound to {self.topic_root}")
        self.topic_root = root
        self.model = model
        self.effort = effort
        if not self._events:
            self._append("session_started", topic_root=str(root), model=model, effort=effort)
        return {
            "ok": self.blocker is None,
            "topic_root": str(root),
            "model": model,
            "effort": effort,
            "status": self.status,
            "blocker": self.blocker,
        }

    def send_message(self, message: str) -> dict[str, object]:
        self._require_session()
        if self.blocker:
            return {"ok": False, "status": "blocked", "error": self.blocker}
        self._append("user_message", message=message)
        if self.fail_messages:
            self.status = "failed"
            self.blocker = "simulated message failure"
            self._append("error", error=self.blocker)
            return {"ok": False, "status": self.status, "error": self.blocker}
        self.status = "idle"
        reply = f"Fake Codex acknowledged: {message}"
        self._append("assistant_message", message=reply)
        return {"ok": True, "status": self.status, "message": reply}

    def send_message_until_outputs(
        self,
        message: str,
        required_outputs: list[Path],
        *,
        stable_seconds: float = 5.0,
        timeout_seconds: float | None = None,
        require_output_updates: bool = False,
    ) -> dict[str, object]:
        result = self.send_message(message)
        if not result.get("ok"):
            return result
        missing = [str(path) for path in required_outputs if not path.exists() or path.stat().st_size <= 0]
        if missing:
            return {"ok": False, "status": self.status, "error": "required outputs were not written", "missing": missing}
        return {"ok": True, "status": self.status, "outputs_ready": True}

    def send_action(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        self._require_session()
        if self.blocker:
            return {"ok": False, "status": "blocked", "error": self.blocker}
        self.status = "idle"
        self._append("action", action=action, payload=dict(payload))
        return {"ok": True, "status": self.status, "action": action}

    def events_since(self, cursor: int = 0, limit: int = 200) -> dict[str, object]:
        safe_limit = max(0, int(limit))
        matching = [event.as_dict() for event in self._events if event.cursor > int(cursor)]
        bounded = matching[:safe_limit] if safe_limit else []
        next_cursor = int(cursor)
        if bounded:
            next_cursor = int(bounded[-1]["cursor"])
        return {
            "ok": True,
            "cursor": int(cursor),
            "next_cursor": next_cursor,
            "events": bounded,
            "has_more": len(matching) > len(bounded),
        }

    def transcript(self) -> dict[str, object]:
        events = [event.as_dict() for event in self._events]
        return _transcript_from_events(events, self.state())

    def state(self) -> dict[str, object]:
        return {
            "ok": self.blocker is None,
            "status": self.status,
            "topic_root": str(self.topic_root) if self.topic_root else None,
            "model": self.model,
            "effort": self.effort,
            "blocker": self.blocker,
            "context_left": None,
        }

    def stop_turn(self) -> dict[str, object]:
        self._require_session()
        if self.status == "running":
            self.status = "idle"
            self._append("turn_stopped")
            return {"ok": True, "status": self.status}
        return {"ok": True, "status": self.status, "skipped": "no active turn"}

    def _require_session(self) -> None:
        if self.topic_root is None:
            raise RuntimeError("session has not been started")

    def _append(self, kind: str, **data: object) -> None:
        self._events.append(
            SessionEvent(
                cursor=self._next_cursor,
                kind=kind,
                created_at=datetime.now(timezone.utc).isoformat(),
                data=data,
            )
        )
        self._next_cursor += 1


class AppServerProtocolError(RuntimeError):
    pass


ProcessFactory = Callable[[list[str], Path], object]


class AppServerCodexSessionManager:
    def __init__(
        self,
        codex_bin: str | None = None,
        project_root: str | Path | None = None,
        spawn: ProcessFactory | None = None,
        request_timeout: float = 10.0,
    ) -> None:
        self.codex_bin = resolve_codex_bin(codex_bin)
        self.project_root = Path(project_root).expanduser().resolve() if project_root else repo_root()
        self.spawn = spawn or self._spawn_process
        self.request_timeout = request_timeout
        self.topic_root: Path | None = None
        self.model: str | None = None
        self.effort: str | None = None
        self.thread_id: str | None = None
        self.active_turn_id: str | None = None
        self.status = "idle"
        self.blocker: str | None = None
        self.context_left: float | None = None
        self._proc: object | None = None
        self._reader: threading.Thread | None = None
        self._responses: dict[int, dict[str, object]] = {}
        self._condition = threading.Condition()
        self._initialize_lock = threading.Lock()
        self._events: list[SessionEvent] = []
        self._next_cursor = 1
        self._next_request_id = 1

    def ensure_session(self, topic_root: Path, model: str | None, effort: str | None) -> dict[str, object]:
        root = Path(topic_root).expanduser().resolve()
        with self._initialize_lock:
            if self.topic_root is not None and root != self.topic_root:
                raise ValueError(f"session already bound to {self.topic_root}")
            self.topic_root = root
            self.model = model
            self.effort = effort
            if self.blocker:
                return self.state() | {"ok": False}
            if self.thread_id:
                return self.state() | {"ok": True}
            try:
                self._ensure_process(root)
                self._request(
                    "initialize",
                    {
                        "clientInfo": {
                            "name": "battery_lit",
                            "title": "battery_lit",
                            "version": "0.1.0",
                        },
                        "capabilities": {"experimentalApi": True},
                    },
                )
                self._notify("initialized", {})
                thread_params: dict[str, object] = {
                    "cwd": str(root),
                    "sandbox": "workspace-write",
                    "runtimeWorkspaceRoots": [str(root)],
                }
                if model:
                    thread_params["model"] = model
                result = self._request("thread/start", thread_params)
                thread = result.get("thread") if isinstance(result, dict) else None
                self.thread_id = str(thread.get("id")) if isinstance(thread, dict) and thread.get("id") else None
                if not self.thread_id:
                    raise AppServerProtocolError("thread/start did not return thread.id")
                self.status = "idle"
                self._append("session_started", topic_root=str(root), model=model, effort=effort, thread_id=self.thread_id)
                return self.state() | {"ok": True}
            except Exception as exc:
                return self._block(str(exc))

    def send_message(self, message: str) -> dict[str, object]:
        self._require_thread()
        if self.blocker:
            return {"ok": False, "status": self.status, "error": self.blocker}
        return self._start_turn(self._operation_prompt(message), display_message=message)

    def send_message_until_outputs(
        self,
        message: str,
        required_outputs: list[Path],
        *,
        stable_seconds: float = 5.0,
        timeout_seconds: float | None = None,
        require_output_updates: bool = False,
    ) -> dict[str, object]:
        self._require_thread()
        if self.blocker:
            return {"ok": False, "status": self.status, "error": self.blocker}
        initial_signatures = {path: _file_signature(path) for path in required_outputs}
        started = self._start_turn(self._operation_prompt(message), display_message=message)
        if not started.get("ok"):
            return started
        deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None else None
        complete_since: float | None = None
        while True:
            now = time.monotonic()
            outputs_ready = all(path.exists() and path.stat().st_size > 0 for path in required_outputs)
            if outputs_ready and require_output_updates:
                outputs_ready = any(_file_signature(path) != initial_signatures.get(path) for path in required_outputs)
            if outputs_ready:
                complete_since = complete_since or now
                if now - complete_since >= stable_seconds:
                    interrupted = False
                    if self.status == "running":
                        stopped = self.stop_turn()
                        interrupted = bool(stopped.get("ok"))
                    return {
                        "ok": True,
                        "status": self.status,
                        "outputs_ready": True,
                        "interrupted_after_outputs": interrupted,
                        "thread_id": self.thread_id,
                    }
            else:
                complete_since = None

            if self.status in {"failed", "blocked"}:
                missing = [str(path) for path in required_outputs if not path.exists() or path.stat().st_size <= 0]
                return {
                    "ok": False,
                    "status": self.status,
                    "error": self.blocker or "codex turn failed before required outputs were ready",
                    "missing": missing,
                    "thread_id": self.thread_id,
                }
            if self.status == "idle" and not outputs_ready:
                missing = [str(path) for path in required_outputs if not path.exists() or path.stat().st_size <= 0]
                return {
                    "ok": False,
                    "status": self.status,
                    "error": "codex turn completed without required outputs",
                    "missing": missing,
                    "thread_id": self.thread_id,
                }
            if deadline is not None and now >= deadline:
                if self.status == "running":
                    self.stop_turn()
                missing = [str(path) for path in required_outputs if not path.exists() or path.stat().st_size <= 0]
                return {
                    "ok": False,
                    "status": self.status,
                    "error": f"timed out waiting for required outputs after {timeout_seconds:.0f} seconds",
                    "missing": missing,
                    "thread_id": self.thread_id,
                }
            time.sleep(0.5)

    def send_action(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        task = session_action_task(action, payload)
        result = self._start_turn(self._operation_prompt(task), display_message=f"Browser action: {action}")
        if result.get("ok"):
            self._append("action", action=action, payload=dict(payload))
        return result | {"action": action}

    def events_since(self, cursor: int = 0, limit: int = 200) -> dict[str, object]:
        safe_limit = max(0, int(limit))
        with self._condition:
            matching = [event.as_dict() for event in self._events if event.cursor > int(cursor)]
        bounded = matching[:safe_limit] if safe_limit else []
        next_cursor = int(cursor)
        if bounded:
            next_cursor = int(bounded[-1]["cursor"])
        return {
            "ok": self.blocker is None,
            "cursor": int(cursor),
            "next_cursor": next_cursor,
            "events": bounded,
            "has_more": len(matching) > len(bounded),
            "blocker": self.blocker,
        }

    def transcript(self) -> dict[str, object]:
        with self._condition:
            events = [event.as_dict() for event in self._events]
        return _transcript_from_events(events, self.state())

    def state(self) -> dict[str, object]:
        return {
            "status": self.status,
            "topic_root": str(self.topic_root) if self.topic_root else None,
            "thread_id": self.thread_id,
            "active_turn_id": self.active_turn_id,
            "model": self.model,
            "effort": self.effort,
            "blocker": self.blocker,
            "context_left": self.context_left,
        }

    def stop_turn(self) -> dict[str, object]:
        if not self.thread_id or not self.active_turn_id:
            return {"ok": True, "status": self.status, "skipped": "no active turn"}
        try:
            self._request("turn/interrupt", {"threadId": self.thread_id, "turnId": self.active_turn_id})
        except Exception as exc:
            return self._block(str(exc))
        self.status = "idle"
        self._append("turn_stopped", thread_id=self.thread_id, turn_id=self.active_turn_id)
        self.active_turn_id = None
        return {"ok": True, "status": self.status}

    def close(self) -> None:
        if self._proc is None:
            return
        terminate = getattr(self._proc, "terminate", None)
        if callable(terminate) and self._poll_process() is None:
            terminate()
        wait = getattr(self._proc, "wait", None)
        if callable(wait):
            try:
                wait(timeout=2)
            except TypeError:
                wait()
            except Exception:
                return

    def _operation_prompt(self, task: str) -> str:
        assert self.topic_root is not None
        return build_operation_prompt(self.project_root, self.topic_root, task)

    def _start_turn(self, message: str, display_message: str | None = None) -> dict[str, object]:
        assert self.topic_root is not None
        assert self.thread_id is not None
        params: dict[str, object] = {
            "threadId": self.thread_id,
            "cwd": str(self.topic_root),
            "runtimeWorkspaceRoots": [str(self.topic_root)],
            "sandboxPolicy": _app_server_sandbox_policy(),
            "input": [{"type": "text", "text": message}],
        }
        if self.model:
            params["model"] = self.model
        if self.effort:
            params["effort"] = self.effort
        self.status = "running"
        self._append("user_message", message=display_message or message)
        try:
            result = self._request("turn/start", params)
        except Exception as exc:
            return self._block(str(exc))
        turn = result.get("turn") if isinstance(result, dict) else None
        if isinstance(turn, dict) and turn.get("id"):
            self.active_turn_id = str(turn["id"])
        self._wait_for_quick_completion()
        return {"ok": True, "status": self.status, "thread_id": self.thread_id, "turn_id": self.active_turn_id}

    def _ensure_process(self, cwd: Path) -> None:
        if self._proc is not None and self._poll_process() is None:
            return
        command = [self.codex_bin, "app-server", "--listen", "stdio://"]
        self._proc = self.spawn(command, cwd)
        if self._poll_process() is not None:
            raise AppServerProtocolError(f"app-server exited with code {self._poll_process()}")
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    def _spawn_process(self, command: list[str], cwd: Path) -> subprocess.Popen[str]:
        return subprocess.Popen(
            command,
            cwd=str(cwd),
            env=codex_env(self.project_root / "bin"),
            text=True,
            bufsize=1,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def _request(self, method: str, params: dict[str, object]) -> dict[str, object]:
        request_id = self._next_request_id
        self._next_request_id += 1
        self._send({"method": method, "id": request_id, "params": params})
        deadline = time.time() + self.request_timeout
        with self._condition:
            while request_id not in self._responses:
                if self._poll_process() is not None:
                    raise AppServerProtocolError(f"app-server exited with code {self._poll_process()}")
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise AppServerProtocolError(f"timed out waiting for {method}")
                self._condition.wait(timeout=min(remaining, 0.1))
            response = self._responses.pop(request_id)
        error = response.get("error")
        if isinstance(error, dict):
            raise AppServerProtocolError(str(error.get("message") or error))
        result = response.get("result")
        return result if isinstance(result, dict) else {}

    def _notify(self, method: str, params: dict[str, object]) -> None:
        self._send({"method": method, "params": params})

    def _send(self, message: dict[str, object]) -> None:
        if self._proc is None:
            raise AppServerProtocolError("app-server process is not started")
        if self._poll_process() is not None:
            raise AppServerProtocolError(f"app-server exited with code {self._poll_process()}")
        stdin = getattr(self._proc, "stdin", None)
        if stdin is None:
            raise AppServerProtocolError("app-server stdin is unavailable")
        stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        stdin.flush()

    def _reader_loop(self) -> None:
        assert self._proc is not None
        stdout = getattr(self._proc, "stdout", None)
        if stdout is None:
            self._block("app-server stdout is unavailable")
            return
        while True:
            line = stdout.readline()
            if not line:
                if self._poll_process() is not None:
                    self._block(f"app-server exited with code {self._poll_process()}")
                    return
                continue
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                self._append("app-server/stdout", text=line)
                continue
            if "id" in message:
                with self._condition:
                    self._responses[int(message["id"])] = message
                    self._condition.notify_all()
            else:
                self._record_notification(message)

    def _record_notification(self, message: dict[str, object]) -> None:
        method = str(message.get("method") or "notification")
        params = message.get("params")
        data = dict(params) if isinstance(params, dict) else {"params": params}
        if method == "turn/started":
            self.status = "running"
            turn = data.get("turn")
            if isinstance(turn, dict) and turn.get("id"):
                self.active_turn_id = str(turn["id"])
        elif method == "turn/completed":
            self.status = "idle"
            turn = data.get("turn")
            if isinstance(turn, dict) and turn.get("id") == self.active_turn_id:
                self.active_turn_id = None
        elif method == "error" and _is_transient_stream_disconnect(data):
            # The app-server emits these while it retries the response stream.
            # They are informational unless a later turn/failed notification arrives.
            self._append("connection_warning", message=_format_notification_error(data), details=data)
            return
        elif method in {"turn/failed", "error"}:
            self.status = "failed"
            self.blocker = _format_notification_error(data, fallback=method)
        self._append(method, **data)

    def _update_context_left(self, data: dict[str, object]) -> None:
        return None

    def _wait_for_quick_completion(self) -> None:
        deadline = time.time() + 0.05
        while time.time() < deadline and self.status == "running":
            time.sleep(0.005)

    def _poll_process(self) -> int | None:
        if self._proc is None:
            return None
        poll = getattr(self._proc, "poll", None)
        return poll() if callable(poll) else None

    def _require_thread(self) -> None:
        if self.topic_root is None or self.thread_id is None:
            raise RuntimeError("session has not been started")

    def _append(self, kind: str, **data: object) -> None:
        with self._condition:
            self._events.append(
                SessionEvent(
                    cursor=self._next_cursor,
                    kind=kind,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    data=data,
                )
            )
            self._next_cursor += 1
            self._condition.notify_all()

    def _block(self, message: str) -> dict[str, object]:
        self.status = "blocked"
        self.blocker = message
        self._append("blocker", error=message)
        return self.state() | {"ok": False}


def _is_transient_stream_disconnect(data: dict[str, object]) -> bool:
    payload = data.get("error") if isinstance(data.get("error"), dict) else data
    assert isinstance(payload, dict)
    info = payload.get("codexErrorInfo")
    disconnected = isinstance(info, dict) and "responseStreamDisconnected" in info
    message = str(payload.get("message") or "").strip().lower()
    return disconnected and message.startswith("reconnecting")


def _format_notification_error(data: dict[str, object], fallback: str = "") -> str:
    if isinstance(data.get("error"), dict):
        return _format_notification_error(data["error"], fallback=fallback)
    primary = data.get("message") or data.get("error")
    details = data.get("additionalDetails")
    def render(value: object) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value).strip()

    parts = [render(value) for value in (primary, details) if value and render(value)]
    if parts:
        return " — ".join(dict.fromkeys(parts))
    if data:
        return json.dumps(data, ensure_ascii=False, sort_keys=True)
    return fallback


def _transcript_from_events(events: list[dict[str, object]], state: dict[str, object]) -> dict[str, object]:
    messages: list[dict[str, object]] = []
    active_delta: dict[str, object] | None = None
    latest_cursor = 0

    def flush_delta() -> None:
        nonlocal active_delta
        message = str(active_delta.get("message") or "") if active_delta else ""
        if active_delta and message and not _is_routine_progress_message(message):
            messages.append({key: value for key, value in active_delta.items() if key != "key"})
        active_delta = None

    for event in events:
        cursor = int(event.get("cursor") or 0)
        latest_cursor = max(latest_cursor, cursor)
        kind = str(event.get("kind") or "")
        if kind == "session_started":
            continue
        if kind == "item/agentMessage/delta":
            delta = str(event.get("delta") or "")
            if not delta:
                continue
            key = f"{event.get('turnId') or 'turn'}:{event.get('itemId') or 'assistant'}"
            if not active_delta or active_delta.get("key") != key:
                flush_delta()
                active_delta = {"author": "codex", "message": "", "cursor": cursor, "key": key}
            active_delta["message"] = str(active_delta.get("message") or "") + delta
            active_delta["cursor"] = cursor
            continue
        flush_delta()
        if kind == "user_message":
            message = str(event.get("message") or "")
            if message.startswith("Browser action: "):
                continue
            messages.append({"author": "you", "message": message, "cursor": cursor})
        elif kind == "assistant_message":
            message = str(event.get("message") or "")
            if not _is_routine_progress_message(message):
                messages.append({"author": "codex", "message": message, "cursor": cursor})
        elif kind == "action":
            messages.append({"author": "you", "message": str(event.get("action") or "action"), "cursor": cursor})
        elif kind in {"blocker", "error", "connection_warning"}:
            messages.append({"author": "system", "message": _format_notification_error(event, fallback="blocked"), "cursor": cursor})
        elif kind == "turn/failed":
            messages.append({"author": "system", "message": str(event.get("message") or event.get("error") or "turn failed"), "cursor": cursor})
    flush_delta()
    return {
        "ok": not state.get("blocker"),
        "cursor": latest_cursor,
        "status": state.get("status"),
        "blocker": state.get("blocker"),
        "messages": messages,
    }


def _is_routine_progress_message(message: str) -> bool:
    text = " ".join(str(message or "").strip().lower().split())
    if not text:
        return False
    patterns = [
        "checking the project and topic operating files",
        "checking policy/status",
        "i have the operating constraints",
        "topic-local skill is older",
        "using the project-root contract",
        "project-root contract as requested",
        "sandbox cannot start commands",
        "sandbox wrapper cannot create",
        "user namespaces are unavailable",
        "rerunning the required file reads outside the sandbox",
        "routine file reads",
    ]
    return any(pattern in text for pattern in patterns)


def _file_signature(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns)


def _app_server_sandbox_policy() -> dict[str, str]:
    if os.environ.get("BATTERY_LIT_CODEX_BYPASS_SANDBOX") == "1":
        return {"type": "dangerFullAccess"}
    return {"type": "workspaceWrite"}
