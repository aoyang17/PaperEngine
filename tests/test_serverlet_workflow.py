from __future__ import annotations

import json
import time

from battery_lit.candidates import append_candidates
from battery_lit.codex_worker import CodexEvent, FakeCodexRunner
from battery_lit.topic import init_topic
from battery_lit.web_app import WebApp


def test_browser_action_creates_job_and_recent_summary_without_direct_mutation(tmp_path):
    init_topic(tmp_path, "Workflow Topic", "browser-only workflow")
    append_candidates(
        tmp_path,
        [
            {
                "title": "Workflow Candidate",
                "authors": ["Ada Lovelace"],
                "year": 2026,
                "abstract": "Candidate abstract.",
                "source": "fixture",
                "status": "new",
            }
        ],
    )
    before = (tmp_path / "candidates.jsonl").read_text(encoding="utf-8")
    runner = FakeCodexRunner(
        [
            CodexEvent(kind="message", payload={"text": "starting"}),
            CodexEvent(kind="result", payload={"ok": True, "summary": "marked relevant"}),
        ]
    )
    app = WebApp(tmp_path, runner=runner)

    response = app.handle("/api/codex/candidates/mark", method="POST", body="candidate_id=CAND-001&decision=relevant")
    data = json.loads(response.body)

    assert response.status == 202
    job_dir = tmp_path / ".battery" / "jobs" / data["job_id"]
    for _ in range(100):
        if (job_dir / "summary.json").exists():
            break
        time.sleep(0.02)
    assert (job_dir / "prompt.txt").exists()
    assert (job_dir / "events.jsonl").exists()
    assert (job_dir / "summary.json").exists()
    assert (tmp_path / "candidates.jsonl").read_text(encoding="utf-8") == before

    jobs = {"recent_jobs": []}
    for _ in range(100):
        jobs = json.loads(app.handle("/api/jobs").body)
        if jobs["recent_jobs"]:
            break
        time.sleep(0.02)
    assert jobs["active_job"] is None
    assert jobs["recent_jobs"][0]["summary"] == "marked relevant"

    dashboard = app.handle("/dashboard.html").body
    assert "marked relevant" in dashboard
    assert "Total Paper" in dashboard
