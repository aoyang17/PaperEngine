from __future__ import annotations

import json
import subprocess

from conftest import ROOT, fixture_path


def _run(*args: str) -> dict:
    proc = subprocess.run([str(ROOT / "bin" / "paper_engine"), *args], text=True, capture_output=True, check=True)
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


def test_fixture_cli_workflow_reaches_html_knowledge_base(tmp_path):
    _run("init", "--root", str(tmp_path), "--title", "Agentic Discovery", "--direction", "AI scientist systems")
    policy = _run("policy", "check", "--root", str(tmp_path), "--json")
    collect = _run("collect", "--root", str(tmp_path), "--fixture", str(fixture_path("search_results.json")), "--target-new", "5")
    _run("candidates", "mark", "--root", str(tmp_path), "CAND-001", "relevant")
    _run("acquire", "--root", str(tmp_path), "CAND-001", "--manual-pdf", str(fixture_path("example.pdf")))
    promoted = _run("promote", "--root", str(tmp_path), "CAND-001")

    bibkey = promoted["bibkey"]
    _run("read", "--root", str(tmp_path), bibkey, "--parse-only")
    _write_reading_bundle(tmp_path, bibkey)

    validation = _run("read", "--root", str(tmp_path), bibkey, "--validate-report")
    quality = _run("read", "--root", str(tmp_path), bibkey, "--quality-audit")
    reading_audit = _run("tool", "audit-readings", "--root", str(tmp_path), "--json")
    note = _run("read", "--root", str(tmp_path), bibkey, "--rebuild-note")
    html = _run("html", "build", "--root", str(tmp_path))
    library = _run("library", "list", "--root", str(tmp_path), "--json")
    status = _run("status", "--root", str(tmp_path), "--json")

    assert policy["ok"] is True
    assert collect["added"] == 1
    assert validation["ok"] is True
    assert quality["ok"] is True
    assert reading_audit["ok"] is True
    assert reading_audit["total_papers"] == 1
    assert "quality_score" in quality
    assert note["ok"] is True
    assert html["ok"] is True
    assert status["ok"] is True
    assert library[0]["bibkey"] == bibkey
    assert (tmp_path / "papers" / bibkey / "paper.pdf").exists()
    assert (tmp_path / "papers" / bibkey / "parsed.md").exists()
    assert (tmp_path / "papers" / bibkey / "source_map.json").exists()
    assert (tmp_path / "papers" / bibkey / "note.md").exists()
    assert (tmp_path / "papers" / bibkey / "reading_result.html").exists()
    assert (tmp_path / "html" / "dashboard.html").exists()
    assert (tmp_path / "html" / "library.html").exists()
