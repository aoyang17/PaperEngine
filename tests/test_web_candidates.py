from __future__ import annotations

import json

from battery_lit.candidates import append_candidates
from battery_lit.codex_worker import CodexEvent, FakeCodexRunner
from battery_lit.topic import init_topic
from battery_lit.web_app import WebApp
from battery_lit.web_views import render_web_page


def _candidate_topic(root):
    init_topic(root, "Candidate Browser", "candidate workflow")
    append_candidates(
        root,
        [
            {"title": "First Candidate", "authors": ["Ada"], "year": 2026, "venue": "arXiv", "abstract": "First abstract", "source": "arxiv", "status": "new", "score": 0.6, "score_status": "scored"},
            {"title": "Second Candidate", "authors": ["Grace"], "year": 2025, "venue": "ICLR", "abstract": "Second abstract", "source": "crossref", "status": "relevant", "decision": "relevant", "score": 0.8, "score_status": "scored"},
            {"title": "Third Candidate", "authors": ["Alan"], "year": 2024, "venue": "Workshop", "abstract": "Third abstract", "source": "openalex", "status": "irrelevant", "decision": "irrelevant", "score": -0.4, "score_status": "scored"},
            {"title": "Fourth Candidate", "authors": ["Katherine"], "year": 2023, "venue": "unknown", "abstract": "Fourth abstract", "source": "fixture", "status": "dismissed", "decision": "dismissed", "score": 0.0, "score_status": "unscored"},
        ],
    )


def _prompt(root, job_id):
    return (root / ".battery" / "jobs" / job_id / "prompt.txt").read_text(encoding="utf-8")


def test_candidate_page_uses_session_action_routes(tmp_path):
    _candidate_topic(tmp_path)

    html = render_web_page(tmp_path, "candidates")

    assert "/api/codex/candidates/mark" not in html
    assert "/api/codex/candidates/download" not in html
    assert "/api/codex/candidates/dismiss" not in html
    assert 'data-session-action="candidate_download_selected"' in html
    assert 'data-session-action="candidate_mark_relevant"' in html
    assert 'data-session-action="candidate_dismissed"' in html
    assert 'data-session-action="candidate_mark_irrelevant"' in html
    assert 'data-bulk-action="candidate-download"' in html
    assert 'type="checkbox"' in html
    assert 'data-select-all="candidates"' in html
    assert 'data-selected-count' in html
    assert 'class="download-selected"' in html
    assert 'data-bulk-action="candidate-download" data-session-action="candidate_download_selected" data-i18n="download_selected_pdfs" disabled' in html
    assert "All" in html
    assert "Queue" in html
    assert "Relevant" in html
    assert "Irrelevant" in html


def test_candidate_page_has_compact_filters_sort_and_abstract_details(tmp_path):
    _candidate_topic(tmp_path)

    html = render_web_page(tmp_path, "candidates")

    assert 'data-tab-filter="all"' in html
    assert 'data-tab-filter="new"' in html
    assert 'data-tab-filter="relevant"' in html
    assert 'data-tab-filter="irrelevant"' in html
    assert 'data-search-table="candidates"' in html
    assert 'data-filter-field="venue"' in html
    assert 'data-filter-field="pdf"' in html
    assert '<option value="" data-i18n="all">All</option>' in html
    assert '<option value="yes" data-i18n="has_pdf">Has PDF</option>' in html
    assert '<option value="no" data-i18n="no_pdf">No PDF</option>' in html
    assert 'data-sort-key="score"' in html
    assert 'data-sort-key="year"' in html
    assert 'class="score-source"' in html
    assert "0.60" in html
    assert 'data-i18n="unscored">Unscored' in html
    assert 'class="relevance-column"' in html
    assert "Abstract" in html
    assert "First abstract" in html


def test_candidate_page_shows_pdf_icon_only_for_existing_pdfs(tmp_path):
    _candidate_topic(tmp_path)
    incoming = tmp_path / "papers" / "_incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    (incoming / "CAND-001.pdf").write_bytes(b"%PDF-1.4\nincoming")
    final_dir = tmp_path / "papers" / "Grace2025Second"
    final_dir.mkdir(parents=True, exist_ok=True)
    (final_dir / "paper.pdf").write_bytes(b"%PDF-1.4\nfinal")
    records = [json.loads(line) for line in (tmp_path / "candidates.jsonl").read_text(encoding="utf-8").splitlines()]
    records[1]["bibkey"] = "Grace2025Second"
    (tmp_path / "candidates.jsonl").write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

    html = render_web_page(tmp_path, "candidates")
    incoming_response = WebApp(tmp_path).handle("/incoming/CAND-001.pdf")
    bad_response = WebApp(tmp_path).handle("/incoming/../CAND-001.pdf")

    assert 'href="/incoming/CAND-001.pdf"' in html
    assert 'href="/papers/Grace2025Second/paper.pdf"' in html
    assert 'href="/incoming/CAND-003.pdf"' not in html
    assert 'data-id="CAND-001"' in html and 'data-pdf="yes"' in html
    assert 'data-id="CAND-003"' in html and 'data-pdf="no"' in html
    assert incoming_response.status == 200
    assert incoming_response.content_type == "application/pdf"
    assert incoming_response.body.startswith(b"%PDF-")
    assert bad_response.status == 404


def test_candidate_tabs_order_and_all_semantics(tmp_path):
    _candidate_topic(tmp_path)

    html = render_web_page(tmp_path, "candidates")

    queue = html.index('data-tab-filter="new"')
    all_tab = html.index('data-tab-filter="all"')
    relevant = html.index('data-tab-filter="relevant"')
    irrelevant = html.index('data-tab-filter="irrelevant"')
    assert queue < all_tab < relevant < irrelevant
    assert 'data-i18n="admitted_candidates_intro"' in html
    assert "Admitted candidates only" in html


def test_candidate_relevance_buttons_reflect_existing_preferences(tmp_path):
    _candidate_topic(tmp_path)

    html = render_web_page(tmp_path, "candidates")

    assert 'data-decision="relevant"' in html
    assert 'data-decision="irrelevant"' in html
    assert 'data-decision="dismissed"' in html
    assert 'class="relevance-button active relevant"' in html
    assert 'class="relevance-button active irrelevant"' in html
    assert 'class="relevance-button active dismissed"' in html


def test_candidate_download_accepts_multiple_selected_ids(tmp_path):
    _candidate_topic(tmp_path)
    app = WebApp(tmp_path, runner=FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "queued"})]))

    response = app.handle(
        "/api/codex/candidates/download",
        method="POST",
        body="candidate_id=CAND-001&candidate_id=CAND-002",
    )
    data = json.loads(response.body)
    prompt = _prompt(tmp_path, data["job_id"])

    assert response.status == 202
    assert data["action"] == "candidate-acquire"
    assert "CAND-001" in prompt
    assert "CAND-002" in prompt
    assert json.loads((tmp_path / "candidates.jsonl").read_text().splitlines()[0])["status"] == "new"
