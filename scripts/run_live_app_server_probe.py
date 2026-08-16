from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from battery_lit.codex_session import AppServerCodexSessionManager  # noqa: E402
from battery_lit.topic import init_topic  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an opt-in live Codex app-server probe.")
    parser.add_argument("--root", default=".tmp/live-app-server-probe-topic")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    if os.environ.get("BATTERY_LIT_LIVE_CODEX") != "1":
        print(json.dumps({"ok": True, "skipped": True, "reason": "set BATTERY_LIT_LIVE_CODEX=1 to run live Codex probe"}))
        return 0

    topic_root = Path(args.root).expanduser().resolve()
    if topic_root.exists() and any(topic_root.iterdir()):
        print(json.dumps({"ok": False, "error": f"probe root is not empty: {topic_root}"}))
        return 2
    init_topic(topic_root, "Live App Server Probe", "verify persistent Codex session transport")

    manager = AppServerCodexSessionManager(request_timeout=min(args.timeout, 30.0))
    try:
        state = manager.ensure_session(topic_root, model=os.environ.get("BATTERY_LIT_CODEX_MODEL"), effort=os.environ.get("BATTERY_LIT_CODEX_EFFORT"))
        if not state.get("ok"):
            print(json.dumps({"ok": False, "stage": "ensure_session", "state": state}, ensure_ascii=False))
            return 2
        turn = manager.send_message("Do not run shell commands. Reply with one short sentence confirming this topic session is active.")
        if not turn.get("ok"):
            print(json.dumps({"ok": False, "stage": "send_message", "turn": turn, "state": manager.state()}, ensure_ascii=False))
            return 2
        deadline = time.time() + args.timeout
        while time.time() < deadline:
            current = manager.state()
            if current.get("status") in {"idle", "failed", "blocked"}:
                break
            time.sleep(0.5)
        events = manager.events_since(0, limit=50)
        current = manager.state()
        ok = current.get("status") == "idle" and not current.get("blocker")
        print(json.dumps({"ok": ok, "state": current, "events": events.get("events", [])[-10:]}, ensure_ascii=False))
        return 0 if ok else 2
    finally:
        manager.close()


if __name__ == "__main__":
    raise SystemExit(main())
