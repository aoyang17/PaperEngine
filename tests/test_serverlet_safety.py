from __future__ import annotations

import json

from battery_lit.codex_worker import CodexEvent, FakeCodexRunner
from battery_lit.prompt_contracts import build_operation_prompt
from battery_lit.topic import init_topic
from battery_lit.web_app import WebApp


def _app(root):
    init_topic(root, "Safety Topic", "serverlet safety")
    return WebApp(root, runner=FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "queued"})]))


def test_chat_accepts_multiline_natural_language(tmp_path):
    app = _app(tmp_path)

    response = app.handle("/api/codex/chat", method="POST", body="message=Please+summarize%0Aand+suggest+next+steps")
    data = json.loads(response.body)

    assert response.status == 202
    prompt = (tmp_path / ".battery" / "jobs" / data["job_id"] / "prompt.txt").read_text(encoding="utf-8")
    assert "Please summarize\nand suggest next steps" in prompt


def test_chat_rejects_control_chars_and_overlong_text(tmp_path):
    app = _app(tmp_path)

    control = app.handle("/api/codex/chat", method="POST", body="message=bad%00input")
    long = app.handle("/api/codex/chat", method="POST", body="message=" + ("a" * 5001))

    assert control.status == 400
    assert long.status == 400


def test_no_shell_bridge_route_exists(tmp_path):
    app = _app(tmp_path)

    response = app.handle("/api/shell", method="POST", body="cmd=rm+-rf+.")

    assert response.status == 404


def test_operation_prompt_reports_blockers_instead_of_improvising(tmp_path):
    prompt = build_operation_prompt("/project/battery", tmp_path, "Do something unsafe.")

    assert "stop and report the blocker" in prompt
    assert "Do not improvise a new workflow" in prompt

