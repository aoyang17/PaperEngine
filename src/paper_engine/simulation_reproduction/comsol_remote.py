from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shlex
import uuid
from typing import Any


class ComsolRemoteError(RuntimeError):
    """Raised when the COMSOL gateway or remote scheduler contract fails."""


@dataclass(frozen=True)
class ComsolRemoteConfig:
    host: str
    port: int
    user: str
    instance_selection: str
    environment_script: str
    instance_id: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "ComsolRemoteConfig":
        source = Path(path).expanduser()
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ComsolRemoteError(f"invalid COMSOL remote config {source}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ComsolRemoteError("COMSOL remote config must be a JSON object")
        ssh = raw.get("ssh")
        remote = raw.get("remote")
        if not isinstance(ssh, dict) or not isinstance(remote, dict):
            raise ComsolRemoteError("config requires ssh and remote objects")
        values = {
            "host": str(ssh.get("host") or "").strip(),
            "port": int(ssh.get("port") or 22),
            "user": str(ssh.get("user") or "").strip(),
            "instance_selection": str(ssh.get("instance_selection") or "").strip(),
            "environment_script": str(remote.get("environment_script") or "").strip(),
            "instance_id": str(ssh.get("instance_id") or "").strip(),
        }
        missing = [name for name, value in values.items() if name != "instance_id" and not value]
        if missing:
            raise ComsolRemoteError(f"missing COMSOL remote config fields: {', '.join(missing)}")
        if not 1 <= values["port"] <= 65535:
            raise ComsolRemoteError("SSH port must be between 1 and 65535")
        return cls(**values)


@dataclass(frozen=True)
class RemoteResult:
    command: str
    returncode: int
    output: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.returncode == 0,
            "returncode": self.returncode,
            "output": self.output,
        }


class ComsolRemoteAgent:
    """Drive password-authenticated SSH gateways with an instance menu.

    Passwords are read only from an external mode-0600 file and are never
    included in configuration, commands, output, or repository artifacts.
    """

    def __init__(self, config: ComsolRemoteConfig, password_file: str | Path) -> None:
        self.config = config
        self.password_file = Path(password_file).expanduser()

    def run(self, command: str, *, timeout: int = 60) -> RemoteResult:
        pexpect = _load_pexpect()
        password = self._read_password()
        args = [
            "-tt",
            "-p",
            str(self.config.port),
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "PreferredAuthentications=password,keyboard-interactive",
            "-o",
            "PubkeyAuthentication=no",
            f"{self._login_user()}@{self.config.host}",
        ]
        child = pexpect.spawn("ssh", args, encoding="utf-8", timeout=timeout)
        chunks: list[str] = []
        try:
            matched = child.expect(
                [r"(?i)password[^:]*:", r"密码[^:：]*[:：]", pexpect.EOF, pexpect.TIMEOUT]
            )
            chunks.append(child.before or "")
            if matched >= 2:
                raise ComsolRemoteError("SSH password prompt was not reached")
            child.send(password + "\r")
            if not self.config.instance_id:
                selected = child.expect(
                    [r"认证成功[^\r\n]*实例", r"(?i)select[^\r\n]*instance", pexpect.EOF, pexpect.TIMEOUT]
                )
                chunks.append(child.before or "")
                if selected >= 2:
                    raise ComsolRemoteError("SSH gateway instance menu was not reached")
                child.send(self.config.instance_selection + "\r")
            entered = child.expect([r"(?m)[^\r\n]*[#$] ?$", pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
            chunks.append(child.before or "")
            if entered != 0:
                raise ComsolRemoteError("selected instance did not produce a remote shell")

            child.send("stty -echo\r")
            if child.expect([r"(?m)[^\r\n]*[#$] ?$", pexpect.EOF, pexpect.TIMEOUT]) != 0:
                raise ComsolRemoteError("could not disable remote command echo")
            marker = f"__PAPER_ENGINE_DONE_{uuid.uuid4().hex}__"
            wrapped = f"{command}; paper_engine_rc=$?; printf '\\n{marker}:%s\\n' \"$paper_engine_rc\""
            child.send(wrapped + "\r")
            finished = child.expect([rf"{re.escape(marker)}:(\d+)\r?\n", pexpect.EOF, pexpect.TIMEOUT], timeout=timeout)
            chunks.append(child.before or "")
            if finished != 0:
                raise ComsolRemoteError("remote command did not complete before disconnect/timeout")
            returncode = int(child.match.group(1))
            child.send("exit\r")
            return RemoteResult(command=command, returncode=returncode, output="".join(chunks).strip())
        finally:
            child.close(force=True)

    def probe(self) -> RemoteResult:
        environment = _remote_path(self.config.environment_script)
        command = (
            "set -u; export LD_LIBRARY_PATH=\"${LD_LIBRARY_PATH:-}\"; "
            f"source {environment}; "
            "printf 'login_user=%s\\n' \"$(id -un)\"; "
            "printf 'home=%s\\n' \"$HOME\"; "
            "printf 'comsol=%s\\n' \"$(command -v comsol)\"; "
            "printf 'sbatch=%s\\n' \"$(command -v sbatch)\"; "
            "sbatch --version | head -1"
        )
        return self.run(command)

    def submit(self, *, remote_workdir: str, script: str) -> RemoteResult:
        workdir = _remote_path(remote_workdir)
        script_name = _remote_path(script)
        environment = _remote_path(self.config.environment_script)
        command = (
            f"cd {workdir} && test -s {script_name} && "
            "export LD_LIBRARY_PATH=\"${LD_LIBRARY_PATH:-}\" && "
            f"source {environment} && "
            f"job_id=$(sbatch --parsable {script_name}) && "
            "printf 'job_id=%s\\n' \"$job_id\""
        )
        return self.run(command)

    def status(self, job_id: str) -> RemoteResult:
        if not re.fullmatch(r"[0-9]+(?:[_.][A-Za-z0-9]+)?", job_id):
            raise ComsolRemoteError("invalid Slurm job id")
        command = (
            f"squeue -j {shlex.quote(job_id)} -o '%.18i %.9P %.24j %.8T %.10M %.6D %R'; "
            f"sacct -j {shlex.quote(job_id)} --format=JobID,JobName%24,Partition,State,ExitCode,Elapsed -n -P"
        )
        return self.run(command)

    def verify(
        self,
        *,
        remote_workdir: str,
        job_id: str,
        stdout_pattern: str,
        stderr_pattern: str,
        artifact: str,
    ) -> RemoteResult:
        if not re.fullmatch(r"[0-9]+", job_id):
            raise ComsolRemoteError("invalid Slurm job id")
        workdir = _remote_path(remote_workdir)
        stdout = shlex.quote(stdout_pattern.replace("%j", job_id))
        stderr = shlex.quote(stderr_pattern.replace("%j", job_id))
        artifact_path = shlex.quote(artifact)
        command = (
            f"cd {workdir} && "
            f"job_state=$(sacct -j {job_id} --format=State,ExitCode -n -P | awk 'NF {{print; exit}}') && "
            "printf 'job_state=%s\\n' \"$job_state\" && test \"$job_state\" = 'COMPLETED|0:0' && "
            f"test -f {stdout} && test -f {stderr} && test -s {artifact_path} && "
            "batch_log=$(find . -maxdepth 1 -type f -name '*_comsol_batch.log' -size +0c -print -quit) && "
            "test -n \"$batch_log\" && "
            f"! grep -Eiq '(Error|Exception|FileNotFound|Cannot open display)' {stdout} {stderr} \"$batch_log\" && "
            f"stat -c 'artifact=%n size=%s modified=%y' {artifact_path}"
        )
        return self.run(command)

    def upload(self, *, local_path: str | Path, remote_path: str, timeout: int = 300) -> RemoteResult:
        source = Path(local_path).expanduser().resolve()
        if not source.exists():
            raise ComsolRemoteError(f"upload source does not exist: {source}")
        args = self._scp_base_args()
        if source.is_dir():
            args.append("-r")
        args.extend([str(source), f"{self.config.host}:{remote_path}"])
        return self._transfer(args, timeout=timeout)

    def download(self, *, remote_path: str, local_path: str | Path, timeout: int = 1800) -> RemoteResult:
        destination = Path(local_path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        args = self._scp_base_args()
        args.extend(["-r", f"{self.config.host}:{remote_path}", str(destination)])
        return self._transfer(args, timeout=timeout)

    def _scp_base_args(self) -> list[str]:
        return [
            "-P",
            str(self.config.port),
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            "PreferredAuthentications=password,keyboard-interactive",
            "-o",
            "PubkeyAuthentication=no",
            "-o",
            f"User={self._login_user()}",
        ]

    def _transfer(self, args: list[str], *, timeout: int) -> RemoteResult:
        pexpect = _load_pexpect()
        password = self._read_password()
        child = pexpect.spawn("scp", args, encoding="utf-8", timeout=timeout)
        chunks: list[str] = []
        try:
            matched = child.expect(
                [r"(?i)password[^:]*:", r"密码[^:：]*[:：]", pexpect.EOF, pexpect.TIMEOUT]
            )
            chunks.append(child.before or "")
            if matched >= 2:
                detail = _diagnostic(child.before or "")
                raise ComsolRemoteError(f"SCP password prompt was not reached: {detail}")
            child.send(password + "\r")
            if not self.config.instance_id:
                selected = child.expect(
                    [r"认证成功[^\r\n]*实例", r"(?i)select[^\r\n]*instance", pexpect.EOF, pexpect.TIMEOUT]
                )
                chunks.append(child.before or "")
                if selected >= 2:
                    raise ComsolRemoteError("SCP gateway instance menu was not reached")
                child.send(self.config.instance_selection + "\r")
            # The Yeesuan gateway can leave the instance session open after its
            # SCP backend has reported 100%.  Waiting only for EOF therefore
            # hangs despite a complete transfer.  Accept EOF normally; for this
            # gateway behavior, require at least one explicit 100% marker followed
            # by a quiet interval.  Callers still verify uploaded/downloaded
            # artifacts by size or SHA256 before using them.
            last_percent: int | None = None
            while True:
                quiet_timeout = min(timeout, 30) if last_percent is not None else timeout
                completed = child.expect(
                    [r"([0-9]{1,3})%", r"(?m)[^\r\n]*[#$] ?$", pexpect.EOF, pexpect.TIMEOUT],
                    timeout=quiet_timeout,
                )
                chunks.append(child.before or "")
                if completed == 0:
                    chunks.append(child.after or "")
                    last_percent = int(child.match.group(1))
                    if not 0 <= last_percent <= 100:
                        raise ComsolRemoteError(f"invalid SCP progress marker: {last_percent}%")
                    continue
                if completed == 1:
                    child.send("exit\r")
                    child.expect([pexpect.EOF, pexpect.TIMEOUT], timeout=10)
                    child.close()
                    return RemoteResult(command="scp", returncode=0, output="".join(chunks).strip())
                if completed == 2:
                    child.close()
                    returncode = child.exitstatus if child.exitstatus is not None else 1
                    return RemoteResult(command="scp", returncode=returncode, output="".join(chunks).strip())
                if last_percent == 100:
                    chunks.append("\ntransfer completed; gateway session stayed open after 100%")
                    child.close(force=True)
                    return RemoteResult(command="scp", returncode=0, output="".join(chunks).strip())
                if last_percent is None:
                    raise ComsolRemoteError("SCP transfer timed out before reporting progress")
                raise ComsolRemoteError(f"SCP transfer stalled at {last_percent}%")
        finally:
            child.close(force=True)

    def _login_user(self) -> str:
        if self.config.instance_id:
            return f"{self.config.user}::{self.config.instance_id}"
        return self.config.user

    def _read_password(self) -> str:
        try:
            mode = self.password_file.stat().st_mode & 0o777
            if mode & 0o077:
                raise ComsolRemoteError("password file must not be accessible by group or others")
            password = self.password_file.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as exc:
            raise ComsolRemoteError(f"cannot read password file: {exc}") from exc
        if not password:
            raise ComsolRemoteError("password file is empty")
        return password


def _load_pexpect():
    try:
        import pexpect
    except ImportError as exc:
        raise ComsolRemoteError("COMSOL remote agent requires pexpect>=4.8") from exc
    return pexpect


def _remote_path(value: str) -> str:
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise ComsolRemoteError("invalid remote path")
    if value.startswith("~/"):
        return '"$HOME"/' + shlex.quote(value[2:])
    return shlex.quote(value)


def _diagnostic(value: str) -> str:
    cleaned = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value).strip()
    return cleaned[-500:] if cleaned else "no remote diagnostic"
