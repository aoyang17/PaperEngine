from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from paper_engine import cli


def _install_import_module(monkeypatch, result):
    calls = []
    module = types.ModuleType("paper_engine.topic_import")

    def import_paper_from_topic(target_root, source_root, source_bibkey):
        calls.append((target_root, source_root, source_bibkey))
        return result

    module.import_paper_from_topic = import_paper_from_topic
    monkeypatch.setitem(sys.modules, "paper_engine.topic_import", module)
    return calls


def test_import_from_topic_parser_requires_explicit_source_arguments():
    parser = cli.build_parser()

    args = parser.parse_args(
        [
            "library",
            "import-from-topic",
            "--root",
            "/target",
            "--source-root",
            "/source",
            "--source-bibkey",
            "Source2026Paper",
            "--json",
        ]
    )

    assert args.library_command == "import-from-topic"
    assert args.root == "/target"
    assert args.source_root == "/source"
    assert args.source_bibkey == "Source2026Paper"
    assert args.json is True


def test_import_from_topic_calls_core_once_emits_json_and_refreshes_only_when_imported(monkeypatch, capsys):
    calls = _install_import_module(monkeypatch, {"ok": True, "status": "imported", "bibkey": "Target2026Paper"})
    refreshes = []
    monkeypatch.setattr(cli, "_auto_build_html", lambda root: refreshes.append(root))
    args = cli.build_parser().parse_args(
        [
            "library",
            "import-from-topic",
            "--root",
            "/target",
            "--source-root",
            "/source",
            "--source-bibkey",
            "Source2026Paper",
            "--json",
        ]
    )

    assert cli.run(args) == 0
    assert calls == [("/target", "/source", "Source2026Paper")]
    assert refreshes == ["/target"]
    assert json.loads(capsys.readouterr().out) == {"ok": True, "status": "imported", "bibkey": "Target2026Paper"}


def test_import_from_topic_already_exists_is_success_without_html_refresh(monkeypatch, capsys):
    calls = _install_import_module(monkeypatch, {"ok": True, "status": "already_exists", "bibkey": "Target2026Paper"})
    refreshes = []
    monkeypatch.setattr(cli, "_auto_build_html", lambda root: refreshes.append(root))
    args = cli.build_parser().parse_args(
        [
            "library",
            "import-from-topic",
            "--root",
            "/target",
            "--source-root",
            "/source",
            "--source-bibkey",
            "Source2026Paper",
            "--json",
        ]
    )

    assert cli.run(args) == 0
    assert calls == [("/target", "/source", "Source2026Paper")]
    assert refreshes == []
    assert json.loads(capsys.readouterr().out)["status"] == "already_exists"


def test_import_from_topic_failure_is_nonzero_without_html_refresh(monkeypatch, capsys):
    calls = _install_import_module(monkeypatch, {"ok": False, "status": "skipped", "error": "source paper has no PDF"})
    refreshes = []
    monkeypatch.setattr(cli, "_auto_build_html", lambda root: refreshes.append(root))
    args = cli.build_parser().parse_args(
        [
            "library",
            "import-from-topic",
            "--root",
            "/target",
            "--source-root",
            "/source",
            "--source-bibkey",
            "Source2026Paper",
            "--json",
        ]
    )

    assert cli.run(args) == 1
    assert calls == [("/target", "/source", "Source2026Paper")]
    assert refreshes == []
    assert json.loads(capsys.readouterr().out)["status"] == "skipped"


def test_cross_topic_import_workflow_and_guides_keep_the_contract():
    root = Path(__file__).resolve().parents[1]
    skill = (root / "templates" / "skills" / "paper_acquire_bib" / "SKILL.md").read_text(encoding="utf-8")
    agents = (root / "templates" / "topic_repo" / "AGENTS.md").read_text(encoding="utf-8")
    english = (root / "docs" / "user_manual.md").read_text(encoding="utf-8")
    chinese = (root / "docs" / "user_manual_zh.md").read_text(encoding="utf-8")

    command = "paper_engine library import-from-topic --root <target-topic> --source-root <source-topic> --source-bibkey <bibkey> --json"
    for text in (skill, agents):
        assert command in text
        assert "explicitly names the source topic path" in text or "explicitly name the source topic path" in text
        assert "exactly one match" in text
        assert "never shell-copy" in text.lower()
        assert "preferences.yml" in text
    assert "There is no web button or batch interface" in skill
    assert "import-from-topic" in english
    assert "import-from-topic" in chinese
