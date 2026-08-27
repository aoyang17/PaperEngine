from __future__ import annotations

import json

from paper_engine.codex_worker import CodexEvent, FakeCodexRunner
from paper_engine.topic import init_topic
from paper_engine.web_app import WebApp
from paper_engine.web_views import render_web_page


def _library_topic(root):
    init_topic(root, "Library Browser", "library workflow")
    (root / "library.bib").write_text(
        """
@article{Smith2024Paper,
  author = {Smith, Ada},
  title = {First Paper},
  year = {2024},
  journal = {Example Venue},
  doi = {10.1000/first},
}
@article{Lee2025Result,
  author = {Lee, Grace},
  title = {Second Paper},
  year = {2025},
  journal = {Example Venue},
  doi = {10.1000/second},
}
""",
        encoding="utf-8",
    )
    paper_dir = root / "papers" / "Smith2024Paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    (paper_dir / "note.md").write_text("# First Paper\n", encoding="utf-8")
    (paper_dir / "reading_result.html").write_text("<!doctype html><title>Reading</title>", encoding="utf-8")


def _prompt(root, job_id):
    return (root / ".paper_engine" / "jobs" / job_id / "prompt.txt").read_text(encoding="utf-8")


def test_library_and_paper_pages_use_session_action_routes(tmp_path):
    _library_topic(tmp_path)

    library = render_web_page(tmp_path, "library")
    paper = render_web_page(tmp_path, "papers/Smith2024Paper.html")

    assert "/api/codex/library/read" not in library
    assert "/api/codex/library/read" not in paper
    assert 'data-bulk-action="library-read"' in library
    assert 'data-session-action="library_read_selected"' in library
    assert "Read Paper" in library


def test_library_title_cell_links_pdf_and_html_note(tmp_path):
    _library_topic(tmp_path)

    library = render_web_page(tmp_path, "library")

    assert 'href="/papers/Smith2024Paper.html"' in library
    assert 'href="/papers/Smith2024Paper/paper.pdf"' in library
    assert 'href="/papers/Smith2024Paper/reading_result.html"' in library
    assert "Knowledge</a>" in library
    assert "note.md" not in library
    assert 'class="paper-title-icons"' in library


def test_library_hides_knowledge_link_until_note_exists(tmp_path):
    _library_topic(tmp_path)
    (tmp_path / "papers" / "Smith2024Paper" / "note.md").unlink()

    library = render_web_page(tmp_path, "library")
    paper = render_web_page(tmp_path, "papers/Smith2024Paper.html")

    assert 'title="PDF"' in library
    assert 'title="Knowledge"' not in library
    assert "Knowledge pending" in paper
    assert 'data-i18n="knowledge">Knowledge</a>' not in paper


def test_web_server_serves_paper_pdf(tmp_path):
    _library_topic(tmp_path)
    app = WebApp(tmp_path)

    response = app.handle("/papers/Smith2024Paper/paper.pdf")

    assert response.status == 200
    assert response.content_type == "application/pdf"
    assert response.body == b"%PDF-1.4\n"


def test_web_server_serves_math_page_images(tmp_path):
    _library_topic(tmp_path)
    math_dir = tmp_path / "papers" / "Smith2024Paper" / "math_pages"
    math_dir.mkdir(parents=True)
    (math_dir / "page-001.png").write_bytes(b"png")
    app = WebApp(tmp_path)

    response = app.handle("/papers/Smith2024Paper/math_pages/page-001.png")

    assert response.status == 200
    assert response.content_type == "image/png"
    assert response.body == b"png"


def test_web_server_serves_paper_reading_result_and_note(tmp_path):
    _library_topic(tmp_path)
    app = WebApp(tmp_path)

    result_response = app.handle("/papers/Smith2024Paper/reading_result.html")
    note_response = app.handle("/papers/Smith2024Paper/note.md")
    css_response = app.handle("/html/style.css")
    library_response = app.handle("/html/library.html")

    assert result_response.status == 200
    assert result_response.content_type == "text/html; charset=utf-8"
    assert "Reading" in result_response.body
    assert note_response.status == 200
    assert note_response.content_type == "text/markdown; charset=utf-8"
    assert "# First Paper" in note_response.body
    assert css_response.status == 200
    assert css_response.content_type == "text/css; charset=utf-8"
    assert library_response.status == 200
    assert library_response.content_type == "text/html; charset=utf-8"


def test_old_paper_html_route_remains_compatible(tmp_path):
    _library_topic(tmp_path)
    app = WebApp(tmp_path)

    response = app.handle("/papers/Smith2024Paper.html")

    assert response.status == 200
    assert "First Paper" in response.body


def test_library_table_is_compact_without_assets_or_actions_columns(tmp_path):
    _library_topic(tmp_path)

    library = render_web_page(tmp_path, "library")

    assert 'data-i18n="assets"' not in library
    assert 'data-i18n="actions"' not in library
    assert 'data-sort-key="venue"' in library
    assert 'data-search-table="library"' in library


def test_library_bulk_read_has_selection_count_and_disabled_default(tmp_path):
    _library_topic(tmp_path)

    library = render_web_page(tmp_path, "library")

    assert 'data-select-all="library"' in library
    assert 'data-library-selected-count' in library
    assert 'data-bulk-action="library-read"' in library
    assert 'data-session-action="library_read_selected"' in library
    assert "disabled" in library


def test_library_read_accepts_multiple_selected_bibkeys(tmp_path):
    _library_topic(tmp_path)
    app = WebApp(tmp_path, runner=FakeCodexRunner([CodexEvent(kind="result", payload={"ok": True, "summary": "queued"})]))

    response = app.handle(
        "/api/codex/library/read",
        method="POST",
        body="bibkey=Smith2024Paper&bibkey=Lee2025Result",
    )
    data = json.loads(response.body)
    prompt = _prompt(tmp_path, data["job_id"])

    assert response.status == 202
    assert data["action"] == "library-read"
    assert "Smith2024Paper" in prompt
    assert "Lee2025Result" in prompt
    assert "Do not start arbitrary nested Codex processes" in prompt
    assert "paper_engine read-many" in prompt
