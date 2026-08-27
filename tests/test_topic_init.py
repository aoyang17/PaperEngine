from __future__ import annotations

import subprocess

import yaml

from conftest import ROOT
from paper_engine.topic import init_topic, root_from_title
from paper_engine.util import slugify_path_component


def test_init_creates_file_only_topic_repo(tmp_path):
    result = init_topic(tmp_path, title="Agentic Discovery", direction="AI scientist systems", seed_papers=["A Seed Paper"])

    assert result["ok"] is True
    for name in ["README.md", "AGENTS.md", "topic.yml", "preferences.yml", "policy.yml", "candidates.jsonl", "library.bib"]:
        assert (tmp_path / name).exists()
    for name in ["papers", "reports", "html", "skills", "schemas"]:
        assert (tmp_path / name).is_dir()
    assert not (tmp_path / "state.sqlite").exists()
    assert (tmp_path / "skills" / "topic_init" / "SKILL.md").exists()
    assert (tmp_path / "skills" / "topic_enter" / "SKILL.md").exists()
    topic = yaml.safe_load((tmp_path / "topic.yml").read_text())
    assert topic["title"] == "Agentic Discovery"
    assert topic["direction"] == "AI scientist systems"
    assert topic["user_description_raw"] == "AI scientist systems"
    assert topic["seed_papers"] == ["A Seed Paper"]
    assert topic["refinement_questions_answered"] == []
    assert topic["search"]["seed_queries"] == []
    assert topic["search"]["exclude_terms"] == []


def test_init_is_idempotent_and_cli_builds_initial_html(tmp_path):
    cmd = [
        str(ROOT / "bin" / "paper_engine"),
        "init",
        "--root",
        str(tmp_path),
        "--title",
        "HTML Init",
        "--direction",
        "HTML topic initialization",
    ]
    first = subprocess.run(cmd, text=True, capture_output=True, check=True)
    second = subprocess.run(cmd, text=True, capture_output=True, check=True)

    assert '"ok": true' in first.stdout
    assert '"ok": true' in second.stdout
    assert (tmp_path / "html" / "dashboard.html").exists()
    assert "Never invent citations" in (tmp_path / "AGENTS.md").read_text()
    assert (tmp_path / "policy.yml").exists()


def test_title_slug_for_topic_folder_is_path_safe():
    assert slugify_path_component("AI Scientist: Self-Evolving Agents (2026)!") == "ai-scientist-self-evolving-agents-2026"
    assert slugify_path_component("  /Bad  Title\\Name: Test  ") == "bad-title-name-test"


def test_root_from_title_uses_slug_under_base_dir(tmp_path):
    root = root_from_title(tmp_path, "AI Scientist: Self-Evolving Agents")
    assert root == tmp_path / "ai-scientist-self-evolving-agents"


def test_cli_init_base_dir_derives_safe_root_from_title(tmp_path):
    cmd = [
        str(ROOT / "bin" / "paper_engine"),
        "init",
        "--base-dir",
        str(tmp_path),
        "--title",
        "AI Scientist: Self-Evolving Agents",
        "--direction",
        "AI scientist systems",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=True)
    root = tmp_path / "ai-scientist-self-evolving-agents"

    assert '"ok": true' in proc.stdout
    assert root.exists()
    assert (root / "topic.yml").exists()
    assert yaml.safe_load((root / "topic.yml").read_text())["title"] == "AI Scientist: Self-Evolving Agents"


def test_repository_root_wrapper_initializes_topic(tmp_path):
    cmd = [
        str(ROOT / "bin" / "paper_engine"),
        "init",
        "--base-dir",
        str(tmp_path),
        "--title",
        "Root Wrapper Topic",
        "--direction",
        "repository root wrapper initialization",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=True)
    root = tmp_path / "root-wrapper-topic"

    assert '"ok": true' in proc.stdout
    assert root.exists()
    assert yaml.safe_load((root / "topic.yml").read_text(encoding="utf-8"))["direction"] == "repository root wrapper initialization"


def test_init_help_carries_clean_room_rules():
    proc = subprocess.run(
        [str(ROOT / "bin" / "paper_engine"), "init", "--help"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "Do not inspect existing topic folders" in proc.stdout
    assert ".agents" in proc.stdout
    assert ".codex" in proc.stdout
    assert "ask the user; do not infer from filesystem" in proc.stdout


def test_cli_init_base_dir_does_not_use_sibling_topic_as_template(tmp_path):
    sibling = tmp_path / "old-topic"
    sibling.mkdir()
    (sibling / "AGENTS.md").write_text("COPY_ME_FROM_OLD_TOPIC", encoding="utf-8")
    (sibling / "topic.yml").write_text("title: Old Topic\n", encoding="utf-8")

    cmd = [
        str(ROOT / "bin" / "paper_engine"),
        "init",
        "--base-dir",
        str(tmp_path),
        "--title",
        "Fresh Clean Room Topic",
        "--direction",
        "new topic direction",
    ]
    subprocess.run(cmd, text=True, capture_output=True, check=True)
    root = tmp_path / "fresh-clean-room-topic"

    assert root.exists()
    assert "COPY_ME_FROM_OLD_TOPIC" not in (root / "AGENTS.md").read_text(encoding="utf-8")
    assert yaml.safe_load((root / "topic.yml").read_text(encoding="utf-8"))["title"] == "Fresh Clean Room Topic"


def test_cli_init_requires_title_and_direction(tmp_path):
    missing_direction = subprocess.run(
        [str(ROOT / "bin" / "paper_engine"), "init", "--root", str(tmp_path), "--title", "No Direction"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing_direction.returncode == 1
    assert "requires --direction" in missing_direction.stderr
    assert "ask the user; do not infer from filesystem" in missing_direction.stderr

    missing_title = subprocess.run(
        [str(ROOT / "bin" / "paper_engine"), "init", "--root", str(tmp_path), "--direction", "No title direction"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing_title.returncode == 1
    assert "requires --title" in missing_title.stderr
    assert "ask the user; do not infer from filesystem" in missing_title.stderr


def test_cli_init_rejects_non_empty_non_topic_root(tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    (target / "notes.txt").write_text("do not inspect me", encoding="utf-8")

    proc = subprocess.run(
        [
            str(ROOT / "bin" / "paper_engine"),
            "init",
            "--root",
            str(target),
            "--title",
            "Existing Target",
            "--direction",
            "existing target direction",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "target topic root already exists and is non-empty" in proc.stderr
    assert "do not infer from filesystem" in proc.stderr
    assert not (target / "topic.yml").exists()
