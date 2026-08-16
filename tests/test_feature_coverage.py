from __future__ import annotations

from conftest import ROOT


def test_feature_coverage_doc_lists_required_categories():
    text = (ROOT / "docs" / "feature_coverage.md").read_text(encoding="utf-8")
    for category in [
        "init",
        "topic config",
        "search",
        "seed/resolve paper",
        "candidate queue",
        "preference feedback",
        "PDF download",
        "BibTeX",
        "paper-centric files",
        "parse/deep-read/note",
        "checks",
        "HTML view",
        "real probe",
    ]:
        assert category in text


def test_source_does_not_import_external_project_packages():
    source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "src" / "battery_lit").glob("*.py"))
    assert "battery_research_literature" not in source
    assert "/mnt/f/AI/skill" not in source
