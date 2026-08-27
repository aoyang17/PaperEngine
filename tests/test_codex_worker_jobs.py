from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

from paper_engine.codex_worker import CodexEvent, FakeCodexRunner, SubprocessCodexRunner
from paper_engine.jobs import JobAlreadyActive, JobManager
from paper_engine.prompt_contracts import build_worker_prompt
from paper_engine.topic import init_topic


class BlockingRunner:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def run(self, prompt: str, cwd: Path, job_dir: Path):
        self.calls += 1
        self.started.set()
        self.release.wait(timeout=5)
        yield CodexEvent(kind="result", payload={"ok": True, "summary": "released"})


def test_worker_prompt_contains_required_context_and_boundaries(tmp_path):
    init_topic(tmp_path, "Prompt Topic", "bounded literature workflow")

    prompt = build_worker_prompt(
        project_root=Path("/project/paper-engine"),
        topic_root=tmp_path,
        task="Collect 10 more candidates.",
    )

    assert "/project/paper-engine/README.md" in prompt
    assert "/project/paper-engine/AGENTS.md" in prompt
    assert str(tmp_path / "AGENTS.md") in prompt
    assert str(tmp_path / "policy.yml") in prompt
    assert str(tmp_path / "topic.yml") in prompt
    assert str(tmp_path / "preferences.yml") in prompt
    assert "Do not inspect sibling topic folders" in prompt
    assert "Use paper_engine CLI commands for state changes" in prompt
    assert "run `/project/paper-engine/bin/paper_engine`" in prompt
    assert "Collect 10 more candidates." in prompt


def test_fake_runner_emits_scripted_events(tmp_path):
    runner = FakeCodexRunner(
        [
            CodexEvent(kind="message", payload={"text": "started"}),
            CodexEvent(kind="result", payload={"ok": True}),
        ]
    )

    events = list(runner.run("do work", tmp_path, tmp_path / "job"))

    assert [event.kind for event in events] == ["message", "result"]
    assert runner.calls[0]["prompt"] == "do work"
    assert runner.calls[0]["cwd"] == tmp_path


def test_job_manager_persists_successful_job(tmp_path):
    init_topic(tmp_path, "Job Topic", "job persistence")
    runner = FakeCodexRunner(
        [
            CodexEvent(kind="message", payload={"text": "working"}),
            CodexEvent(kind="result", payload={"ok": True, "summary": "done"}),
        ]
    )
    manager = JobManager(tmp_path, runner=runner, project_root=Path("/project/paper-engine"))

    result = manager.run_job("Collect papers", action="collect")

    job_dir = tmp_path / ".paper_engine" / "jobs" / result["job_id"]
    assert result["ok"] is True
    assert result["action"] == "collect"
    assert result["summary"] == "done"
    assert (job_dir / "prompt.txt").exists()
    assert (job_dir / "events.jsonl").exists()
    assert (job_dir / "summary.json").exists()
    assert not (tmp_path / ".paper_engine" / "active_job.json").exists()

    events = [json.loads(line) for line in (job_dir / "events.jsonl").read_text().splitlines()]
    assert events[0]["kind"] == "message"
    assert json.loads((job_dir / "summary.json").read_text())["ok"] is True
    assert json.loads((tmp_path / ".paper_engine" / "jobs.jsonl").read_text().splitlines()[0])["job_id"] == result["job_id"]


def test_job_manager_clears_active_job_after_runner_failure(tmp_path):
    init_topic(tmp_path, "Fail Topic", "job failures")
    runner = FakeCodexRunner([CodexEvent(kind="message", payload={"text": "before error"})], fail=RuntimeError("boom"))
    manager = JobManager(tmp_path, runner=runner, project_root=Path("/project/paper-engine"))

    result = manager.run_job("Fail now", action="collect")

    job_dir = tmp_path / ".paper_engine" / "jobs" / result["job_id"]
    assert result["ok"] is False
    assert "boom" in result["error"]
    assert not (tmp_path / ".paper_engine" / "active_job.json").exists()
    assert "boom" in (job_dir / "stderr.log").read_text()


def test_job_manager_rejects_when_active_job_exists(tmp_path):
    init_topic(tmp_path, "Lock Topic", "job locks")
    active = tmp_path / ".paper_engine" / "active_job.json"
    active.parent.mkdir()
    active.write_text(json.dumps({"job_id": "existing"}), encoding="utf-8")

    manager = JobManager(tmp_path, runner=FakeCodexRunner([]), project_root=Path("/project/paper-engine"))

    with pytest.raises(JobAlreadyActive):
        manager.run_job("Collect papers", action="collect")


def test_job_manager_atomic_lock_allows_only_one_concurrent_job(tmp_path):
    init_topic(tmp_path, "Concurrent Topic", "job locks")
    runner = BlockingRunner()
    first = JobManager(tmp_path, runner=runner, project_root=Path("/project/paper-engine"))
    second = JobManager(tmp_path, runner=FakeCodexRunner([]), project_root=Path("/project/paper-engine"))

    queued = first.start_job("Long task", action="collect")
    assert queued["ok"] is True
    assert runner.started.wait(timeout=2)

    with pytest.raises(JobAlreadyActive):
        second.run_job("Other task", action="collect")

    runner.release.set()
    for _ in range(100):
        if not (tmp_path / ".paper_engine" / "active_job.json").exists():
            break
        time.sleep(0.02)
    assert not (tmp_path / ".paper_engine" / "active_job.json").exists()
    assert runner.calls == 1


def test_job_manager_reports_invalid_active_lock_as_busy(tmp_path):
    init_topic(tmp_path, "Bad Lock Topic", "job locks")
    active = tmp_path / ".paper_engine" / "active_job.json"
    active.parent.mkdir()
    active.write_text("{not-json", encoding="utf-8")

    manager = JobManager(tmp_path, runner=FakeCodexRunner([]), project_root=Path("/project/paper-engine"))

    with pytest.raises(JobAlreadyActive) as exc:
        manager.run_job("Collect papers", action="collect")
    assert "unknown" in str(exc.value)


def test_subprocess_runner_uses_account_default_and_env_model(monkeypatch):
    monkeypatch.delenv("PAPER_ENGINE_CODEX_MODEL", raising=False)
    monkeypatch.delenv("PAPER_ENGINE_CODEX_EFFORT", raising=False)
    assert SubprocessCodexRunner().model is None
    assert SubprocessCodexRunner().effort is None

    monkeypatch.setenv("PAPER_ENGINE_CODEX_MODEL", "gpt-5.6-sol")
    monkeypatch.setenv("PAPER_ENGINE_CODEX_EFFORT", "xhigh")
    assert SubprocessCodexRunner().model == "gpt-5.6-sol"
    assert SubprocessCodexRunner().effort == "xhigh"


def test_subprocess_runner_command_matches_current_codex_cli(monkeypatch, tmp_path):
    monkeypatch.delenv("PAPER_ENGINE_CODEX_MODEL", raising=False)
    monkeypatch.delenv("PAPER_ENGINE_CODEX_BIN", raising=False)

    command = SubprocessCodexRunner().command(tmp_path)

    assert command[:3] == ["codex", "exec", "--json"]
    assert "--sandbox" in command
    assert "--skip-git-repo-check" in command
    assert "-C" in command
    assert str(tmp_path) in command
    assert command[-1] == "-"
    assert "probe" not in command
    assert "--model" not in command
    assert "--ask-for-approval" not in command

    monkeypatch.setenv("PAPER_ENGINE_CODEX_MODEL", "gpt-5.6-sol")
    command = SubprocessCodexRunner().command(tmp_path)
    assert "--model" in command
    assert "gpt-5.6-sol" in command

    command = SubprocessCodexRunner(model="gpt-5.6-terra", effort="high").command(tmp_path)
    assert "--model" in command
    assert "gpt-5.6-terra" in command
    assert "-c" in command
    assert 'model_reasoning_effort="high"' in command


def test_subprocess_runner_uses_explicit_codex_bin_env(monkeypatch, tmp_path):
    monkeypatch.setenv("PAPER_ENGINE_CODEX_BIN", "/opt/codex/bin/codex")

    command = SubprocessCodexRunner().command(tmp_path)

    assert command[0] == "/opt/codex/bin/codex"


def test_subprocess_runner_prepends_project_bin_and_local_bins_to_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    project_bin = tmp_path / "project" / "bin"
    runner = SubprocessCodexRunner(project_bin=project_bin)

    path = runner.env()["PATH"].split(":")
    assert path[0] == str(project_bin.resolve())
    assert str(Path.home() / ".local" / "bin") in path
    assert "/home/battery/.local/bin" in path
    assert "/home/mdolabuser/.local/bin" in path
    assert "/usr/bin" in path


def test_subprocess_runner_merges_stderr_to_stdout(monkeypatch, tmp_path):
    popen_args = {}

    class FakeStdout:
        def __iter__(self):
            return iter([])

    class FakeStdin:
        def __init__(self):
            self.written = ""
            self.closed = False

        def write(self, text):
            self.written += text

        def close(self):
            self.closed = True

    class FakeProc:
        stdout = FakeStdout()
        stdin = FakeStdin()

        def wait(self):
            return 0

    def fake_popen(command, **kwargs):
        popen_args.update(kwargs)
        return FakeProc()

    monkeypatch.setattr("paper_engine.codex_worker.subprocess.Popen", fake_popen)

    list(SubprocessCodexRunner().run("probe", tmp_path, tmp_path))

    assert popen_args["stderr"] is subprocess.STDOUT
    assert popen_args["stdin"] is subprocess.PIPE
    assert "env" in popen_args
