from __future__ import annotations

import json
from pathlib import Path

from paper_engine.codex_worker import CodexEvent, FakeCodexRunner
from paper_engine.jobs import JobManager
from paper_engine.topic import init_topic
from paper_engine.web_app import WebApp


def _finished_job(root: Path) -> str:
    runner = FakeCodexRunner(
        [
            CodexEvent(kind="message", payload={"text": "working"}),
            CodexEvent(kind="result", payload={"ok": True, "summary": "finished"}),
        ]
    )
    result = JobManager(root, runner=runner, project_root=Path("/project/paper-engine")).run_job("Health check", action="health")
    return str(result["job_id"])


def test_job_detail_api_returns_summary(tmp_path):
    init_topic(tmp_path, "Jobs Topic", "job detail")
    job_id = _finished_job(tmp_path)
    app = WebApp(tmp_path)

    response = app.handle(f"/api/jobs/{job_id}")
    data = json.loads(response.body)

    assert response.status == 200
    assert data["ok"] is True
    assert data["job"]["job_id"] == job_id
    assert data["job"]["action"] == "health"
    assert data["job"]["summary"] == "finished"
    assert data["job"]["event_count"] == 2


def test_job_events_api_returns_bounded_events(tmp_path):
    init_topic(tmp_path, "Events Topic", "job events")
    job_id = _finished_job(tmp_path)
    app = WebApp(tmp_path)

    response = app.handle(f"/api/jobs/{job_id}/events")
    data = json.loads(response.body)

    assert response.status == 200
    assert data["ok"] is True
    assert data["job_id"] == job_id
    assert [event["kind"] for event in data["events"]] == ["message", "result"]


def test_job_events_api_reads_only_tail(tmp_path, monkeypatch):
    init_topic(tmp_path, "Many Events Topic", "job events")
    job_id = "20260101T000000Z-deadbeef"
    job_dir = tmp_path / ".paper_engine" / "jobs" / job_id
    job_dir.mkdir(parents=True)
    with (job_dir / "events.jsonl").open("w", encoding="utf-8") as handle:
        for index in range(500):
            handle.write(json.dumps({"kind": "message", "payload": {"index": index}}) + "\n")

    def fail_read_text(self, *args, **kwargs):
        if self.name == "events.jsonl":
            raise AssertionError("events endpoint should not read the full events file")
        return original_read_text(self, *args, **kwargs)

    original_read_text = Path.read_text
    monkeypatch.setattr(Path, "read_text", fail_read_text)

    response = WebApp(tmp_path).handle(f"/api/jobs/{job_id}/events")
    data = json.loads(response.body)

    assert response.status == 200
    assert len(data["events"]) == 200
    assert data["events"][0]["payload"]["index"] == 300
    assert data["events"][-1]["payload"]["index"] == 499


def test_job_apis_reject_invalid_or_missing_ids(tmp_path):
    init_topic(tmp_path, "Invalid Jobs", "job safety")
    app = WebApp(tmp_path)

    invalid = app.handle("/api/jobs/../topic.yml")
    missing = app.handle("/api/jobs/20260101T000000Z-deadbeef")

    assert invalid.status == 400
    assert missing.status == 404


def test_job_events_do_not_read_outside_jobs_dir(tmp_path):
    init_topic(tmp_path, "Safe Jobs", "job boundaries")
    app = WebApp(tmp_path)

    response = app.handle("/api/jobs/%2e%2e%2ftopic.yml/events")

    assert response.status == 400
    assert "topic.yml" not in response.body
