from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import queue
import threading
import time
from pathlib import Path

from paper_engine.codex_session import AppServerCodexSessionManager
from paper_engine.topic import init_topic


class FakeStdout:
    def __init__(self, process: "FakeAppServerProcess") -> None:
        self.process = process

    def readline(self) -> str:
        try:
            return self.process.outbox.get(timeout=0.5)
        except queue.Empty:
            return "" if self.process.return_code is not None else "\n"


class FakeStdin:
    def __init__(self, process: "FakeAppServerProcess") -> None:
        self.process = process

    def write(self, line: str) -> int:
        self.process.handle_client_line(line)
        return len(line)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.process.return_code = 0


class FakeAppServerProcess:
    def __init__(
        self,
        error_method: str | None = None,
        crash_immediately: bool = False,
        initialize_delay: float = 0.0,
    ) -> None:
        self.error_method = error_method
        self.initialize_delay = initialize_delay
        self.return_code: int | None = 1 if crash_immediately else None
        self.outbox: queue.Queue[str] = queue.Queue()
        self.stdin = FakeStdin(self)
        self.stdout = FakeStdout(self)
        self.stderr = None
        self.sent: list[dict[str, object]] = []
        self.next_turn = 1

    def poll(self) -> int | None:
        return self.return_code

    def terminate(self) -> None:
        self.return_code = 0

    def wait(self, timeout: float | None = None) -> int:
        self.return_code = 0 if self.return_code is None else self.return_code
        return self.return_code

    def handle_client_line(self, line: str) -> None:
        data = json.loads(line)
        self.sent.append(data)
        method = str(data.get("method") or "")
        request_id = data.get("id")
        if method == "initialized":
            return
        if self.error_method == method and request_id is not None:
            self._send({"id": request_id, "error": {"code": -32000, "message": f"{method} failed"}})
            return
        if method == "initialize":
            if self.initialize_delay:
                time.sleep(self.initialize_delay)
            self._send({"id": request_id, "result": {"userAgent": "fake-codex"}})
        elif method == "thread/start":
            self._send({"method": "thread/started", "params": {"thread": {"id": "thr_123"}}})
            self._send({"id": request_id, "result": {"thread": {"id": "thr_123"}}})
        elif method == "turn/start":
            turn_id = f"turn_{self.next_turn}"
            self.next_turn += 1
            self._send({"method": "turn/started", "params": {"threadId": "thr_123", "turn": {"id": turn_id}}})
            self._send({"id": request_id, "result": {"turn": {"id": turn_id}}})
            self._send({"method": "item/agentMessage/delta", "params": {"threadId": "thr_123", "turnId": turn_id, "itemId": "msg", "delta": "working"}})
            self._send(
                {
                    "method": "thread/tokenUsage/updated",
                    "params": {
                        "threadId": "thr_123",
                        "turnId": turn_id,
                        "tokenUsage": {
                            "modelContextWindow": 100,
                            "total": {
                                "totalTokens": 25,
                                "inputTokens": 20,
                                "cachedInputTokens": 0,
                                "outputTokens": 5,
                                "reasoningOutputTokens": 0,
                            },
                            "last": {
                                "totalTokens": 25,
                                "inputTokens": 20,
                                "cachedInputTokens": 0,
                                "outputTokens": 5,
                                "reasoningOutputTokens": 0,
                            },
                        },
                    },
                }
            )
            self._send({"method": "turn/completed", "params": {"threadId": "thr_123", "turn": {"id": turn_id, "status": "completed"}}})
        elif method == "turn/interrupt":
            self._send({"id": request_id, "result": {"ok": True}})

    def _send(self, data: dict[str, object]) -> None:
        self.outbox.put(json.dumps(data) + "\n")


def test_app_server_starts_and_initializes_thread(tmp_path):
    init_topic(tmp_path, "App Server Topic", "app server")
    process = FakeAppServerProcess()
    commands: list[list[str]] = []

    def spawn(command: list[str], cwd: Path):
        commands.append(command)
        return process

    manager = AppServerCodexSessionManager(spawn=spawn)

    state = manager.ensure_session(tmp_path, model="gpt-5.6-sol", effort="medium")

    assert state["ok"] is True
    assert state["thread_id"] == "thr_123"
    assert commands == [["codex", "app-server", "--listen", "stdio://"]]
    methods = [message["method"] for message in process.sent]
    assert methods == ["initialize", "initialized", "thread/start"]
    thread_start = process.sent[-1]["params"]
    assert thread_start["model"] == "gpt-5.6-sol"
    assert thread_start["cwd"] == str(tmp_path.resolve())
    assert thread_start["sandbox"] == "workspace-write"


def test_app_server_initializes_once_under_concurrent_requests(tmp_path):
    init_topic(tmp_path, "Concurrent App Server Topic", "concurrent app server")
    process = FakeAppServerProcess(initialize_delay=0.05)
    spawn_calls: list[list[str]] = []
    barrier = threading.Barrier(8)

    def spawn(command: list[str], cwd: Path):
        spawn_calls.append(command)
        return process

    manager = AppServerCodexSessionManager(spawn=spawn, request_timeout=2.0)

    def start_session(_: int):
        barrier.wait()
        return manager.ensure_session(tmp_path, model="gpt-5.6-sol", effort="medium")

    with ThreadPoolExecutor(max_workers=8) as executor:
        states = list(executor.map(start_session, range(8)))

    assert all(state["ok"] is True for state in states)
    assert {state["thread_id"] for state in states} == {"thr_123"}
    assert len(spawn_calls) == 1
    methods = [message["method"] for message in process.sent]
    assert methods.count("initialize") == 1
    assert methods.count("initialized") == 1
    assert methods.count("thread/start") == 1
    assert manager.state()["blocker"] is None
    assert manager.state()["status"] == "idle"


def test_app_server_spawn_adds_common_codex_bins_to_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    popen_args = {}

    def fake_popen(command, **kwargs):
        popen_args["command"] = command
        popen_args.update(kwargs)
        return FakeAppServerProcess()

    monkeypatch.setattr("paper_engine.codex_session.subprocess.Popen", fake_popen)
    manager = AppServerCodexSessionManager(project_root=tmp_path)

    manager._spawn_process(["codex", "app-server", "--listen", "stdio://"], tmp_path)

    path = popen_args["env"]["PATH"].split(":")
    assert popen_args["command"][0] == "codex"
    assert str(tmp_path.resolve() / "bin") in path
    assert str(Path.home() / ".local" / "bin") in path
    assert "/home/battery/.local/bin" in path
    assert "/home/mdolabuser/.local/bin" in path
    assert "/usr/bin" in path


def test_app_server_turn_start_for_message_and_action(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_ENGINE_CODEX_BYPASS_SANDBOX", "0")
    init_topic(tmp_path, "Turn Topic", "turn start")
    process = FakeAppServerProcess()
    manager = AppServerCodexSessionManager(spawn=lambda command, cwd: process)
    manager.ensure_session(tmp_path, model=None, effort=None)

    message = manager.send_message("Search 30 papers")
    action = manager.send_action("candidate_download_selected", {"candidate_ids": ["CAND-001"]})

    assert message["ok"] is True
    assert action["ok"] is True
    turn_messages = [item for item in process.sent if item.get("method") == "turn/start"]
    assert len(turn_messages) == 2
    assert turn_messages[0]["params"]["sandboxPolicy"] == {"type": "workspaceWrite"}
    assert "Search 30 papers" in turn_messages[0]["params"]["input"][0]["text"]
    assert "When a command says `paper_engine`, run" in turn_messages[0]["params"]["input"][0]["text"]
    assert "candidate_download_selected" in turn_messages[1]["params"]["input"][0]["text"]
    assert "CAND-001" in turn_messages[1]["params"]["input"][0]["text"]
    assert "/bin/paper_engine" in turn_messages[1]["params"]["input"][0]["text"]


def test_app_server_uses_danger_policy_when_bypass_env_is_set(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_ENGINE_CODEX_BYPASS_SANDBOX", "1")
    init_topic(tmp_path, "Bypass Topic", "turn sandbox")
    process = FakeAppServerProcess()
    manager = AppServerCodexSessionManager(spawn=lambda command, cwd: process)
    manager.ensure_session(tmp_path, model=None, effort=None)

    result = manager.send_message("Work without namespace sandbox")

    assert result["ok"] is True
    turn_start = next(item for item in process.sent if item.get("method") == "turn/start")
    assert turn_start["params"]["sandboxPolicy"] == {"type": "dangerFullAccess"}


def test_app_server_waits_for_outputs_then_interrupts_running_turn(tmp_path):
    init_topic(tmp_path, "Output Topic", "output wait")
    output = tmp_path / "done.json"

    class OutputProcess(FakeAppServerProcess):
        def handle_client_line(self, line: str) -> None:
            data = json.loads(line)
            self.sent.append(data)
            method = str(data.get("method") or "")
            request_id = data.get("id")
            if method in {"initialize", "thread/start", "initialized", "turn/interrupt"}:
                return super().handle_client_line(line)
            if method == "turn/start":
                turn_id = f"turn_{self.next_turn}"
                self.next_turn += 1
                self._send({"method": "turn/started", "params": {"threadId": "thr_123", "turn": {"id": turn_id}}})
                self._send({"id": request_id, "result": {"turn": {"id": turn_id}}})
                output.write_text('{"ok": true}\n', encoding="utf-8")
                return
            return super().handle_client_line(line)

    process = OutputProcess()
    manager = AppServerCodexSessionManager(spawn=lambda command, cwd: process)
    manager.ensure_session(tmp_path, model=None, effort=None)

    result = manager.send_message_until_outputs("write output", [output], stable_seconds=0.1, timeout_seconds=2)

    assert result["ok"] is True
    assert result["interrupted_after_outputs"] is True
    assert manager.state()["status"] == "idle"
    assert any(message.get("method") == "turn/interrupt" for message in process.sent)


def test_app_server_notifications_become_events_and_state(tmp_path):
    init_topic(tmp_path, "Events Topic", "notifications")
    process = FakeAppServerProcess()
    manager = AppServerCodexSessionManager(spawn=lambda command, cwd: process)
    manager.ensure_session(tmp_path, model=None, effort=None)

    manager.send_message("Work")
    events = manager.events_since(0)["events"]

    assert any(event["kind"] == "turn/started" for event in events)
    assert any(event["kind"] == "item/agentMessage/delta" and event["delta"] == "working" for event in events)
    assert any(event["kind"] == "thread/tokenUsage/updated" for event in events)
    assert any(event["kind"] == "turn/completed" for event in events)
    state = manager.state()
    assert state["status"] == "idle"
    assert state["thread_id"] == "thr_123"
    assert state["context_left"] is None


def test_app_server_jsonrpc_error_becomes_visible_blocker(tmp_path):
    init_topic(tmp_path, "Error Topic", "errors")
    process = FakeAppServerProcess(error_method="thread/start")
    manager = AppServerCodexSessionManager(spawn=lambda command, cwd: process)

    state = manager.ensure_session(tmp_path, model=None, effort=None)

    assert state["ok"] is False
    assert state["status"] == "blocked"
    assert "thread/start failed" in state["blocker"]


def test_app_server_process_crash_becomes_visible_blocker(tmp_path):
    init_topic(tmp_path, "Crash Topic", "crashes")
    process = FakeAppServerProcess(crash_immediately=True)
    manager = AppServerCodexSessionManager(spawn=lambda command, cwd: process)

    state = manager.ensure_session(tmp_path, model=None, effort=None)

    assert state["ok"] is False
    assert state["status"] == "blocked"
    assert "app-server exited" in state["blocker"]
