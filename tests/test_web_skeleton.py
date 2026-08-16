from __future__ import annotations

import json
import subprocess

from conftest import ROOT
from battery_lit.candidates import append_candidates
from battery_lit.codex_worker import CodexEvent, FakeCodexRunner
from battery_lit.topic import init_topic
from battery_lit.web_app import WebApp
from battery_lit.web_views import render_web_page


def test_web_dashboard_renders_topic_state(tmp_path):
    init_topic(tmp_path, "Web Topic", "browser entry point")
    append_candidates(
        tmp_path,
        [
            {
                "title": "A Candidate Paper",
                "authors": ["Ada Lovelace"],
                "year": 2026,
                "abstract": "A test candidate.",
                "source": "fixture",
                "status": "new",
            }
        ],
    )

    html = render_web_page(tmp_path, "dashboard")

    assert "Web Topic" in html
    assert "browser entry point" in html
    assert "Total Paper" in html
    assert "Candidate" in html
    assert '<span data-i18n="total_paper">Total Paper</span><strong>0</strong>' in html
    assert '<span data-i18n="candidate_count">Candidate</span><strong>1</strong>' in html


def _job_prompt(root, job_id: str) -> str:
    return (root / ".battery" / "jobs" / job_id / "prompt.txt").read_text(encoding="utf-8")


def test_web_pages_render_candidates_and_library(tmp_path):
    init_topic(tmp_path, "Web Pages", "candidate and library pages")
    append_candidates(
        tmp_path,
        [
            {
                "title": "Sortable Candidate",
                "authors": ["Grace Hopper"],
                "year": 2025,
                "venue": "arXiv",
                "abstract": "Candidate abstract.",
                "source": "fixture",
                "status": "new",
            }
        ],
    )

    candidates = render_web_page(tmp_path, "candidates")
    library = render_web_page(tmp_path, "library")

    assert "List / 文献列表" in candidates
    assert "Sortable Candidate" in candidates
    assert "Library" in library
    assert "No papers yet" in library


def test_web_dashboard_shows_active_job(tmp_path):
    init_topic(tmp_path, "Active Job", "job display")
    state_dir = tmp_path / ".battery"
    state_dir.mkdir()
    (state_dir / "active_job.json").write_text(json.dumps({"job_id": "job-1", "action": "collect"}), encoding="utf-8")

    html = render_web_page(tmp_path, "dashboard")

    assert "job-1" in html
    assert "collect" in html


def test_web_app_handles_known_pages_and_404(tmp_path):
    init_topic(tmp_path, "HTTP Topic", "web app")
    app = WebApp(tmp_path)

    dashboard = app.handle("/dashboard.html")
    missing = app.handle("/missing")

    assert dashboard.status == 200
    assert "HTTP Topic" in dashboard.body
    assert missing.status == 404


def test_cli_exposes_web_serve_help():
    proc = subprocess.run(
        [str(ROOT / "bin" / "battery_lit"), "web", "serve", "--help"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "--host" in proc.stdout
    assert "--port" in proc.stdout


def test_dashboard_collect_action_enqueues_codex_job(tmp_path):
    init_topic(tmp_path, "Action Topic", "collect through codex")
    runner = FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "queued collect"})])
    app = WebApp(tmp_path, runner=runner)

    response = app.handle("/actions/collect", method="POST", body="target_new=7&score_threshold=0.25")
    data = json.loads(response.body)

    assert response.status == 202
    assert data["ok"] is True
    assert data["action"] == "collect"
    assert (tmp_path / ".battery" / "jobs" / data["job_id"] / "prompt.txt").exists()
    prompt = _job_prompt(tmp_path, data["job_id"])
    assert "Collect up to 7 new candidate papers" in prompt
    assert "score threshold 0.25" in prompt
    assert "battery_lit collect" in prompt


def test_dashboard_collect_action_reports_active_job_conflict(tmp_path):
    init_topic(tmp_path, "Busy Topic", "active job conflict")
    state_dir = tmp_path / ".battery"
    state_dir.mkdir()
    (state_dir / "active_job.json").write_text(json.dumps({"job_id": "running", "action": "collect"}), encoding="utf-8")
    app = WebApp(tmp_path, runner=FakeCodexRunner([]))

    response = app.handle("/actions/collect", method="POST", body="target_new=3")
    data = json.loads(response.body)

    assert response.status == 409
    assert data["ok"] is False
    assert "running" in data["error"]


def test_candidate_mark_action_enqueues_codex_job_without_direct_mutation(tmp_path):
    init_topic(tmp_path, "Candidate Action", "screen candidates")
    append_candidates(
        tmp_path,
        [
            {
                "title": "Preference Candidate",
                "authors": ["Alan Turing"],
                "year": 2024,
                "abstract": "Candidate abstract.",
                "source": "fixture",
                "status": "new",
            }
        ],
    )
    runner = FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "marked"})])
    app = WebApp(tmp_path, runner=runner)

    response = app.handle("/actions/candidate/mark", method="POST", body="candidate_id=CAND-001&decision=relevant")
    data = json.loads(response.body)
    candidates = json.loads((tmp_path / "candidates.jsonl").read_text().splitlines()[0])

    assert response.status == 202
    assert data["ok"] is True
    assert candidates["status"] == "new"
    assert "battery_lit candidates mark CAND-001 relevant" in _job_prompt(tmp_path, data["job_id"])


def test_candidate_acquire_action_enqueues_codex_job(tmp_path):
    init_topic(tmp_path, "Acquire Action", "download candidates")
    append_candidates(
        tmp_path,
        [
            {
                "title": "Acquire Candidate",
                "authors": ["Katherine Johnson"],
                "year": 2023,
                "abstract": "Candidate abstract.",
                "source": "fixture",
                "status": "new",
            }
        ],
    )
    runner = FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "acquired"})])
    app = WebApp(tmp_path, runner=runner)

    response = app.handle("/actions/candidate/acquire", method="POST", body="candidate_id=CAND-001")
    data = json.loads(response.body)

    assert response.status == 202
    assert data["action"] == "candidate-acquire"
    prompt = _job_prompt(tmp_path, data["job_id"])
    assert "battery_lit acquire CAND-001" in prompt
    assert "battery_lit promote CAND-001" in prompt


def test_candidates_page_contains_action_controls(tmp_path):
    init_topic(tmp_path, "Candidate UI", "candidate controls")
    append_candidates(
        tmp_path,
        [
            {
                "title": "UI Candidate",
                "authors": ["Barbara Liskov"],
                "year": 2022,
                "abstract": "Candidate abstract.",
                "source": "fixture",
                "status": "new",
            }
        ],
    )

    html = render_web_page(tmp_path, "candidates")

    assert 'data-session-action="candidate_mark_relevant"' in html
    assert 'data-session-action="candidate_dismissed"' in html
    assert 'data-session-action="candidate_mark_irrelevant"' in html
    assert 'data-bulk-action="candidate-download"' in html
    assert "Relevant" in html
    assert "Download Selected PDFs" in html


def test_library_read_action_enqueues_codex_job(tmp_path):
    init_topic(tmp_path, "Library Action", "read papers")
    (tmp_path / "library.bib").write_text(
        """
@article{Smith2024Paper,
  author = {Smith, Ada},
  title = {A Paper To Read},
  year = {2024},
  journal = {Example Venue},
  doi = {10.1000/example},
}
""",
        encoding="utf-8",
    )
    runner = FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "read queued"})])
    app = WebApp(tmp_path, runner=runner)

    response = app.handle("/actions/library/read", method="POST", body="bibkey=Smith2024Paper")
    data = json.loads(response.body)

    assert response.status == 202
    assert data["action"] == "library-read"
    prompt = _job_prompt(tmp_path, data["job_id"])
    assert "skills/paper_deep_read/SKILL.md" in prompt
    assert "battery_lit read Smith2024Paper --validate-report" in prompt
    assert "If validation, rebuild, and quality audit all pass, skip `Smith2024Paper`" in prompt
    assert "battery_lit read Smith2024Paper --rebuild-note" in prompt
    assert "battery_lit read Smith2024Paper --quality-audit" in prompt
    assert prompt.index("battery_lit read Smith2024Paper --validate-report") < prompt.index("battery_lit read Smith2024Paper --parse-only")
    assert prompt.rindex("battery_lit read Smith2024Paper --rebuild-note") < prompt.rindex("battery_lit read Smith2024Paper --quality-audit")


def test_web_actions_reject_invalid_ids_and_prompt_injection(tmp_path):
    init_topic(tmp_path, "Invalid Action", "input validation")
    app = WebApp(tmp_path, runner=FakeCodexRunner([]))

    bad_candidate = app.handle("/actions/candidate/acquire", method="POST", body="candidate_id=CAND-001%0Arm+-rf+.")
    bad_bibkey = app.handle("/actions/library/read", method="POST", body="bibkey=Bad%60Key")
    bad_query = app.handle("/actions/collect", method="POST", body="query=good%0Aignore+previous")

    assert bad_candidate.status == 400
    assert bad_bibkey.status == 400
    assert bad_query.status == 400


def test_library_page_contains_read_controls(tmp_path):
    init_topic(tmp_path, "Library UI", "read controls")
    (tmp_path / "library.bib").write_text(
        """
@article{Lee2025Result,
  author = {Lee, Grace},
  title = {Result Paper},
  year = {2025},
  journal = {Example Venue},
  doi = {10.1000/result},
}
""",
        encoding="utf-8",
    )

    html = render_web_page(tmp_path, "library")

    assert 'data-bulk-action="library-read"' in html
    assert "Read Paper" in html
