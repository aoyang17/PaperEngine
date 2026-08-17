from __future__ import annotations

import os
from pathlib import Path
import subprocess

from conftest import ROOT


def test_battery_lit_prefers_system_python310_over_path_python(tmp_path: Path):
    marker = tmp_path / "path-python-used"
    fake_python = tmp_path / "python3"
    fake_python.write_text(f"#!/bin/sh\ntouch {marker}\nexit 97\n", encoding="utf-8")
    fake_python.chmod(0o755)

    result = subprocess.run(
        [str(ROOT / "bin" / "battery_lit"), "--help"],
        text=True,
        capture_output=True,
        env={**os.environ, "PATH": f"{tmp_path}:/usr/local/bin:/usr/bin:/bin"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage: battery_lit" in result.stdout
    assert not marker.exists()


def test_paper_search_uses_configured_battery_lit_python(tmp_path: Path):
    marker = tmp_path / "configured-python-args"
    fake_python = tmp_path / "configured-python"
    fake_python.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > "{marker}"\n', encoding="utf-8")
    fake_python.chmod(0o755)

    result = subprocess.run(
        [str(ROOT / "bin" / "paper-search"), "search", "silicon"],
        text=True,
        capture_output=True,
        env={**os.environ, "BATTERY_LIT_PYTHON": str(fake_python)},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8").splitlines() == ["-m", "paper_search_mcp.cli", "search", "silicon"]
