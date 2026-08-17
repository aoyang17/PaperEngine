from __future__ import annotations

from pathlib import Path
import time

import pytest

from battery_lit.codex_worker import CodexRunnerError, SubprocessCodexRunner
from battery_lit.codex_session import AppServerCodexSessionManager, FakeCodexSessionManager
from battery_lit.topic import init_topic


def test_fake_session_binds_one_topic_root(tmp_path):
    topic = tmp_path / "topic"
    other = tmp_path / "other"
    init_topic(topic, "Session Topic", "session binding")
    init_topic(other, "Other Topic", "other session")
    manager = FakeCodexSessionManager()

    state = manager.ensure_session(topic, model="gpt-5.5", effort="medium")

    assert state["ok"] is True
    assert state["topic_root"] == str(topic.resolve())
    assert state["model"] == "gpt-5.5"
    assert state["effort"] == "medium"
    with pytest.raises(ValueError, match="already bound"):
        manager.ensure_session(other, model=None, effort=None)


def test_subprocess_codex_runner_can_use_controlled_bypass(monkeypatch, tmp_path):
    monkeypatch.setenv("BATTERY_LIT_CODEX_BYPASS_SANDBOX", "1")

    command = SubprocessCodexRunner(codex_bin="/usr/bin/codex").command(tmp_path)

    assert "--dangerously-bypass-approvals-and-sandbox" in command
    assert "--sandbox" not in command


def test_subprocess_codex_runner_stops_after_required_outputs_are_stable(monkeypatch, tmp_path):
    output = tmp_path / "done.json"
    fake_codex = tmp_path / "fake_codex.py"
    fake_codex.write_text(
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import time

sys.stdin.read()
Path(os.environ["FAKE_CODEX_OUTPUT"]).write_text("{\\"ok\\": true}\\n", encoding="utf-8")
print(json.dumps({"type": "message", "text": "wrote output"}), flush=True)
time.sleep(30)
""",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    monkeypatch.setenv("FAKE_CODEX_OUTPUT", str(output))
    runner = SubprocessCodexRunner(codex_bin=str(fake_codex), bypass_sandbox=True)

    start = time.monotonic()
    events = list(
        runner.run_until_outputs(
            "write the output",
            tmp_path,
            tmp_path / "job",
            [output],
            stable_seconds=0.2,
            timeout_seconds=5,
        )
    )

    assert time.monotonic() - start < 5
    assert output.exists()
    assert any(event.kind == "message" for event in events)


def test_subprocess_codex_runner_repair_requires_output_update(monkeypatch, tmp_path):
    output = tmp_path / "done.json"
    output.write_text('{"ok": false, "old": true}\n', encoding="utf-8")
    fake_codex = tmp_path / "fake_codex_noop.py"
    fake_codex.write_text(
        """#!/usr/bin/env python3
import sys
import time

sys.stdin.read()
time.sleep(30)
""",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    runner = SubprocessCodexRunner(codex_bin=str(fake_codex), bypass_sandbox=True)

    with pytest.raises(CodexRunnerError, match="timed out"):
        list(
            runner.run_until_outputs(
                "repair the output",
                tmp_path,
                tmp_path / "job",
                [output],
                stable_seconds=0.1,
                timeout_seconds=0.5,
                require_output_updates=True,
            )
        )


def test_fake_session_records_message_and_reply(tmp_path):
    init_topic(tmp_path, "Chat Topic", "chat session")
    manager = FakeCodexSessionManager()
    manager.ensure_session(tmp_path, model=None, effort=None)

    result = manager.send_message("Summarize status")

    assert result["ok"] is True
    events = manager.events_since(0)["events"]
    assert [event["kind"] for event in events] == ["session_started", "user_message", "assistant_message"]
    assert events[-2]["message"] == "Summarize status"
    assert "Summarize status" in events[-1]["message"]
    assert manager.state()["status"] == "idle"


def test_fake_session_records_action_payload(tmp_path):
    init_topic(tmp_path, "Action Topic", "action session")
    manager = FakeCodexSessionManager()
    manager.ensure_session(tmp_path, model=None, effort=None)

    result = manager.send_action("candidate_download_selected", {"candidate_ids": ["CAND-001", "CAND-002"]})

    assert result["ok"] is True
    event = manager.events_since(0)["events"][-1]
    assert event["kind"] == "action"
    assert event["action"] == "candidate_download_selected"
    assert event["payload"] == {"candidate_ids": ["CAND-001", "CAND-002"]}


def test_fake_session_transcript_coalesces_delta_messages(tmp_path):
    init_topic(tmp_path, "Transcript Topic", "transcript replay")
    manager = FakeCodexSessionManager()
    manager.ensure_session(tmp_path, model=None, effort=None)

    manager._append("user_message", message="Browser action: library_read_selected")
    manager._append("action", action="library_read_selected", payload={"bibkeys": ["Smith2024Paper"]})
    manager._append("item/agentMessage/delta", turnId="turn-1", itemId="msg-1", delta="hello ")
    manager._append("item/agentMessage/delta", turnId="turn-1", itemId="msg-1", delta="world")
    manager._append("turn/completed")

    transcript = manager.transcript()

    assert transcript["ok"] is True
    assert transcript["cursor"] == manager.events_since(0)["events"][-1]["cursor"]
    assert transcript["messages"] == [
        {"author": "you", "message": "library_read_selected", "cursor": 3},
        {"author": "codex", "message": "hello world", "cursor": 5},
    ]


def test_fake_session_transcript_filters_routine_read_progress(tmp_path):
    init_topic(tmp_path, "Quiet Read Topic", "quiet read")
    manager = FakeCodexSessionManager()
    manager.ensure_session(tmp_path, model=None, effort=None)

    manager._append("action", action="library_read_selected", payload={"bibkeys": ["Yang2025Dflow"]})
    manager._append("assistant_message", message="Using the topic-local paper_deep_read skill for the reading bundle, after checking the project and topic operating files.")
    manager._append("assistant_message", message="The sandbox cannot start commands because user namespaces are unavailable on this host, so I am rerunning the required file reads outside the sandbox.")
    manager._append("assistant_message", message="The topic-local skill is older, so I am using the project-root contract as requested.")
    manager._append("assistant_message", message="Parsing succeeded and produced the paper index plus page images.")
    manager._append("item/agentMessage/delta", turnId="turn-1", itemId="noise", delta="I have the operating constraints. Next I am ")
    manager._append("item/agentMessage/delta", turnId="turn-1", itemId="noise", delta="checking policy/status.")
    manager._append("item/agentMessage/delta", turnId="turn-1", itemId="summary", delta='{"status":"completed",')
    manager._append("item/agentMessage/delta", turnId="turn-1", itemId="summary", delta='"action":"library_read_selected"}')

    transcript = manager.transcript()
    text = "\n".join(str(message["message"]) for message in transcript["messages"])

    assert "library_read_selected" in text
    assert "Parsing succeeded" in text
    assert '"status":"completed"' in text
    assert "topic-local skill is older" not in text
    assert "sandbox cannot start commands" not in text
    assert "checking policy/status" not in text


def test_fake_session_events_since_returns_ordered_bounded_events(tmp_path):
    init_topic(tmp_path, "Events Topic", "event cursor")
    manager = FakeCodexSessionManager()
    manager.ensure_session(tmp_path, model=None, effort=None)
    manager.send_message("first")
    manager.send_action("work_status", {})
    manager.send_message("second")

    all_events = manager.events_since(0)["events"]
    cursor = all_events[1]["cursor"]
    later = manager.events_since(cursor, limit=2)

    assert [event["cursor"] for event in later["events"]] == [cursor + 1, cursor + 2]
    assert later["next_cursor"] == cursor + 2
    assert later["has_more"] is True


def test_fake_session_reports_failed_and_blocked_states(tmp_path):
    init_topic(tmp_path, "State Topic", "state reporting")
    failed = FakeCodexSessionManager(fail_messages=True)
    failed.ensure_session(tmp_path, model=None, effort=None)

    result = failed.send_message("fail")

    assert result["ok"] is False
    assert failed.state()["status"] == "failed"
    assert "simulated" in failed.state()["blocker"]

    blocked = FakeCodexSessionManager(blocker="codex app-server unavailable")
    blocked.ensure_session(tmp_path, model=None, effort=None)
    assert blocked.state()["status"] == "blocked"
    assert blocked.state()["blocker"] == "codex app-server unavailable"


def test_app_server_reconnect_warning_does_not_poison_completed_turn(tmp_path):
    manager = AppServerCodexSessionManager(codex_bin="/usr/bin/false", project_root=tmp_path)
    manager.status = "running"
    manager.active_turn_id = "turn-1"

    manager._record_notification(
        {
            "method": "error",
            "params": {
                "message": "Reconnecting... 2/5",
                "codexErrorInfo": {"responseStreamDisconnected": {"httpStatusCode": None}},
                "additionalDetails": "request timed out",
            },
        }
    )

    assert manager.state()["status"] == "running"
    assert manager.state()["blocker"] is None
    warning = manager.events_since(0)["events"][-1]
    assert warning["kind"] == "connection_warning"
    assert warning["message"] == "Reconnecting... 2/5 — request timed out"

    manager._record_notification({"method": "turn/completed", "params": {"turn": {"id": "turn-1"}}})

    assert manager.state()["status"] == "idle"
    assert manager.state()["blocker"] is None
    assert manager.transcript()["ok"] is True


def test_app_server_recognizes_nested_reconnect_payload(tmp_path):
    manager = AppServerCodexSessionManager(codex_bin="/usr/bin/false", project_root=tmp_path)
    manager.status = "running"

    manager._record_notification(
        {
            "method": "error",
            "params": {
                "error": {
                    "message": "Reconnecting... 4/5",
                    "codexErrorInfo": {"responseStreamDisconnected": {"httpStatusCode": None}},
                    "additionalDetails": "request timed out",
                }
            },
        }
    )

    assert manager.state()["status"] == "running"
    assert manager.state()["blocker"] is None
    assert manager.events_since(0)["events"][-1]["message"] == "Reconnecting... 4/5 — request timed out"


def test_app_server_terminal_error_remains_blocking(tmp_path):
    manager = AppServerCodexSessionManager(codex_bin="/usr/bin/false", project_root=tmp_path)
    manager.status = "running"

    manager._record_notification({"method": "error", "params": {"error": {"code": "fatal"}}})

    assert manager.state()["status"] == "failed"
    assert manager.state()["blocker"] == '{"code": "fatal"}'


def test_fake_session_does_not_write_business_artifacts(tmp_path):
    init_topic(tmp_path, "No Write Topic", "do not mutate artifacts")
    before = _business_artifact_snapshot(tmp_path)
    manager = FakeCodexSessionManager()
    manager.ensure_session(tmp_path, model=None, effort=None)

    manager.send_message("Mark CAND-001 relevant")
    manager.send_action("candidate_mark_relevant", {"candidate_id": "CAND-001"})

    assert _business_artifact_snapshot(tmp_path) == before


def _business_artifact_snapshot(root: Path) -> dict[str, str | None]:
    paths = [
        "candidates.jsonl",
        "library.bib",
        "papers/CAND-001/metadata.json",
        "papers/CAND-001/paper.pdf",
        "papers/CAND-001/deep_read.json",
    ]
    return {
        path: (root / path).read_text(encoding="utf-8") if (root / path).exists() and not (root / path).is_dir() else None
        for path in paths
    }
