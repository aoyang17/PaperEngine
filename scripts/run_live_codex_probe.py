#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from battery_lit.codex_worker import SubprocessCodexRunner  # noqa: E402
from battery_lit.jobs import JobManager  # noqa: E402
from battery_lit.topic import init_topic  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Opt-in live Codex worker probe.")
    parser.add_argument("--root", help="Existing or new fixture topic root")
    parser.add_argument("--mutating", action="store_true", help="Run a safe fixture mutation probe")
    args = parser.parse_args()

    if os.environ.get("BATTERY_LIT_LIVE_CODEX") != "1":
        print(json.dumps({"ok": False, "skipped": True, "reason": "set BATTERY_LIT_LIVE_CODEX=1"}))
        return 0

    with tempfile.TemporaryDirectory(prefix="battery-live-codex-") as tmp:
        topic_root = Path(args.root).expanduser().resolve() if args.root else Path(tmp) / "topic"
        init_topic(topic_root, "Live Codex Probe", "safe status probe")
        manager = JobManager(topic_root, runner=SubprocessCodexRunner(), project_root=ROOT)
        if args.mutating:
            task = "Run `battery_lit status --json`, then run `battery_lit html build`. Do not inspect sibling topics."
            action = "live-mutating-probe"
        else:
            task = "Run `battery_lit status --json` and `battery_lit policy check --json`. Do not modify files. Return a short summary."
            action = "live-readonly-probe"
        result = manager.run_job(task, action=action)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
