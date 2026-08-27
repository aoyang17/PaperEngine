from __future__ import annotations

import json
import subprocess

import yaml

from conftest import ROOT
from paper_engine.policy import check_policy
from paper_engine.topic import init_topic


def test_init_policy_contains_safety_contract(tmp_path):
    init_topic(tmp_path, title="Safe Topic")
    policy = yaml.safe_load((tmp_path / "policy.yml").read_text(encoding="utf-8"))

    assert policy["schema_version"] == "v1"
    assert "papers/<bibkey>/source_map.json" in policy["allowed_direct_writes"]
    assert "papers/<bibkey>/note_plan.json" in policy["allowed_direct_writes"]
    assert "papers/<bibkey>/deep_read.json" in policy["allowed_direct_writes"]
    assert "library.bib" in policy["cli_only_writes"]
    assert "delete topic root" in policy["forbidden_without_explicit_confirmation"]
    assert policy["destructive_policy"]["requires_dry_run"] is True
    assert policy["destructive_policy"]["requires_explicit_user_confirmation"] is True
    assert "policy.yml" in policy["context_policy"]["read_first"]


def test_policy_check_cli_passes_for_new_topic(tmp_path):
    init_topic(tmp_path)
    proc = subprocess.run(
        [str(ROOT / "bin" / "paper_engine"), "policy", "check", "--root", str(tmp_path), "--json"],
        text=True,
        capture_output=True,
        check=True,
    )
    result = json.loads(proc.stdout)

    assert result["ok"] is True
    assert result["errors"] == []
    assert result["policy"].endswith("policy.yml")


def test_policy_check_reports_missing_policy(tmp_path):
    result = check_policy(tmp_path)

    assert result["ok"] is False
    assert result["errors"] == ["missing policy.yml"]


def test_policy_check_rejects_weak_destructive_policy(tmp_path):
    init_topic(tmp_path)
    policy = yaml.safe_load((tmp_path / "policy.yml").read_text(encoding="utf-8"))
    policy["destructive_policy"]["requires_dry_run"] = False
    (tmp_path / "policy.yml").write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")

    result = check_policy(tmp_path)

    assert result["ok"] is False
    assert "destructive_policy.requires_dry_run must be true" in result["errors"]


def test_cli_does_not_expose_uncontrolled_destructive_subcommands():
    text = (ROOT / "src" / "paper_engine" / "cli.py").read_text(encoding="utf-8")

    forbidden_snippets = [
        'sub.add_parser("delete"',
        'sub.add_parser("clear"',
        'sub.add_parser("remove"',
        'sub.add_parser("destroy"',
        'sub.add_parser("reset"',
    ]
    for snippet in forbidden_snippets:
        assert snippet not in text
