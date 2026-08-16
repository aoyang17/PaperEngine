from __future__ import annotations

import yaml

from battery_lit.candidates import append_candidates, update_candidate
from battery_lit.topic import init_topic
from battery_lit.web_app import WebApp


def _topic_with_content(tmp_path):
    init_topic(tmp_path, "Render Topic", "rendering checks")
    append_candidates(
        tmp_path,
        [
            {
                "title": "Rendered Candidate",
                "authors": ["Ada Lovelace"],
                "year": 2026,
                "venue": "arXiv",
                "abstract": "A candidate used to check the rendered table.",
                "source": "fixture",
                "status": "new",
            }
        ],
    )
    (tmp_path / "library.bib").write_text(
        """
@article{Smith2024Paper,
  author = {Smith, Ada},
  title = {Rendered Paper},
  year = {2024},
  journal = {Example Venue},
  doi = {10.1000/rendered},
}
""",
        encoding="utf-8",
    )
    return tmp_path


def _assert_clean_html(body: str) -> None:
    assert len(body) > 300
    assert "<!doctype html>" in body
    assert "{{" not in body
    assert "{%" not in body
    assert "Undefined" not in body
    assert "Traceback" not in body


def test_web_rendered_pages_are_nonblank_and_linked(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))

    for path in ["/", "/dashboard.html", "/candidates.html", "/library.html"]:
        response = app.handle(path)
        assert response.status == 200
        _assert_clean_html(response.body)
        assert "/dashboard.html" in response.body
        assert "/candidates.html" in response.body
        assert "/library.html" in response.body
        assert "data-codex-model" in response.body
        assert "data-codex-effort" in response.body
        assert "data-language-select" in response.body


def test_web_rendered_pages_contain_expected_workflow_controls(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))

    dashboard = app.handle("/dashboard.html").body
    candidates = app.handle("/candidates.html").body
    library = app.handle("/library.html").body

    assert 'data-session-action="search_30"' in dashboard
    assert 'data-session-action="candidate_mark_relevant"' in candidates
    assert 'data-session-action="candidate_download_selected"' in candidates
    assert 'data-bulk-action="library-read"' in library
    assert "Rendered Candidate" in candidates
    assert "Rendered Paper" in library


def test_workflow_pages_share_single_job_status_container(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))

    for path in ["/dashboard.html", "/candidates.html", "/library.html", "/papers/Smith2024Paper.html"]:
        body = app.handle(path).body
        assert body.count("data-job-status") == 1
        assert "No active job" in body


def test_workflow_pages_show_codex_sandbox_warning(tmp_path, monkeypatch):
    monkeypatch.setattr("battery_lit.web_views.codex_sandbox_warning", lambda: "Codex sandbox namespace is unavailable in this container")
    app = WebApp(_topic_with_content(tmp_path))

    body = app.handle("/dashboard.html").body

    assert "Codex sandbox namespace is unavailable" in body
    assert 'class="job warning"' in body


def test_dashboard_is_session_first_overview(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))

    dashboard = app.handle("/dashboard.html").body

    assert 'data-i18n="total_paper"' in dashboard
    assert '<span data-i18n="total_paper">Total Paper</span><strong>1</strong>' in dashboard
    assert 'data-i18n="candidate_count"' in dashboard
    assert '<span data-i18n="candidate_count">Candidate</span><strong>1</strong>' in dashboard
    assert 'data-i18n="downloaded"' in dashboard
    assert 'data-i18n="read_paper_count"' in dashboard
    assert "/api/codex/chat" not in dashboard
    assert "/api/codex/search" not in dashboard
    assert "/api/codex/candidates/score" not in dashboard
    assert "/api/codex/health-check" not in dashboard
    assert 'data-session-action="search_30"' in dashboard
    assert 'data-session-action="score_queue"' in dashboard
    assert 'data-session-action="work_status"' in dashboard
    assert "external Codex" not in dashboard


def test_dashboard_shows_active_job_without_old_action_forms(tmp_path):
    root = _topic_with_content(tmp_path)
    state_dir = root / ".battery"
    state_dir.mkdir(exist_ok=True)
    (state_dir / "active_job.json").write_text('{"job_id":"job-1","action":"collect"}', encoding="utf-8")

    dashboard = WebApp(root).handle("/dashboard.html").body

    assert "collect" in dashboard
    assert "job-1" in dashboard
    assert 'data-async-action' not in dashboard


def test_web_static_css_route_is_available(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))

    response = app.handle("/static/style.css")

    assert response.status == 200
    assert response.content_type.startswith("text/css")
    assert ".topbar" in response.body


def test_generated_html_routes_are_available_for_reading_results(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))

    css = app.handle("/html/style.css")
    dashboard = app.handle("/html/dashboard.html")
    library = app.handle("/html/library.html")

    assert css.status == 200
    assert css.content_type.startswith("text/css")
    assert dashboard.status == 200
    assert "dashboard" in dashboard.body.lower() or "总览" in dashboard.body
    assert library.status == 200
    assert "Rendered Paper" in library.body


def test_web_static_js_route_is_available(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))

    response = app.handle("/static/app.js")

    assert response.status == 200
    assert response.content_type.startswith("application/javascript")
    assert "batteryTable" in response.body
    assert "fetch(" in response.body
    assert "/api/jobs" in response.body
    assert "battery_codex_model" in response.body
    assert "model_reasoning_effort" not in response.body


def test_candidate_and_library_pages_have_filter_and_sort_controls(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))

    candidates = app.handle("/candidates.html").body
    library = app.handle("/library.html").body

    assert 'data-battery-table="candidates"' in candidates
    assert 'placeholder="Search title, authors, abstract"' in candidates
    assert 'data-filter-field="status"' in candidates
    assert 'data-sort-key="year"' in candidates
    assert 'data-battery-table="library"' in library


def test_four_module_dashboard_and_module_filters_render_in_chinese_by_default(tmp_path):
    root = _topic_with_content(tmp_path)
    topic_path = root / "topic.yml"
    topic = yaml.safe_load(topic_path.read_text(encoding="utf-8"))
    topic["research_modules"] = [
        {
            "id": f"module_{index}",
            "order": index,
            "title_zh": f"模块{index}",
            "title_en": f"Module {index}",
            "description_zh": f"中文说明{index}",
            "description_en": f"English description {index}",
            "strict_scope": index == 1,
        }
        for index in range(1, 5)
    ]
    topic_path.write_text(yaml.safe_dump(topic, sort_keys=False, allow_unicode=True), encoding="utf-8")
    update_candidate(
        root,
        "CAND-001",
        module_ids=["module_1", "module_3"],
        primary_module_id="module_1",
        module_scores={"module_1": 0.9, "module_3": 0.6},
        module_reasons={"module_1": ["match"], "module_3": ["match"]},
        cross_module=True,
        scope_evidence=["evidence"],
    )
    app = WebApp(root)

    dashboard = app.handle("/dashboard.html").body
    candidates = app.handle("/candidates.html").body
    library = app.handle("/library.html").body

    assert '<html lang="zh">' in dashboard
    assert dashboard.count('class="research-module-card"') == 4
    assert 'data-i18n="research_chain"' in dashboard
    assert "Rendered Candidate" in dashboard
    assert 'data-filter-field="module"' in candidates
    assert 'data-module="module_1,module_3"' in candidates
    assert 'data-filter-field="module"' in library
    assert 'placeholder="Search title, bibkey, venue"' in library
    assert 'data-sort-key="venue"' in library


def test_wide_tables_use_scroll_container(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))

    candidates = app.handle("/candidates.html").body
    library = app.handle("/library.html").body
    css = app.handle("/static/style.css").body

    assert 'class="table-scroll candidate-list-shell"' in candidates
    assert 'class="table-scroll library-list-shell"' in library
    assert ".table-scroll" in css
    assert "overflow-x: auto" in css
    assert "white-space: nowrap" in css


def test_codex_chat_bubbles_do_not_force_horizontal_scroll(tmp_path):
    css = WebApp(_topic_with_content(tmp_path)).handle("/static/style.css").body

    assert ".chat-transcript" in css
    assert "overflow-x: hidden" in css
    assert ".chat-message" in css
    assert "min-width: 0" in css
    assert "max-width: 100%" in css
    assert "overflow-wrap: anywhere" in css
    assert "word-break: break-word" in css
    assert "white-space: pre-wrap" in css


def test_candidate_page_has_tabs_filters_details_and_bulk_controls(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))
    candidates = app.handle("/candidates.html").body

    assert 'data-tab-filter="new"' in candidates
    assert 'data-tab-filter="relevant"' in candidates
    assert 'data-tab-filter="irrelevant"' in candidates
    assert 'data-filter-field="venue"' in candidates
    assert 'type="checkbox"' in candidates
    assert "DOI/arXiv/URL" in candidates
    assert 'data-decision="dismissed"' in candidates


def test_library_page_has_selection_and_title_asset_icons(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))
    library = app.handle("/library.html").body

    assert 'data-bulk-action="library-read"' in library
    assert 'data-session-action="library_read_selected"' in library
    assert 'type="checkbox"' in library
    assert 'class="paper-title-icons"' in library
    assert 'data-i18n="assets"' not in library
    assert 'data-i18n="actions"' not in library


def test_web_paper_detail_page_renders_library_entry(tmp_path):
    app = WebApp(_topic_with_content(tmp_path))

    response = app.handle("/papers/Smith2024Paper.html")

    assert response.status == 200
    assert "Rendered Paper" in response.body
    assert "Smith2024Paper" in response.body
    assert "Example Venue" in response.body
