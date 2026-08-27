from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import threading

from paper_engine.candidates import append_candidates, get_candidate
from paper_engine.codex_session import FakeCodexSessionManager
from paper_engine.topic import init_topic, load_preferences
from paper_engine.web_app import WebApp


def _app(root, manager=None):
    init_topic(root, "Session API Topic", "session api")
    return WebApp(root, session_manager=manager or FakeCodexSessionManager())


def test_session_start_returns_metadata(tmp_path):
    app = _app(tmp_path)

    response = app.handle("/api/session/start", method="POST", body="codex_model=gpt-5.6-sol&codex_effort=medium")
    data = json.loads(response.body)

    assert response.status == 200
    assert data["ok"] is True
    assert data["topic_root"] == str(tmp_path.resolve())
    assert data["model"] == "gpt-5.6-sol"
    assert data["effort"] == "medium"


def test_web_app_creates_one_session_manager_under_concurrent_access(tmp_path, monkeypatch):
    init_topic(tmp_path, "Concurrent Session API Topic", "concurrent session api")
    app = WebApp(tmp_path)
    created: list[FakeCodexSessionManager] = []
    barrier = threading.Barrier(8)

    def create_manager(*, project_root):
        manager = FakeCodexSessionManager()
        created.append(manager)
        return manager

    monkeypatch.setattr("paper_engine.web_app.AppServerCodexSessionManager", create_manager)

    def get_session(_: int):
        barrier.wait()
        return app._session()

    with ThreadPoolExecutor(max_workers=8) as executor:
        managers = list(executor.map(get_session, range(8)))

    assert len(created) == 1
    assert all(manager is created[0] for manager in managers)


def test_session_message_enters_session_without_job_artifacts(tmp_path):
    manager = FakeCodexSessionManager()
    app = _app(tmp_path, manager)

    response = app.handle("/api/session/message", method="POST", body=json.dumps({"message": "Search 30 candidates"}))
    data = json.loads(response.body)

    assert response.status == 202
    assert data["ok"] is True
    assert not (tmp_path / ".paper_engine" / "jobs").exists()
    events = manager.events_since(0)["events"]
    assert any(event["kind"] == "user_message" and event["message"] == "Search 30 candidates" for event in events)


def test_session_action_accepts_structured_payload(tmp_path):
    manager = FakeCodexSessionManager()
    app = _app(tmp_path, manager)

    response = app.handle(
        "/api/session/action",
        method="POST",
        body=json.dumps({"action": "work_status", "payload": {}}),
    )
    data = json.loads(response.body)

    assert response.status == 202
    assert data["ok"] is True
    event = manager.events_since(0)["events"][-1]
    assert event["kind"] == "action"
    assert event["action"] == "work_status"
    assert event["payload"] == {}
    assert not (tmp_path / ".paper_engine" / "jobs").exists()


def test_candidate_download_session_action_updates_state_directly(tmp_path, monkeypatch):
    manager = FakeCodexSessionManager()
    app = _app(tmp_path, manager)
    append_candidates(
        tmp_path,
        [
            {
                "title": "Direct Download Paper",
                "authors": ["Ada Lovelace"],
                "year": 2026,
                "venue": "arXiv",
                "abstract": "A test candidate.",
                "source": "fixture",
                "status": "relevant",
            }
        ],
    )

    def fake_acquire(root, candidate_id):
        assert candidate_id == "CAND-001"
        return {"ok": True, "candidate_id": candidate_id, "status": "downloaded", "pdf": "incoming/CAND-001.pdf"}

    def fake_enrich(root, candidate_id, live=False):
        assert candidate_id == "CAND-001"
        assert live is True
        return {"title": "Direct Download Paper", "year": 2026}

    def fake_promote(root, candidate_id):
        assert candidate_id == "CAND-001"
        return {"ok": True, "bibkey": "Lovelace2026Direct", "status": "promoted"}

    monkeypatch.setattr("paper_engine.web_app.enrich_candidate", fake_enrich)
    monkeypatch.setattr("paper_engine.web_app.acquire_pdf", fake_acquire)
    monkeypatch.setattr("paper_engine.web_app.promote_candidate", fake_promote)
    monkeypatch.setattr("paper_engine.web_app.build_html", lambda root: {"ok": True})

    response = app.handle(
        "/api/session/action",
        method="POST",
        body=json.dumps({"action": "candidate_download_selected", "payload": {"candidate_ids": ["CAND-001"]}}),
    )
    data = json.loads(response.body)

    assert response.status == 200
    assert data["ok"] is True
    assert data["results"][0]["promote"]["bibkey"] == "Lovelace2026Direct"
    assert manager.events_since(0)["events"] == []
    assert not (tmp_path / ".paper_engine" / "jobs").exists()


def test_candidate_download_session_action_skips_existing_pdf(tmp_path, monkeypatch):
    manager = FakeCodexSessionManager()
    app = _app(tmp_path, manager)
    append_candidates(
        tmp_path,
        [
            {
                "title": "Existing PDF Paper",
                "authors": ["Ada Lovelace"],
                "year": 2026,
                "venue": "arXiv",
                "abstract": "A test candidate.",
                "source": "fixture",
                "status": "in_library",
                "bibkey": "Lovelace2026Existing",
                "doi": "10.1000/existing",
            }
        ],
    )
    (tmp_path / "library.bib").write_text(
        """
@article{Lovelace2026Existing,
  author = {Lovelace, Ada},
  title = {Existing PDF Paper},
  year = {2026},
  journal = {arXiv},
  doi = {10.1000/existing},
}
""",
        encoding="utf-8",
    )
    paper_dir = tmp_path / "papers" / "Lovelace2026Existing"
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "paper.pdf").write_bytes(b"%PDF-1.4\nexisting")

    def fake_enrich(root, candidate_id, live=False):
        assert candidate_id == "CAND-001"
        return {"title": "Existing PDF Paper", "year": 2026}

    monkeypatch.setattr("paper_engine.web_app.enrich_candidate", fake_enrich)
    monkeypatch.setattr("paper_engine.web_app.build_html", lambda root: {"ok": True})

    response = app.handle(
        "/api/session/action",
        method="POST",
        body=json.dumps({"action": "candidate_download_selected", "payload": {"candidate_ids": ["CAND-001"]}}),
    )
    data = json.loads(response.body)

    assert response.status == 200
    assert data["ok"] is True
    assert data["results"][0]["acquire"]["status"] == "skipped_existing"
    assert data["results"][0]["promote"]["status"] == "already_promoted"
    assert (paper_dir / "paper.pdf").read_bytes().startswith(b"%PDF-")


def test_candidate_preference_session_action_updates_state_directly(tmp_path):
    manager = FakeCodexSessionManager()
    app = _app(tmp_path, manager)
    append_candidates(
        tmp_path,
        [
            {
                "title": "Direct Preference Paper",
                "authors": ["Ada Lovelace"],
                "year": 2026,
                "venue": "arXiv",
                "abstract": "A test candidate.",
                "source": "fixture",
                "status": "new",
            }
        ],
    )

    response = app.handle(
        "/api/session/action",
        method="POST",
        body=json.dumps({"action": "candidate_mark_relevant", "payload": {"candidate_id": "CAND-001"}}),
    )
    data = json.loads(response.body)

    assert response.status == 200
    assert data["ok"] is True
    assert get_candidate(tmp_path, "CAND-001")["status"] == "relevant"
    assert get_candidate(tmp_path, "CAND-001")["decision"] == "relevant"
    assert load_preferences(tmp_path)["effective_feedbacks"] == 1
    assert manager.events_since(0)["events"] == []
    assert not (tmp_path / ".paper_engine" / "jobs").exists()


def test_candidate_preference_session_action_does_not_double_count_repeat_click(tmp_path):
    manager = FakeCodexSessionManager()
    app = _app(tmp_path, manager)
    append_candidates(
        tmp_path,
        [
            {
                "title": "Repeat Preference Paper",
                "authors": ["Ada Lovelace"],
                "year": 2026,
                "venue": "arXiv",
                "abstract": "A test candidate.",
                "source": "fixture",
                "status": "new",
            }
        ],
    )

    body = json.dumps({"action": "candidate_mark_relevant", "payload": {"candidate_id": "CAND-001"}})
    app.handle("/api/session/action", method="POST", body=body)
    app.handle("/api/session/action", method="POST", body=body)

    assert load_preferences(tmp_path)["effective_feedbacks"] == 1


def test_session_events_are_cursor_bounded(tmp_path):
    app = _app(tmp_path)
    app.handle("/api/session/message", method="POST", body=json.dumps({"message": "one"}))
    app.handle("/api/session/action", method="POST", body=json.dumps({"action": "work_status", "payload": {}}))

    response = app.handle("/api/session/events?cursor=1&limit=2")
    data = json.loads(response.body)

    assert response.status == 200
    assert data["ok"] is True
    assert len(data["events"]) == 2
    assert data["next_cursor"] == data["events"][-1]["cursor"]


def test_session_transcript_returns_coalesced_snapshot(tmp_path):
    manager = FakeCodexSessionManager()
    app = _app(tmp_path, manager)
    app.handle("/api/session/start", method="POST", body="")
    manager._append("user_message", message="Browser action: library_read_selected")
    manager._append("action", action="library_read_selected", payload={"bibkeys": ["Smith2024Paper"]})
    manager._append("item/agentMessage/delta", turnId="turn-1", itemId="msg-1", delta="reading ")
    manager._append("item/agentMessage/delta", turnId="turn-1", itemId="msg-1", delta="done")

    response = app.handle("/api/session/transcript")
    data = json.loads(response.body)

    assert response.status == 200
    assert data["ok"] is True
    assert data["messages"] == [
        {"author": "you", "message": "library_read_selected", "cursor": 3},
        {"author": "codex", "message": "reading done", "cursor": 5},
    ]
    assert data["cursor"] == 5


def test_session_transcript_filters_routine_read_progress(tmp_path):
    manager = FakeCodexSessionManager()
    app = _app(tmp_path, manager)
    app.handle("/api/session/start", method="POST", body="")
    manager._append("action", action="library_read_selected", payload={"bibkeys": ["Yang2025Dflow"]})
    manager._append("assistant_message", message="The topic-local skill is older, so I am using the project-root contract as requested.")
    manager._append("assistant_message", message="Parsing succeeded and produced the paper index plus page images.")

    response = app.handle("/api/session/transcript")
    data = json.loads(response.body)
    text = "\n".join(message["message"] for message in data["messages"])

    assert response.status == 200
    assert "Parsing succeeded" in text
    assert "topic-local skill is older" not in text


def test_session_state_exposes_blocker_and_context_left(tmp_path):
    manager = FakeCodexSessionManager(blocker="codex app-server unavailable")
    app = _app(tmp_path, manager)

    start = app.handle("/api/session/start", method="POST", body="")
    state = app.handle("/api/session/state")

    assert start.status == 503
    assert json.loads(start.body)["blocker"] == "codex app-server unavailable"
    assert state.status == 200
    assert json.loads(state.body)["status"] == "blocked"
    assert json.loads(state.body)["context_left"] is None


def test_session_rejects_second_turn_while_running(tmp_path):
    class RunningSession(FakeCodexSessionManager):
        def state(self):
            state = super().state()
            state["status"] = "running"
            return state

    app = _app(tmp_path, RunningSession())
    app.handle("/api/session/start", method="POST", body="")

    response = app.handle("/api/session/message", method="POST", body=json.dumps({"message": "second"}))

    assert response.status == 409
    assert "already running" in json.loads(response.body)["error"]


def test_session_stop_routes_to_manager(tmp_path):
    manager = FakeCodexSessionManager()
    app = _app(tmp_path, manager)
    app.handle("/api/session/start", method="POST", body="")

    response = app.handle("/api/session/stop", method="POST", body="")
    data = json.loads(response.body)

    assert response.status == 200
    assert data["ok"] is True
