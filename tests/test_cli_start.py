from __future__ import annotations

import os
import subprocess

from conftest import ROOT
from battery_lit import cli
from battery_lit.codex_worker import SubprocessCodexRunner
from battery_lit.topic import init_topic


def test_start_command_calls_serve_web_and_disables_codex_sandbox_by_default(tmp_path, monkeypatch, capsys):
    init_topic(tmp_path, "Start Topic", "browser-first workflow")
    called = {}
    monkeypatch.setenv("BATTERY_LIT_CODEX_BYPASS_SANDBOX", "0")

    def fake_serve_web(root, host, port, base_dir=None):
        called["root"] = root
        called["base_dir"] = base_dir
        called["host"] = host
        called["port"] = port

    monkeypatch.setattr("battery_lit.web_app.serve_web", fake_serve_web)

    result = cli.main(["start", "--root", str(tmp_path), "--host", "0.0.0.0", "--port", "10005"])

    captured = capsys.readouterr()
    assert result == 0
    assert called == {"root": str(tmp_path), "base_dir": None, "host": "0.0.0.0", "port": 10005}
    assert os.environ["BATTERY_LIT_CODEX_BYPASS_SANDBOX"] == "1"
    assert "Codex sandbox disabled" in captured.err


def test_start_base_dir_calls_bootstrap_serve_web_and_disables_codex_sandbox_by_default(tmp_path, monkeypatch):
    called = {}
    monkeypatch.setenv("BATTERY_LIT_CODEX_BYPASS_SANDBOX", "0")

    def fake_serve_web(root, host, port, base_dir=None):
        called["root"] = root
        called["base_dir"] = base_dir
        called["host"] = host
        called["port"] = port

    monkeypatch.setattr("battery_lit.web_app.serve_web", fake_serve_web)

    result = cli.main(["start", "--base-dir", str(tmp_path), "--host", "0.0.0.0", "--port", "10005"])

    assert result == 0
    assert called == {"root": None, "base_dir": str(tmp_path), "host": "0.0.0.0", "port": 10005}
    assert os.environ["BATTERY_LIT_CODEX_BYPASS_SANDBOX"] == "1"


def test_start_can_opt_back_into_codex_workspace_sandbox(tmp_path, monkeypatch, capsys):
    init_topic(tmp_path, "Sandbox Topic", "debug sandbox")
    called = {}
    monkeypatch.setenv("BATTERY_LIT_CODEX_BYPASS_SANDBOX", "1")

    def fake_serve_web(root, host, port, base_dir=None):
        called["root"] = root
        called["base_dir"] = base_dir
        called["host"] = host
        called["port"] = port

    monkeypatch.setattr("battery_lit.web_app.serve_web", fake_serve_web)

    result = cli.main(["start", "--root", str(tmp_path), "--codex-sandbox"])

    captured = capsys.readouterr()
    assert result == 0
    assert called["root"] == str(tmp_path)
    assert "BATTERY_LIT_CODEX_BYPASS_SANDBOX" not in os.environ
    assert "workspace sandbox enabled" in captured.err


def test_start_default_bypass_configures_subprocess_codex_runner(tmp_path, monkeypatch):
    init_topic(tmp_path, "Runner Topic", "runner sandbox")
    monkeypatch.setenv("BATTERY_LIT_CODEX_BYPASS_SANDBOX", "0")

    cli._configure_start_codex_sandbox(use_codex_sandbox=False)

    command = SubprocessCodexRunner(codex_bin="/usr/bin/codex").command(tmp_path)

    assert "--dangerously-bypass-approvals-and-sandbox" in command


def test_start_rejects_explicit_root_and_base_dir(tmp_path, capsys):
    init_topic(tmp_path / "topic", "Start Topic", "browser-first workflow")

    result = cli.main(["start", "--root", str(tmp_path / "topic"), "--base-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert result == 1
    assert "mutually exclusive" in captured.err


def test_start_rejects_explicit_current_root_and_base_dir(tmp_path, capsys):
    result = cli.main(["start", "--root", ".", "--base-dir", str(tmp_path)])

    captured = capsys.readouterr()
    assert result == 1
    assert "mutually exclusive" in captured.err


def test_start_rejects_missing_topic_files(tmp_path, capsys):
    result = cli.main(["start", "--root", str(tmp_path), "--host", "127.0.0.1", "--port", "10005"])

    captured = capsys.readouterr()
    assert result == 1
    assert "battery_lit init" in captured.err
    assert "topic.yml" in captured.err


def test_web_serve_remains_supported():
    proc = subprocess.run(
        [str(ROOT / "bin" / "battery_lit"), "web", "serve", "--help"],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "--host" in proc.stdout
    assert "--port" in proc.stdout


def test_read_batch_draft_workers_can_prepare_and_run_in_one_cli_call(tmp_path, monkeypatch, capsys):
    init_topic(tmp_path, "Batch CLI Topic", "batch reread cli")
    called = {}

    def fake_run(
        root,
        run_id,
        max_parallel=None,
        model=None,
        effort=None,
        repair_bibkeys=None,
        repair_errors=None,
        progress=None,
    ):
        called["root"] = root
        called["run_id"] = run_id
        called["max_parallel"] = max_parallel
        called["repair_bibkeys"] = repair_bibkeys
        called["repair_errors"] = repair_errors
        if progress:
            progress("read-batch draft-workers: test heartbeat")
        return {"ok": True, "run_id": run_id, "targets": ["Alpha2024A", "Beta2024B"]}

    monkeypatch.setattr("battery_lit.read_batch.run_read_batch_draft_workers", fake_run)

    result = cli.main(
        [
            "read-batch",
            "--root",
            str(tmp_path),
            "--bibkey",
            "Alpha2024A",
            "--bibkey",
            "Beta2024B",
            "--force-reread",
            "--run-id",
            "combo",
            "--draft-workers",
            "--max-parallel",
            "2",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert called == {
        "root": str(tmp_path),
        "run_id": "combo",
        "max_parallel": 2,
        "repair_bibkeys": [],
        "repair_errors": [],
    }
    assert "read-batch draft-workers: test heartbeat" in captured.err
    assert (tmp_path / ".tmp" / "read_batch" / "combo" / "manifest.json").exists()
