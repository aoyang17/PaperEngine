from __future__ import annotations

import json
import threading

from paper_engine.candidates import append_candidates
from paper_engine.codex_worker import CodexEvent, FakeCodexRunner
from paper_engine.topic import init_topic
from paper_engine.web_app import ALLOWED_CODEX_EFFORTS, ALLOWED_CODEX_MODELS, WebApp


class BlockingRunner:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, prompt, cwd, job_dir):
        self.started.set()
        self.release.wait(timeout=5)
        yield CodexEvent(kind="result", payload={"ok": True, "summary": "done"})


def _app(tmp_path):
    init_topic(tmp_path, "API Topic", "api routes")
    append_candidates(
        tmp_path,
        [
            {
                "title": "API Candidate",
                "authors": ["Ada Lovelace"],
                "year": 2026,
                "abstract": "API candidate abstract.",
                "source": "fixture",
                "status": "new",
            }
        ],
    )
    (tmp_path / "library.bib").write_text(
        """
@article{Smith2024Paper,
  author = {Smith, Ada},
  title = {API Paper},
  year = {2024},
  journal = {Example Venue},
  doi = {10.1000/api},
}
""",
        encoding="utf-8",
    )
    runner = FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "done"})])
    return WebApp(tmp_path, runner=runner), runner


def test_api_status_and_jobs(tmp_path):
    app, _ = _app(tmp_path)

    status = json.loads(app.handle("/api/status").body)
    jobs = json.loads(app.handle("/api/jobs").body)

    assert status["ok"] is True
    assert status["candidates"] == 1
    assert jobs["active_job"] is None
    assert jobs["recent_jobs"] == []


def test_api_codex_dashboard_actions(tmp_path):
    app, _ = _app(tmp_path)

    search = json.loads(app.handle("/api/codex/search", method="POST", body="target_new=3&score_threshold=0.2&codex_model=gpt-5.6-sol&codex_effort=medium").body)
    assert search["ok"] is True
    assert search["queued"] is True


def test_api_rejects_unsupported_codex_model_or_effort(tmp_path):
    app, _ = _app(tmp_path)

    bad_model = app.handle("/api/codex/search", method="POST", body="target_new=3&codex_model=not-a-model")
    bad_effort = app.handle("/api/codex/search", method="POST", body="target_new=3&codex_effort=extreme")
    old_model = app.handle("/api/codex/search", method="POST", body="target_new=3&codex_model=gpt-5.4")
    max_effort = app.handle("/api/codex/search", method="POST", body="target_new=3&codex_effort=max")
    ultra_effort = app.handle("/api/codex/search", method="POST", body="target_new=3&codex_effort=ultra")

    assert bad_model.status == 400
    assert "unsupported codex model" in json.loads(bad_model.body)["error"]
    assert bad_effort.status == 400
    assert "unsupported codex effort" in json.loads(bad_effort.body)["error"]
    assert old_model.status == 400
    assert max_effort.status == 400
    assert ultra_effort.status == 400


def test_web_codex_catalog_matches_supported_gpt_5_6_profile():
    assert ALLOWED_CODEX_MODELS == {
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-5.5",
        "gpt-5.3-codex-spark",
    }
    assert ALLOWED_CODEX_EFFORTS == {"low", "medium", "high", "xhigh"}


def test_api_reports_busy_when_job_active(tmp_path):
    app, _ = _app(tmp_path)
    runner = BlockingRunner()
    app.runner = runner

    search = json.loads(app.handle("/api/codex/search", method="POST", body="target_new=3&score_threshold=0.2").body)
    assert search["ok"] is True
    assert runner.started.wait(timeout=2)

    html = json.loads(app.handle("/api/codex/html-build", method="POST", body="").body)
    assert html["ok"] is False
    assert "active" in html["error"]
    runner.release.set()


def test_api_chat_action_is_bounded(tmp_path):
    app, _ = _app(tmp_path)

    response = app.handle("/api/codex/chat", method="POST", body="message=Summarize+topic+status")
    data = json.loads(response.body)

    assert response.status == 202
    assert data["action"] == "chat"
    prompt = (tmp_path / ".paper_engine" / "jobs" / data["job_id"] / "prompt.txt").read_text(encoding="utf-8")
    assert "Summarize topic status" in prompt
    assert "Do not perform shell commands unless required" in prompt


def test_api_candidate_actions(tmp_path):
    app, _ = _app(tmp_path)
    runner = BlockingRunner()
    app.runner = runner

    mark = app.handle("/api/codex/candidates/mark", method="POST", body="candidate_id=CAND-001&decision=relevant")
    assert mark.status == 202
    assert runner.started.wait(timeout=2)

    busy = json.loads(app.handle("/api/codex/candidates/dismiss", method="POST", body="candidate_id=CAND-001").body)
    assert busy["ok"] is False
    assert "active" in busy["error"]
    runner.release.set()


def test_api_library_rebuild_action(tmp_path):
    app, _ = _app(tmp_path)

    response = app.handle("/api/codex/library/rebuild-html", method="POST", body="bibkey=Smith2024Paper")
    data = json.loads(response.body)

    assert response.status == 202
    assert data["action"] == "library-rebuild-html"
    prompt = (tmp_path / ".paper_engine" / "jobs" / data["job_id"] / "prompt.txt").read_text(encoding="utf-8")
    assert "paper_engine html build" in prompt
