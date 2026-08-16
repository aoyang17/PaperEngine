from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

from .codex_paths import codex_env, resolve_codex_bin


@dataclass(frozen=True)
class CodexEvent:
    kind: str
    payload: dict[str, object]

    def to_json(self) -> str:
        return json.dumps({"kind": self.kind, "payload": self.payload}, ensure_ascii=False)


class CodexRunnerError(RuntimeError):
    pass


class CodexRunner(Protocol):
    def run(self, prompt: str, cwd: Path, job_dir: Path) -> Iterator[CodexEvent]:
        ...


class FakeCodexRunner:
    def __init__(self, events: list[CodexEvent], fail: Exception | None = None) -> None:
        self.events = events
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def run(self, prompt: str, cwd: Path, job_dir: Path) -> Iterator[CodexEvent]:
        self.calls.append({"prompt": prompt, "cwd": cwd, "job_dir": job_dir})
        for event in self.events:
            yield event
        if self.fail:
            raise self.fail


class SubprocessCodexRunner:
    def __init__(
        self,
        codex_bin: str | None = None,
        model: str | None = None,
        effort: str | None = None,
        project_bin: str | Path | None = None,
        bypass_sandbox: bool | None = None,
    ) -> None:
        self.codex_bin = resolve_codex_bin(codex_bin)
        self.model = model or os.environ.get("BATTERY_LIT_CODEX_MODEL")
        self.effort = effort or os.environ.get("BATTERY_LIT_CODEX_EFFORT")
        self.project_bin = Path(project_bin).expanduser().resolve() if project_bin else None
        self.bypass_sandbox = (
            os.environ.get("BATTERY_LIT_CODEX_BYPASS_SANDBOX") == "1"
            if bypass_sandbox is None
            else bool(bypass_sandbox)
        )

    def command(self, cwd: Path) -> list[str]:
        command = [
            self.codex_bin,
            "exec",
            "--json",
        ]
        if self.bypass_sandbox:
            command.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            command.extend(["--sandbox", "workspace-write"])
        command.extend(["--skip-git-repo-check", "-C", str(cwd)])
        if self.model:
            command.extend(["--model", self.model])
        if self.effort:
            command.extend(["-c", f'model_reasoning_effort="{self.effort}"'])
        command.append("-")
        return command

    def env(self) -> dict[str, str]:
        return codex_env(self.project_bin)

    def run(self, prompt: str, cwd: Path, job_dir: Path) -> Iterator[CodexEvent]:
        proc = subprocess.Popen(
            self.command(cwd),
            cwd=str(cwd),
            env=self.env(),
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert proc.stdin is not None
        proc.stdin.write(prompt)
        proc.stdin.close()
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                yield CodexEvent(kind="stdout", payload={"text": line})
                continue
            kind = str(payload.get("type") or payload.get("event") or payload.get("kind") or "event")
            yield CodexEvent(kind=kind, payload=payload)

        return_code = proc.wait()
        if return_code != 0:
            raise CodexRunnerError(f"codex exec failed with exit code {return_code}")

    def run_until_outputs(
        self,
        prompt: str,
        cwd: Path,
        job_dir: Path,
        required_outputs: list[Path],
        *,
        stable_seconds: float = 5.0,
        timeout_seconds: float | None = None,
        require_output_updates: bool = False,
    ) -> Iterator[CodexEvent]:
        initial_signatures = {path: self._file_signature(path) for path in required_outputs}
        proc = subprocess.Popen(
            self.command(cwd),
            cwd=str(cwd),
            env=self.env(),
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert proc.stdin is not None
        proc.stdin.write(prompt)
        proc.stdin.close()
        events: queue.Queue[CodexEvent | None] = queue.Queue()

        def read_stdout() -> None:
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                event = self._event_from_line(raw_line)
                if event:
                    events.put(event)
            events.put(None)

        threading.Thread(target=read_stdout, daemon=True).start()
        start = time.monotonic()
        complete_since: float | None = None
        stdout_done = False
        while True:
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    break
                if event is None:
                    stdout_done = True
                else:
                    yield event

            now = time.monotonic()
            outputs_ready = all(path.exists() and path.stat().st_size > 0 for path in required_outputs)
            if outputs_ready and require_output_updates:
                outputs_ready = any(self._file_signature(path) != initial_signatures.get(path) for path in required_outputs)
            if outputs_ready:
                complete_since = complete_since or now
                if now - complete_since >= stable_seconds and proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=10)
                    while True:
                        try:
                            event = events.get_nowait()
                        except queue.Empty:
                            break
                        if event is not None:
                            yield event
                    return
            else:
                complete_since = None

            return_code = proc.poll()
            if return_code is not None:
                while not stdout_done:
                    try:
                        event = events.get(timeout=0.2)
                    except queue.Empty:
                        break
                    if event is None:
                        stdout_done = True
                    else:
                        yield event
                if return_code != 0 and not outputs_ready:
                    raise CodexRunnerError(f"codex exec failed with exit code {return_code}")
                return

            if timeout_seconds is not None and now - start > timeout_seconds:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)
                raise CodexRunnerError(f"codex exec timed out after {timeout_seconds:.0f} seconds")

            time.sleep(0.5)

    @staticmethod
    def _file_signature(path: Path) -> tuple[int, int] | None:
        if not path.exists():
            return None
        stat = path.stat()
        return (stat.st_size, stat.st_mtime_ns)

    @staticmethod
    def _event_from_line(raw_line: str) -> CodexEvent | None:
        line = raw_line.strip()
        if not line:
            return None
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return CodexEvent(kind="stdout", payload={"text": line})
        kind = str(payload.get("type") or payload.get("event") or payload.get("kind") or "event")
        return CodexEvent(kind=kind, payload=payload)
