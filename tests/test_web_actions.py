from __future__ import annotations

import json
import threading

from paper_engine.candidates import append_candidates
from paper_engine.codex_worker import CodexEvent, FakeCodexRunner
from paper_engine.topic import init_topic
from paper_engine.web_app import WebApp


class BlockingRunner:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, prompt, cwd, job_dir):
        self.started.set()
        self.release.wait(timeout=5)
        yield CodexEvent(kind="result", payload={"ok": True, "summary": "released"})


def _app(root):
    init_topic(root, "Actions Topic", "serverlet action routing")
    append_candidates(
        root,
        [
            {
                "title": "Action Candidate",
                "authors": ["Ada Lovelace"],
                "year": 2026,
                "abstract": "Candidate abstract.",
                "source": "fixture",
                "status": "new",
            }
        ],
    )
    (root / "library.bib").write_text(
        """
@article{Smith2024Paper,
  author = {Smith, Ada},
  title = {Action Paper},
  year = {2024},
  journal = {Example Venue},
  doi = {10.1000/action},
}
""",
        encoding="utf-8",
    )
    runner = FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "queued"})])
    return WebApp(root, runner=runner)


def _prompt(root, job_id):
    return (root / ".paper_engine" / "jobs" / job_id / "prompt.txt").read_text(encoding="utf-8")


def test_chat_action_enqueues_operation_job(tmp_path):
    app = _app(tmp_path)

    response = app.handle("/api/codex/chat", method="POST", body="message=Summarize+the+topic")
    data = json.loads(response.body)

    assert response.status == 202
    assert data["action"] == "chat"
    prompt = _prompt(tmp_path, data["job_id"])
    assert "The browser UI is the user interface" in prompt
    assert "Summarize the topic" in prompt


def test_score_and_health_actions_enqueue_operation_jobs(tmp_path):
    app = _app(tmp_path)

    score = app.handle("/api/codex/candidates/score", method="POST", body="limit=5")
    score_data = json.loads(score.body)
    assert score.status == 202
    assert score_data["action"] == "candidate-score"
    assert "paper_engine candidates scoring-batch --status new --limit 5 --json" in _prompt(tmp_path, score_data["job_id"])

    # Use a new app/root because only one job may be active at a time.
    other_root = tmp_path / "other"
    app = _app(other_root)
    health = app.handle("/api/codex/health-check", method="POST", body="")
    health_data = json.loads(health.body)
    assert health.status == 202
    assert health_data["action"] == "health-check"
    assert "paper_engine policy check" in _prompt(other_root, health_data["job_id"])


def test_candidate_and_library_actions_only_enqueue_jobs(tmp_path):
    app = _app(tmp_path)

    mark = app.handle("/api/codex/candidates/mark", method="POST", body="candidate_id=CAND-001&decision=relevant")
    mark_data = json.loads(mark.body)
    candidate_line = (tmp_path / "candidates.jsonl").read_text(encoding="utf-8").splitlines()[0]

    assert mark.status == 202
    assert json.loads(candidate_line)["status"] == "new"
    assert "paper_engine candidates mark CAND-001 relevant" in _prompt(tmp_path, mark_data["job_id"])

    other_root = tmp_path / "library"
    app = _app(other_root)
    read = app.handle("/api/codex/library/read", method="POST", body="bibkey=Smith2024Paper")
    read_data = json.loads(read.body)
    assert read.status == 202
    prompt = _prompt(other_root, read_data["job_id"])
    assert "paper_engine read Smith2024Paper --validate-report" in prompt
    assert "If validation, rebuild, and quality audit all pass, skip `Smith2024Paper`" in prompt
    assert "paper_engine read Smith2024Paper --rebuild-note" in prompt
    assert "paper_engine read Smith2024Paper --quality-audit" in prompt
    assert prompt.index("paper_engine read Smith2024Paper --validate-report") < prompt.index("paper_engine read Smith2024Paper --parse-only")
    assert prompt.rindex("paper_engine read Smith2024Paper --rebuild-note") < prompt.rindex("paper_engine read Smith2024Paper --quality-audit")


def test_active_job_conflict_returns_409(tmp_path):
    app = _app(tmp_path)
    runner = BlockingRunner()
    app.runner = runner

    first = app.handle("/api/codex/search", method="POST", body="target_new=3")
    assert runner.started.wait(timeout=2)
    second = app.handle("/api/codex/health-check", method="POST", body="")

    assert first.status == 202
    assert second.status == 409
    assert "active" in json.loads(second.body)["error"]
    runner.release.set()
