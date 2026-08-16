#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from battery_lit.topic import root_from_title  # noqa: E402
from battery_lit.web_app import WebApp  # noqa: E402


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _serve(app: WebApp) -> tuple[ThreadingHTTPServer, str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self._send(app.handle(self.path))

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or "0")
            body = self.rfile.read(length).decode("utf-8") if length else ""
            self._send(app.handle(self.path, method="POST", body=body))

        def _send(self, response) -> None:
            body = response.body.encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def _wait_for(path: Path, timeout: float = 180.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if path.exists():
            return True
        time.sleep(1)
    return False


def _wait_for_successful_summary(base_dir: Path, timeout: float = 180.0) -> bool:
    jobs_dir = base_dir / ".battery_serverlet" / "jobs"
    start = time.time()
    while time.time() - start < timeout:
        for summary in jobs_dir.glob("*/summary.json"):
            try:
                data = json.loads(summary.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("ok") is True:
                return True
        time.sleep(1)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Opt-in live browser + Codex serverlet probe.")
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--keep", action="store_true", help="Keep the temporary topic directory")
    args = parser.parse_args()

    if os.environ.get("BATTERY_LIT_LIVE_CODEX") != "1":
        print(json.dumps({"ok": False, "skipped": True, "reason": "set BATTERY_LIT_LIVE_CODEX=1"}))
        return 0

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        print(json.dumps({"ok": False, "error": f"playwright is required: {exc}"}))
        return 1

    base_dir = Path(tempfile.mkdtemp(prefix="battery-live-web-"))
    title = "Live Web Flow Probe Topic"
    expected_root = root_from_title(base_dir, title)
    server, url = _serve(WebApp(base_dir=base_dir, project_root=ROOT))
    screenshot_dir = base_dir / "screenshots"
    screenshot_dir.mkdir()
    result: dict[str, object] = {"ok": False, "base_dir": str(base_dir), "expected_root": str(expected_root)}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 850})
            page.goto(url + "/dashboard.html")
            page.wait_for_load_state("networkidle")
            page.select_option("[data-codex-model]", args.model)
            page.select_option("[data-codex-effort]", args.effort)
            page.fill('input[name="title"]', title)
            page.fill('textarea[name="direction"]', "A safe live probe for test-time guidance literature workflow initialization.")
            page.fill('input[name="seed_paper"]', "Flow Matching for Generative Modeling")
            page.click('button[type="submit"]')
            page.screenshot(path=str(screenshot_dir / "after-create-click.png"), full_page=True)
            if not _wait_for(expected_root / "topic.yml"):
                page.screenshot(path=str(screenshot_dir / "topic-init-timeout.png"), full_page=True)
                result["error"] = "topic.yml was not created before timeout"
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 1
            if not _wait_for_successful_summary(base_dir):
                page.screenshot(path=str(screenshot_dir / "summary-timeout.png"), full_page=True)
                result["error"] = "topic-init summary did not report ok before timeout"
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 1
            page.goto(url + "/api/jobs")
            page.wait_for_timeout(500)
            page.goto(url + "/dashboard.html")
            page.wait_for_load_state("networkidle")
            dashboard_text = page.locator("body").inner_text()
            page.goto(url + "/candidates.html")
            page.wait_for_load_state("networkidle")
            candidates_text = page.locator("body").inner_text()
            page.goto(url + "/library.html")
            page.wait_for_load_state("networkidle")
            library_text = page.locator("body").inner_text()
            page.select_option("[data-language-select]", "zh")
            page.wait_for_timeout(300)
            zh_text = page.locator("body").inner_text()
            page.screenshot(path=str(screenshot_dir / "library-zh.png"), full_page=True)
            browser.close()
        required = ["topic.yml", "policy.yml", "preferences.yml"]
        missing = [name for name in required if not (expected_root / name).exists()]
        result.update(
            {
                "ok": not missing and "Create Topic" not in dashboard_text and "Candidate Queue" in candidates_text and "Library" in library_text and "文献库" in zh_text,
                "missing": missing,
                "screenshots": str(screenshot_dir),
            }
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1
    finally:
        server.shutdown()
        if args.keep:
            print(json.dumps({"kept": str(base_dir)}, ensure_ascii=False))
        else:
            shutil.rmtree(base_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
