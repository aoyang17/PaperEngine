from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunArtifacts:
    """Stable directory contract shared by local and external solvers."""

    root: Path

    @classmethod
    def create(cls, output_root: str | Path, case_id: str, run_id: str | None = None) -> "RunArtifacts":
        stamp = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        root = Path(output_root).expanduser().resolve() / case_id / stamp
        for child in ("raw", "figures", "logs", "model", "reports"):
            (root / child).mkdir(parents=True, exist_ok=True)
        return cls(root=root)

    def path(self, group: str, name: str) -> Path:
        if group not in {"raw", "figures", "logs", "model", "reports"}:
            raise ValueError(f"unknown artifact group: {group}")
        path = self.root / group / name
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, group: str, name: str, value: Any) -> Path:
        destination = self.path(group, name)
        destination.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return destination

    def write_sha256_manifest(self, destination: str | Path) -> Path:
        """Hash every file below the run root into a stable relative manifest."""
        output = Path(destination)
        output.parent.mkdir(parents=True, exist_ok=True)
        output_resolved = output.resolve()
        lines: list[str] = []
        for path in sorted(candidate for candidate in self.root.rglob("*") if candidate.is_file()):
            if path.resolve() == output_resolved:
                continue
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            lines.append(f"{digest.hexdigest()}  {path.relative_to(self.root).as_posix()}")
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return output
