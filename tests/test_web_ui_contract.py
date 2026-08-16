from __future__ import annotations

from battery_lit.candidates import append_candidates
from battery_lit.topic import init_topic
from battery_lit.web_app import WebApp


def _topic(root):
    init_topic(root, "UI Contract Topic", "contract rendering")
    append_candidates(
        root,
        [
            {
                "title": "UI Candidate",
                "authors": ["Ada Lovelace"],
                "year": 2026,
                "venue": "arXiv",
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
  title = {UI Paper},
  year = {2024},
  journal = {Example Venue},
  doi = {10.1000/ui},
}
""",
        encoding="utf-8",
    )
    return root


def test_ui_shell_has_three_primary_pages_and_no_paper_tab(tmp_path):
    body = WebApp(_topic(tmp_path)).handle("/dashboard.html").body

    assert "/dashboard.html" in body
    assert "/candidates.html" in body
    assert "/library.html" in body
    assert "总览" in body
    assert "文献列表" in body
    assert "文件库" in body
    assert "Paper</a>" not in body
    assert "论文详情</a>" not in body


def test_ui_shell_has_persistent_chat_sidebar_controls(tmp_path):
    body = WebApp(_topic(tmp_path)).handle("/dashboard.html").body

    sidebar_index = body.index('class="chat-sidebar')
    title_index = body.index('data-i18n="codex_console"')
    status_index = body.index("data-session-status")
    model_index = body.index("data-codex-model")
    effort_index = body.index("data-codex-effort")
    composer_index = body.index('class="chat-composer"')

    assert sidebar_index < title_index < status_index < model_index < composer_index
    assert sidebar_index < model_index < composer_index
    assert sidebar_index < effort_index < composer_index
    assert 'class="chat-title-row"' in body
    assert 'class="chat-settings-row"' in body
    assert 'data-session-message-form' in body
    assert 'data-session-status' in body
    assert 'data-session-events' in body
    assert "Codex 操作员" not in body
    assert "Codex Console" in body
    assert '<option value="gpt-5.6-sol" selected>GPT-5.6 Sol</option>' in body
    assert '<option value="gpt-5.6-terra">GPT-5.6 Terra</option>' in body
    assert '<option value="gpt-5.6-luna">GPT-5.6 Luna</option>' in body
    assert '<option value="medium" selected>medium</option>' in body
    assert 'value="gpt-5.4"' not in body
    assert 'value="gpt-5.4-mini"' not in body
    assert 'value="max"' not in body
    assert 'value="ultra"' not in body


def test_frontend_migrates_stale_codex_preferences_to_gpt_5_6_defaults(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert 'const DEFAULT_CODEX_MODEL = "gpt-5.6-sol"' in js
    assert 'const DEFAULT_CODEX_EFFORT = "medium"' in js
    assert "function codexSelectValue" in js
    assert "allowed.has(candidate) ? candidate : fallback" in js
    assert "localStorage.setItem(storageKey, value)" in js


def test_quick_command_chips_live_inside_chat_composer(tmp_path):
    body = WebApp(_topic(tmp_path)).handle("/dashboard.html").body

    composer_index = body.index('class="chat-composer"')
    chips_index = body.index('class="quick-command-chips"')
    textarea_index = body.index("data-session-message-input")

    assert composer_index < chips_index < textarea_index
    assert 'data-session-action="search_30"' in body
    assert 'data-session-action="score_queue"' in body
    assert 'data-session-action="work_status"' in body
    assert 'data-i18n="search_30"' in body
    assert 'data-i18n="score_queue"' in body
    assert 'data-i18n="work_status"' in body
    assert 'data-i18n-placeholder="chat_next_placeholder"' in body
    assert 'data-i18n="stop"' in body
    assert 'data-i18n="clear_view"' in body
    assert 'data-i18n="send"' in body


def test_refresh_is_one_icon_style_control_on_topic_pages(tmp_path):
    app = WebApp(_topic(tmp_path))

    for path in ["/dashboard.html", "/candidates.html", "/library.html"]:
        body = app.handle(path).body
        assert body.count('class="refresh-icon"') == 1
        assert "data-page-refresh" in body
        assert 'data-session-action="refresh"' not in body


def test_frontend_uses_session_api_for_chat_and_actions(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert "/api/session/start" in js
    assert "/api/session/state" in js
    assert "/api/session/transcript" in js
    assert "/api/session/events" in js
    assert "/api/session/message" in js
    assert "/api/session/action" in js
    assert "/api/session/stop" in js
    assert "data-session-message-form" in js
    assert "data-session-action" in js
    assert "data-session-clear" in js


def test_frontend_loads_transcript_snapshot_before_polling_events(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert "function loadSessionTranscript()" in js
    assert "transcriptLoaded" in js
    assert "transcriptLoadPromise" in js
    assert "/api/session/transcript" in js
    assert "transcript.innerHTML = \"\"" in js
    assert "while (hasMore)" in js
    assert "limit=200" in js
    assert 'response.status === 202 || action === "library-read"' not in js


def test_frontend_bounds_codex_console_messages_and_polling(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert "const MAX_SESSION_MESSAGES = 100" in js
    assert "function trimSessionMessages()" in js
    assert "messages.length - MAX_SESSION_MESSAGES" in js
    assert "trimSessionMessages();" in js
    assert "if (activeAssistantMessage?.node === node) activeAssistantMessage = null;" in js
    assert "let sessionPollInFlight = false" in js
    assert "if (sessionPollInFlight) return;" in js
    assert "sessionPollInFlight = true;" in js
    assert "sessionPollInFlight = false;" in js


def test_frontend_filters_routine_codex_read_progress(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert "function isRoutineCodexProgress(message)" in js
    assert "topic-local skill is older" in js
    assert "sandbox cannot start commands" in js
    assert "user namespaces are unavailable" in js


def test_frontend_merges_codex_delta_and_hides_context_percent(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert "appendAssistantDelta(event)" in js
    assert "activeAssistantMessage.text += delta" in js
    assert 'appendSessionMessage("codex", event.delta || "")' not in js
    assert "context_left" not in js
    assert "context ${" not in js


def test_frontend_page_refresh_does_not_enter_codex_session(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert "[data-page-refresh]" in js
    assert 'document.querySelectorAll("[data-session-action]:not([data-bulk-action])")' in js
    assert 'data-session-action="refresh"' not in js


def test_frontend_candidate_selection_updates_download_state(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert "function updateCandidateTabView()" in js
    assert 'node.hidden = showAll' in js
    assert "function updateSelectionState()" in js
    assert 'data-selected-count' in js
    assert 'button.disabled = selected === 0' in js
    assert 'selectedCheckboxes("candidates").map((input) => input.value)' in js
    assert '[data-select-all="candidates"]' in js


def test_frontend_library_selection_updates_read_state(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert 'data-library-selected-count' in js
    assert 'data-bulk-action="library-read"' in js
    assert 'button.disabled = librarySelected === 0' in js
    assert '[data-select-all="library"]' in js
    assert 'table[data-battery-table="library"] tbody input[type="checkbox"]' in js


def test_frontend_translates_admitted_candidate_copy(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert "admitted_candidates_intro" in js
    assert "Admitted candidates only" in js
    assert "仅显示已入队候选" in js


def test_frontend_translates_codex_console_sidebar(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert "codex_console" in js
    assert "Codex Console" in js
    assert "Codex 控制台" in js
    assert 'codex_model: "Model"' in js
    assert 'codex_model: "模型"' in js
    assert "bootstrap_chat_intro" in js
    assert "topic_chat_intro" in js
    assert "chat_next_placeholder" in js
    assert "clear_view" in js


def test_download_selected_button_has_visible_enabled_style(tmp_path):
    css = WebApp(_topic(tmp_path)).handle("/static/style.css").body

    assert ".toolbar .download-selected {" in css
    assert "background: #0f766e;" in css
    assert "color: #ffffff;" in css
    assert ".toolbar .download-selected:disabled" in css


def test_bulk_actions_show_visible_progress_text(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body
    css = WebApp(_topic(tmp_path)).handle("/static/style.css").body

    assert "downloading_selected_pdfs" in js
    assert "reading_selected_papers" in js
    assert "summarizeCandidateDownload(data)" in js
    assert ".library-toolbar button[data-bulk-action=\"library-read\"]:disabled" in css


def test_web_visual_system_has_productized_tokens_and_cards(tmp_path):
    app = WebApp(_topic(tmp_path))
    css = app.handle("/static/style.css").body
    dashboard = app.handle("/dashboard.html").body

    assert "--primary: #e87722;" in css
    assert "--shadow:" in css
    assert ".product-card" in css
    assert ".metric-card" in css
    assert "radial-gradient" in css
    assert 'class="chat-sidebar product-card"' in dashboard
    assert 'class="metric-card"' in dashboard


def test_list_and_library_use_productized_row_classes(tmp_path):
    app = WebApp(_topic(tmp_path))
    candidates = app.handle("/candidates.html").body
    library = app.handle("/library.html").body
    css = app.handle("/static/style.css").body

    assert 'class="table-scroll candidate-list-shell"' in candidates
    assert 'class="paper-list-table candidate-list-table"' in candidates
    assert 'class="paper-row-meta"' in candidates
    assert 'class="meta-chip source"' in candidates
    assert 'class="table-scroll library-list-shell"' in library
    assert 'class="paper-list-table library-list-table"' in library
    assert 'class="bibkey-chip"' in library
    assert ".paper-list-table tbody tr" in css


def test_frontend_binds_session_actions_without_chat_form(tmp_path):
    js = WebApp(_topic(tmp_path)).handle("/static/app.js").body

    assert 'const hasSessionAction = document.querySelector("[data-session-action]")' in js
    assert "if (!form && !hasSessionAction && !hasSessionSurface) return;" in js
    assert "if (form) {" in js
    assert 'document.documentElement.dataset.batteryAppReady = "true";' in js
