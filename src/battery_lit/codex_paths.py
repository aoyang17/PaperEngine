from __future__ import annotations

import os
from pathlib import Path


def resolve_codex_bin(codex_bin: str | None = None) -> str:
    return str(codex_bin or os.environ.get("BATTERY_LIT_CODEX_BIN") or "codex")


def codex_env(project_bin: str | Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    path_parts: list[str] = []
    if project_bin:
        path_parts.append(str(Path(project_bin).expanduser().resolve()))
    for path in (
        Path.home() / ".local" / "bin",
        Path("/home/battery/.local/bin"),
        Path("/home/mdolabuser/.local/bin"),
        Path("/usr/local/bin"),
    ):
        text = str(path)
        if text not in path_parts:
            path_parts.append(text)
    for text in env.get("PATH", "").split(os.pathsep):
        if text and text not in path_parts:
            path_parts.append(text)
    env["PATH"] = os.pathsep.join(path_parts)
    return env
