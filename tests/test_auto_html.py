from __future__ import annotations

import json
import os
import subprocess

from conftest import ROOT, fixture_path


def _run(*args: str, env: dict[str, str] | None = None) -> dict:
    proc = subprocess.run(
        [str(ROOT / "bin" / "paper_engine"), *args],
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return json.loads(proc.stdout)


def _write_reading_bundle(root, bibkey):
    paper_dir = root / "papers" / bibkey
    deep_read = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    source_map = json.loads(fixture_path("source_map.json").read_text(encoding="utf-8"))
    paper_index = json.loads(fixture_path("paper_index.json").read_text(encoding="utf-8"))
    note_plan = json.loads(fixture_path("note_plan.json").read_text(encoding="utf-8"))
    deep_read["bibkey"] = bibkey
    deep_read["pdf_path"] = f"papers/{bibkey}/paper.pdf"
    deep_read["parsed_markdown_path"] = f"papers/{bibkey}/parsed.md"
    deep_read["source_map_path"] = f"papers/{bibkey}/source_map.json"
    source_map["paper"]["bibkey"] = bibkey
    source_map["paper"]["pdf_path"] = f"papers/{bibkey}/paper.pdf"
    source_map["paper"]["parsed_markdown_path"] = f"papers/{bibkey}/parsed.md"
    for item in paper_index.get("figures_tables", []):
        if item.get("candidate_image_paths"):
            item["candidate_image_paths"] = [path.replace("Example2026A", bibkey) for path in item["candidate_image_paths"]]
    (paper_dir / "source_map.json").write_text(json.dumps(source_map, indent=2), encoding="utf-8")
    (paper_dir / "paper_index.json").write_text(json.dumps(paper_index, indent=2), encoding="utf-8")
    (paper_dir / "note_plan.json").write_text(json.dumps(note_plan, indent=2), encoding="utf-8")
    (paper_dir / "deep_read.json").write_text(json.dumps(deep_read, indent=2), encoding="utf-8")


def test_collect_refreshes_candidates_html_without_manual_build(tmp_path):
    _run("init", "--root", str(tmp_path), "--title", "Auto HTML", "--direction", "test-time guidance")

    _run("collect", "--root", str(tmp_path), "--fixture", str(fixture_path("search_results.json")), "--target-new", "5")

    candidates_html = (tmp_path / "html" / "candidates.html").read_text(encoding="utf-8")
    assert "A Paper" in candidates_html
    assert "CAND-001" in candidates_html


def test_candidate_score_and_mark_refresh_candidates_html(tmp_path):
    _run("init", "--root", str(tmp_path), "--title", "Auto HTML", "--direction", "test-time guidance")
    _run("collect", "--root", str(tmp_path), "--fixture", str(fixture_path("search_results.json")), "--target-new", "5")
    scores = tmp_path / "scores.jsonl"
    scores.write_text(
        json.dumps(
            {
                "candidate_id": "CAND-001",
                "content": 0.55,
                "preference": 0.05,
                "credibility": 0.0,
                "score": 0.6,
                "score_confidence": "medium",
                "reasons": ["Relevant to the topic."],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    _run("candidates", "apply-scores", "--root", str(tmp_path), "--scores", str(scores))
    scored_html = (tmp_path / "html" / "candidates.html").read_text(encoding="utf-8")
    assert "0.60" in scored_html

    _run("candidates", "mark", "--root", str(tmp_path), "CAND-001", "relevant")
    marked_html = (tmp_path / "html" / "candidates.html").read_text(encoding="utf-8")
    assert "relevant" in marked_html


def test_promote_and_rebuild_note_refresh_library_and_paper_html(tmp_path):
    _run("init", "--root", str(tmp_path), "--title", "Auto HTML", "--direction", "test-time guidance")
    _run("collect", "--root", str(tmp_path), "--fixture", str(fixture_path("search_results.json")), "--target-new", "5")
    _run("acquire", "--root", str(tmp_path), "CAND-001", "--manual-pdf", str(fixture_path("example.pdf")))
    promoted = _run("promote", "--root", str(tmp_path), "CAND-001")
    bibkey = promoted["bibkey"]

    library_html = (tmp_path / "html" / "library.html").read_text(encoding="utf-8")
    assert bibkey in library_html
    assert (tmp_path / "papers" / bibkey / "reading_result.html").exists()

    _run("read", "--root", str(tmp_path), bibkey, "--parse-only")
    _write_reading_bundle(tmp_path, bibkey)

    _run("read", "--root", str(tmp_path), bibkey, "--rebuild-note")

    paper_html = (tmp_path / "papers" / bibkey / "reading_result.html").read_text(encoding="utf-8")
    assert "A compact fixture paper for exercising traceable paper-reading artifacts." in paper_html


def test_auto_html_can_be_disabled_with_environment(tmp_path):
    _run("init", "--root", str(tmp_path), "--title", "Auto HTML", "--direction", "test-time guidance")
    env = {**dict(os.environ), "PAPER_ENGINE_AUTO_HTML": "0"}

    _run("collect", "--root", str(tmp_path), "--fixture", str(fixture_path("search_results.json")), "--target-new", "5", env=env)

    candidates_html = (tmp_path / "html" / "candidates.html").read_text(encoding="utf-8")
    assert "A Paper" not in candidates_html
