from __future__ import annotations

import json

from paper_engine.codex_worker import CodexEvent, FakeCodexRunner
from paper_engine.topic import init_topic, root_from_title
from paper_engine.web_app import WebApp


def _prompt(base_dir, job_id):
    return (base_dir / ".paper_engine_serverlet" / "jobs" / job_id / "prompt.txt").read_text(encoding="utf-8")


def test_bootstrap_mode_renders_create_topic_without_loading_topic(tmp_path, monkeypatch):
    def fail_load_topic(root):
        raise AssertionError("bootstrap page should not load topic.yml")

    monkeypatch.setattr("paper_engine.web_views.load_topic", fail_load_topic)
    app = WebApp(base_dir=tmp_path)

    for path in ["/", "/dashboard.html", "/candidates.html", "/library.html", "/papers/Any.html"]:
        response = app.handle(path)
        assert response.status == 200
        assert "Create Topic" in response.body
        assert "/api/codex/init-topic" in response.body
        assert "Recent Jobs" in response.body
        assert "nav-disabled" in response.body
        assert "Do not inspect sibling topics" in response.body
        assert 'data-session-disabled="true"' in response.body
        assert 'data-session-message-input disabled' in response.body
        assert 'data-page-refresh' in response.body
        assert 'data-session-action="refresh"' not in response.body


def test_bootstrap_rejects_topic_actions_before_init(tmp_path):
    app = WebApp(base_dir=tmp_path)

    response = app.handle("/api/codex/search", method="POST", body="target_new=10")

    assert response.status == 409
    assert "not initialized" in json.loads(response.body)["error"]


def test_bootstrap_init_action_enqueues_clean_room_codex_job(tmp_path):
    runner = FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "queued"})])
    app = WebApp(base_dir=tmp_path, runner=runner)

    response = app.handle(
        "/api/codex/init-topic",
        method="POST",
        body="title=Test+Time+Guidance&direction=Flow+model+test-time+guidance&seed_paper=Seed+Paper",
    )
    data = json.loads(response.body)
    prompt = _prompt(tmp_path, data["job_id"])

    assert response.status == 202
    assert data["action"] == "topic-init"
    assert (tmp_path / ".paper_engine_serverlet" / "jobs" / data["job_id"]).exists()
    assert "templates/skills/topic_init/SKILL.md" in prompt
    assert "/bin/paper_engine" in prompt
    assert " init --base-dir" in prompt
    assert "Test Time Guidance" in prompt
    assert "Flow model test-time guidance" in prompt
    assert "Seed Paper" in prompt
    assert "Do not inspect sibling topic folders" in prompt
    assert "topic.yml" not in prompt


def test_bootstrap_init_defaults_to_direct_project_init(tmp_path):
    app = WebApp(base_dir=tmp_path)

    response = app.handle(
        "/api/codex/init-topic",
        method="POST",
        body="title=Direct+Topic&direction=Direct+direction&seed_paper=Seed+Paper",
    )
    data = json.loads(response.body)
    expected_root = root_from_title(tmp_path, "Direct Topic")

    assert response.status == 202
    assert data["queued"] is False
    assert data["redirect"] == "/dashboard.html"
    assert app.topic_root == expected_root
    assert (expected_root / "topic.yml").exists()
    assert (expected_root / "html" / "dashboard.html").exists()
    assert (tmp_path / ".paper_engine_serverlet" / "jobs" / data["job_id"] / "summary.json").exists()
    assert not (tmp_path / ".paper_engine_serverlet" / "active_job.json").exists()


def test_bootstrap_init_requires_title_and_direction(tmp_path):
    app = WebApp(base_dir=tmp_path)

    no_title = app.handle("/api/codex/init-topic", method="POST", body="direction=Only+direction")
    no_direction = app.handle("/api/codex/init-topic", method="POST", body="title=Only+title")

    assert no_title.status == 400
    assert no_direction.status == 400


def test_bootstrap_binds_after_successful_init_job(tmp_path):
    title = "Test Time Guidance"
    expected_root = root_from_title(tmp_path, title)
    runner = FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "created"})])
    app = WebApp(base_dir=tmp_path, runner=runner)

    response = app.handle(
        "/api/codex/init-topic",
        method="POST",
        body="title=Test+Time+Guidance&direction=Flow+model+test-time+guidance",
    )
    data = json.loads(response.body)
    init_topic(expected_root, title, "Flow model test-time guidance")

    jobs = app.handle("/api/jobs")
    dashboard = app.handle("/dashboard.html")

    assert jobs.status == 200
    assert json.loads(jobs.body)["bound_root"] == str(expected_root)
    assert dashboard.status == 200
    assert "Test Time Guidance" in dashboard.body
    assert "Create Topic" not in dashboard.body
    assert not (tmp_path / ".paper_engine_serverlet" / "active_job.json").exists()


def test_bootstrap_does_not_bind_without_valid_topic_files(tmp_path):
    runner = FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "created"})])
    app = WebApp(base_dir=tmp_path, runner=runner)

    app.handle(
        "/api/codex/init-topic",
        method="POST",
        body="title=Missing+Files&direction=No+topic+files",
    )
    (root_from_title(tmp_path, "Missing Files")).mkdir()

    response = app.handle("/api/jobs")
    dashboard = app.handle("/dashboard.html")

    assert "bound_root" not in json.loads(response.body)
    assert "Create Topic" in dashboard.body


def test_bound_topic_actions_use_topic_job_state(tmp_path):
    title = "Bound Topic"
    expected_root = root_from_title(tmp_path, title)
    init_runner = FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "created"})])
    app = WebApp(base_dir=tmp_path, runner=init_runner)
    app.handle("/api/codex/init-topic", method="POST", body="title=Bound+Topic&direction=Bound+direction")
    init_topic(expected_root, title, "Bound direction")
    app.handle("/api/jobs")
    app.runner = FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "health"})])

    response = app.handle("/api/codex/health-check", method="POST", body="")
    data = json.loads(response.body)

    assert response.status == 202
    assert (expected_root / ".paper_engine" / "jobs" / data["job_id"]).exists()
    assert not (tmp_path / ".paper_engine_serverlet" / "jobs" / data["job_id"]).exists()
