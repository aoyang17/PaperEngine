from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from conftest import ROOT
from scripts.run_subagent_adversarial_probe import run_probe


def test_subagent_adversarial_probe_cleans_work_dir_by_default():
    result = run_probe(keep_work_dir=False)

    assert result["ok"] is True
    assert result["cleanup"]["removed"] is True
    assert not Path(result["work_dir"]).exists()
    assert {check["name"] for check in result["checks"]} == {
        "topic_job_lock",
        "score_shard_merge",
        "malformed_shard_block",
        "readonly_findings_isolation",
    }


def test_subagent_adversarial_probe_cli_json():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_subagent_adversarial_probe.py"), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert '"ok": true' in result.stdout
    assert '"removed": true' in result.stdout
