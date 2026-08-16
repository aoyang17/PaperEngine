#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from battery_lit.bib import list_library  # noqa: E402
from battery_lit.candidates import load_candidates  # noqa: E402
from battery_lit.topic import root_from_title  # noqa: E402


DEFAULT_CHROMIUM = Path("/home/battery/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome")
DEFAULT_BASE_PARENT = Path("/paper_hub/_battery_e2e")


class LiveE2E:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_dir = Path(args.run_dir or DEFAULT_BASE_PARENT / stamp).expanduser().resolve()
        self.topic_root = root_from_title(self.run_dir, args.title)
        self.screenshots = self.run_dir / "screenshots"
        self.report_path = self.run_dir / "e2e_report.json"
        self.report: dict[str, Any] = {
            "ok": False,
            "started_at": stamp,
            "run_dir": str(self.run_dir),
            "topic_root": str(self.topic_root),
            "stages": [],
            "warnings": [],
            "blockers": [],
            "artifacts": {"screenshots": str(self.screenshots)},
        }
        self.server: subprocess.Popen[str] | None = None
        self.base_url = ""

    def run(self) -> int:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots.mkdir(parents=True, exist_ok=True)
        try:
            self.stage("preflight", self.preflight)
            self.stage("create_topic_from_ui", self.create_topic_from_ui)
            self.stage("search_candidates", self.search_candidates)
            self.stage("preference_actions", self.preference_actions)
            self.stage("download_pdf_and_promote", self.download_pdf_and_promote)
            self.stage("read_paper", self.read_paper)
            self.stage("visual_checks", self.visual_checks)
            self.report["ok"] = True
            return 0
        except Exception as exc:
            self.report["ok"] = False
            self.report["blockers"].append({"stage": self.report.get("current_stage"), "error": str(exc)})
            return 1
        finally:
            self.report["ended_at"] = datetime.now(timezone.utc).isoformat()
            self.write_report()
            self.stop_server()

    def stage(self, name: str, fn) -> None:
        self.report["current_stage"] = name
        start = time.time()
        entry: dict[str, Any] = {"name": name, "ok": False, "started_at": datetime.now(timezone.utc).isoformat()}
        self.report["stages"].append(entry)
        self.write_report()
        try:
            result = fn()
            entry["ok"] = True
            if result is not None:
                entry["result"] = result
        except Exception as exc:
            entry["ok"] = False
            entry["error"] = str(exc)
            self.write_report()
            raise
        finally:
            entry["elapsed_sec"] = round(time.time() - start, 2)
            entry["ended_at"] = datetime.now(timezone.utc).isoformat()
            self.write_report()

    def preflight(self) -> dict[str, Any]:
        self.run_cmd([str(ROOT / "bin" / "battery_lit"), "--help"], cwd=ROOT, timeout=20)
        self.run_cmd([str(ROOT / "bin" / "paper-search"), "--help"], cwd=ROOT, timeout=20)
        self.run_cmd(["codex", "--help"], cwd=ROOT, timeout=20)
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(f"playwright is not importable in this Python environment: {exc}") from exc
        chromium = Path(self.args.chromium or DEFAULT_CHROMIUM)
        if not chromium.exists():
            raise RuntimeError(f"chromium executable not found: {chromium}")
        port = self.args.port or self.free_port()
        self.args.port = port
        return {"port": port, "chromium": str(chromium)}

    def create_topic_from_ui(self) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        self.start_server(["--base-dir", str(self.run_dir)])
        chromium = Path(self.args.chromium or DEFAULT_CHROMIUM)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(chromium), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.set_default_timeout(10000)
            try:
                page.goto(f"{self.base_url}/dashboard.html")
                page.wait_for_load_state("networkidle")
                self.wait_for_app_ready(page)
                self.screenshot(page, "01_bootstrap_before.png")
                page.select_option("[data-codex-model]", self.args.model)
                page.select_option("[data-codex-effort]", self.args.effort)
                page.fill('input[name="title"]', self.args.title)
                page.fill('textarea[name="direction"]', self.args.direction)
                if self.args.seed_paper:
                    page.fill('input[name="seed_paper"]', self.args.seed_paper)
                page.click('button[type="submit"]')
                self.screenshot(page, "02_bootstrap_after_submit.png")
                self.wait_for(lambda: (self.topic_root / "topic.yml").exists(), self.args.init_timeout, "topic.yml was not created")
                self.wait_for(
                    lambda: all((self.topic_root / name).exists() for name in ["topic.yml", "policy.yml", "preferences.yml", "README.md", "AGENTS.md"]),
                    30,
                    "required topic files were not created",
                )
                page.wait_for_timeout(3500)
                page.goto(f"{self.base_url}/dashboard.html")
                page.wait_for_load_state("networkidle")
                self.wait_for_app_ready(page)
                body = page.locator("body").inner_text()
                if "Create Topic" in body:
                    raise RuntimeError("browser did not bind to the created topic after init")
                self.screenshot(page, "03_dashboard_after_init.png")
            finally:
                browser.close()
        return {"topic_root": str(self.topic_root)}

    def search_candidates(self) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        self.restart_server_for_topic()
        chromium = Path(self.args.chromium or DEFAULT_CHROMIUM)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(chromium), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.set_default_timeout(10000)
            try:
                page.goto(f"{self.base_url}/dashboard.html")
                page.wait_for_load_state("networkidle")
                self.wait_for_app_ready(page)
                page.select_option("[data-codex-model]", self.args.model)
                page.select_option("[data-codex-effort]", self.args.effort)
                search_result = page.evaluate(
                    """async () => {
                      const response = await fetch("/api/session/action", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          action: "search_30",
                          payload: { target_new: 3 },
                        }),
                      });
                      const data = await response.json();
                      return { ok: response.ok && data.ok !== false, status: response.status, data };
                    }"""
                )
                if not search_result.get("ok"):
                    raise RuntimeError(f"failed to start candidate search: {search_result}")
                self.wait_for_candidates(self.args.min_candidates, self.args.search_timeout)
                self.wait_for_session_idle(self.args.search_timeout)
                page.goto(f"{self.base_url}/candidates.html")
                page.wait_for_load_state("networkidle")
                self.wait_for_app_ready(page)
                self.screenshot(page, "04_candidates_after_search.png")
            finally:
                browser.close()
        candidates = load_candidates(self.topic_root)
        missing_venues = [item.get("candidate_id") for item in candidates if str(item.get("venue") or "").lower() in {"", "unknown"}]
        if missing_venues:
            self.report["warnings"].append({"stage": "search_candidates", "quality_warning": "missing venue", "candidate_ids": missing_venues[:10]})
        return {"candidate_count": len(candidates)}

    def preference_actions(self) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        candidates = load_candidates(self.topic_root)
        if len(candidates) < 3:
            raise RuntimeError(f"need at least 3 candidates for preference actions, found {len(candidates)}")
        selected = [str(item["candidate_id"]) for item in candidates[:3]]
        actions = [
            ("candidate_mark_relevant", "relevant", selected[0], "05_after_relevant.png"),
            ("candidate_mark_irrelevant", "irrelevant", selected[1], "06_after_irrelevant.png"),
            ("candidate_dismissed", "dismissed", selected[2], "07_after_dismissed.png"),
        ]
        chromium = Path(self.args.chromium or DEFAULT_CHROMIUM)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(chromium), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.set_default_timeout(10000)
            try:
                page.goto(f"{self.base_url}/candidates.html")
                page.wait_for_load_state("networkidle")
                self.wait_for_app_ready(page)
                for action, status, candidate_id, shot in actions:
                    self.progress(action=action, candidate_id=candidate_id, expected_status=status)
                    clicked = page.evaluate(
                        """({ candidateId, action }) => {
                          const selector = `tr[data-id="${candidateId}"] [data-session-action="${action}"]`;
                          const node = document.querySelector(selector);
                          if (!node) return { ok: false, reason: "missing" };
                          const rect = node.getBoundingClientRect();
                          const visible = rect.width > 0 && rect.height > 0;
                          if (!visible) return { ok: false, reason: "hidden", rect };
                          node.click();
                          return { ok: true, rect };
                        }""",
                        {"candidateId": candidate_id, "action": action},
                    )
                    if not clicked.get("ok"):
                        raise RuntimeError(f"{action} button for {candidate_id} is not visible")
                    self.progress(action=action, candidate_id=candidate_id, expected_status=status, clicked=True)
                    self.wait_for_candidate_status(candidate_id, status, self.args.action_timeout)
                    page.goto(f"{self.base_url}/candidates.html")
                    page.wait_for_load_state("networkidle")
                    self.wait_for_app_ready(page)
                    row = page.locator(f'tr[data-id="{candidate_id}"]')
                    if status != row.get_attribute("data-status"):
                        raise RuntimeError(f"candidate {candidate_id} UI status did not update to {status}")
                    self.screenshot(page, shot)
            finally:
                browser.close()
        return {"selected": selected}

    def download_pdf_and_promote(self) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        candidates = load_candidates(self.topic_root)
        candidates_to_try = [
            str(item["candidate_id"])
            for item in candidates
            if item.get("status") in {"relevant", "new", "downloaded", "manual_pdf_needed"}
        ][: self.args.pdf_attempts]
        if not candidates_to_try:
            raise RuntimeError("no candidates available for PDF download")
        before = {paper["bibkey"] for paper in list_library(self.topic_root)}
        chromium = Path(self.args.chromium or DEFAULT_CHROMIUM)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(chromium), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.set_default_timeout(10000)
            try:
                page.goto(f"{self.base_url}/candidates.html")
                page.wait_for_load_state("networkidle")
                self.wait_for_app_ready(page)
                clicked = page.evaluate(
                    """async (candidateIds) => {
                      const response = await fetch("/api/session/action", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          action: "candidate_download_selected",
                          payload: { candidate_ids: candidateIds },
                        }),
                      });
                      const data = await response.json();
                      return { ok: response.ok && data.ok !== false, status: response.status, data };
                    }""",
                    candidates_to_try,
                )
                if not clicked.get("ok"):
                    raise RuntimeError(f"failed to select candidates for PDF download: {clicked}")
                self.progress(stage_detail="download_pdf_action", candidate_ids=candidates_to_try)
                self.wait_for(lambda: self.downloaded_bibkeys(before), self.args.pdf_timeout, "no real PDF was downloaded and promoted")
                self.wait_for_session_idle(self.args.pdf_timeout)
                page.goto(f"{self.base_url}/library.html")
                page.wait_for_load_state("networkidle")
                self.wait_for_app_ready(page)
                if not page.locator(".paper-title-icons a[aria-label='PDF']").count():
                    raise RuntimeError("Library UI does not show a PDF icon after promotion")
                self.screenshot(page, "08_library_after_pdf.png")
            finally:
                browser.close()
        self.run_cmd([str(ROOT / "bin" / "battery_lit"), "bib", "check", "--root", str(self.topic_root)], cwd=ROOT, timeout=60)
        self.run_cmd([str(ROOT / "bin" / "battery_lit"), "pdf", "check", "--root", str(self.topic_root)], cwd=ROOT, timeout=60)
        return {"downloaded_bibkeys": self.downloaded_bibkeys(before)}

    def read_paper(self) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        papers = [paper for paper in list_library(self.topic_root) if (self.topic_root / "papers" / paper["bibkey"] / "paper.pdf").exists()]
        if not papers:
            raise RuntimeError("no downloaded paper is available for reading")
        bibkey = str(papers[0]["bibkey"])
        chromium = Path(self.args.chromium or DEFAULT_CHROMIUM)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(chromium), args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.set_default_timeout(10000)
            try:
                page.goto(f"{self.base_url}/library.html")
                page.wait_for_load_state("networkidle")
                self.wait_for_app_ready(page)
                clicked = page.evaluate(
                    """async (bibkey) => {
                      const response = await fetch("/api/session/action", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          action: "library_read_selected",
                          payload: { bibkeys: [bibkey] },
                        }),
                      });
                      const data = await response.json();
                      return { ok: response.ok && data.ok !== false, status: response.status, data };
                    }""",
                    bibkey,
                )
                if not clicked.get("ok"):
                    raise RuntimeError(f"failed to start paper reading from Library UI: {clicked}")
                self.progress(stage_detail="library_read_action", bibkey=bibkey)
                self.wait_for(lambda: self.paper_read_artifacts_exist(bibkey), self.args.read_timeout, f"paper reading artifacts were not completed for {bibkey}")
                page.goto(f"{self.base_url}/library.html")
                page.wait_for_load_state("networkidle")
                self.wait_for_app_ready(page)
                if not page.locator(".paper-title-icons a[aria-label='Knowledge']").count():
                    raise RuntimeError("Library UI does not show a Knowledge/Note icon after reading")
                self.screenshot(page, "09_library_after_read.png")
                page.goto(f"{self.base_url}/papers/{bibkey}.html")
                page.wait_for_load_state("networkidle")
                self.wait_for_app_ready(page)
                self.screenshot(page, "10_paper_detail_after_read.png")
            finally:
                browser.close()
        return {"bibkey": bibkey}

    def visual_checks(self) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        chromium = Path(self.args.chromium or DEFAULT_CHROMIUM)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=str(chromium), args=["--no-sandbox"])
            try:
                for route, name in [
                    ("/dashboard.html", "11_dashboard_desktop_final.png"),
                    ("/candidates.html", "12_candidates_desktop_final.png"),
                    ("/library.html", "13_library_desktop_final.png"),
                ]:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.set_default_timeout(10000)
                    page.goto(self.base_url + route)
                    page.wait_for_load_state("networkidle")
                    self.wait_for_app_ready(page)
                    self.assert_no_horizontal_overflow(page, route)
                    self.screenshot(page, name)
                    page.close()
                for route, name in [
                    ("/dashboard.html", "14_dashboard_mobile_final.png"),
                    ("/candidates.html", "15_candidates_mobile_final.png"),
                ]:
                    page = browser.new_page(viewport={"width": 390, "height": 844})
                    page.set_default_timeout(10000)
                    page.goto(self.base_url + route)
                    page.wait_for_load_state("networkidle")
                    self.wait_for_app_ready(page)
                    self.assert_no_horizontal_overflow(page, route)
                    self.screenshot(page, name)
                    page.close()
            finally:
                browser.close()
        return {"screenshots": str(self.screenshots)}

    def start_server(self, args: list[str]) -> None:
        self.stop_server()
        port = int(self.args.port)
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{self.args.pythonpath}:{ROOT / 'src'}" if self.args.pythonpath else f"{ROOT / 'src'}"
        self.server = subprocess.Popen(
            [str(ROOT / "bin" / "battery_lit"), "start", *args, "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(ROOT),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.base_url = f"http://127.0.0.1:{port}"
        self.wait_for_server(port, self.args.server_timeout)

    def restart_server_for_topic(self) -> None:
        self.start_server(["--root", str(self.topic_root)])

    def stop_server(self) -> None:
        if self.server and self.server.poll() is None:
            self.server.terminate()
            try:
                self.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server.kill()
        self.server = None

    def wait_for_server(self, port: int, timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.server and self.server.poll() is not None:
                output = self.server.stdout.read() if self.server.stdout else ""
                raise RuntimeError(f"server exited early: {output}")
            try:
                with urlopen(f"http://127.0.0.1:{port}/dashboard.html", timeout=1) as response:
                    if response.status == 200:
                        return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError(f"server did not start on port {port}")

    def wait_for_candidates(self, minimum: int, timeout: float) -> None:
        self.wait_for(lambda: len(load_candidates(self.topic_root)) >= minimum, timeout, f"fewer than {minimum} candidates were collected")

    def wait_for_candidate_status(self, candidate_id: str, status: str, timeout: float) -> None:
        def check() -> bool:
            for item in load_candidates(self.topic_root):
                if item.get("candidate_id") == candidate_id:
                    return item.get("status") == status
            return False

        self.wait_for(check, timeout, f"candidate {candidate_id} did not reach status {status}")

    def downloaded_bibkeys(self, before: set[str]) -> list[str]:
        result = []
        for paper in list_library(self.topic_root):
            bibkey = str(paper["bibkey"])
            if bibkey in before:
                continue
            if (self.topic_root / "papers" / bibkey / "paper.pdf").exists():
                result.append(bibkey)
        return result

    def paper_read_artifacts_exist(self, bibkey: str) -> bool:
        paper_dir = self.topic_root / "papers" / bibkey
        return all((paper_dir / name).exists() for name in ["parsed.md", "deep_read.json", "note.md"]) and (
            (self.topic_root / "html" / "papers" / f"{bibkey}.html").exists()
        )

    def wait_for_session_idle(self, timeout: float) -> None:
        def check() -> bool:
            try:
                with urlopen(f"{self.base_url}/api/session/state", timeout=2) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return data.get("status") != "running"
            except Exception:
                return False

        self.wait_for(check, timeout, "Codex session did not become idle")

    def wait_for(self, predicate, timeout: float, message: str) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(2)
        raise RuntimeError(message)

    def screenshot(self, page, name: str) -> None:
        page.screenshot(path=str(self.screenshots / name), full_page=True)

    def assert_no_horizontal_overflow(self, page, route: str) -> None:
        overflow = page.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
        if overflow:
            raise RuntimeError(f"horizontal overflow detected on {route}")

    def wait_for_app_ready(self, page) -> None:
        page.wait_for_function("() => document.documentElement.dataset.batteryAppReady === 'true'", timeout=10000)

    def run_cmd(self, cmd: list[str], cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(f"command failed: {' '.join(cmd)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
        return proc

    def write_report(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(json.dumps(self.report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    def progress(self, **fields: Any) -> None:
        self.report["progress"] = {
            "stage": self.report.get("current_stage"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **fields,
        }
        self.write_report()

    @staticmethod
    def free_port() -> int:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the canonical live browser user journey for battery_lit.")
    parser.add_argument("--run-dir", help="Run output directory. Defaults to /paper_hub/_battery_e2e/<timestamp>.")
    parser.add_argument("--title", default="Live Test-Time Guidance Probe")
    parser.add_argument(
        "--direction",
        default=(
            "Collect literature on test-time guidance for flow matching, score-based SDE models, diffusion models, "
            "and scientific or engineering applications without retraining."
        ),
    )
    parser.add_argument("--seed-paper", default="Classifier-Free Diffusion Guidance")
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--chromium", default=str(DEFAULT_CHROMIUM))
    parser.add_argument("--pythonpath", default="/home/battery/.local/lib/python3.10/site-packages")
    parser.add_argument("--min-candidates", type=int, default=3)
    parser.add_argument("--pdf-attempts", type=int, default=1)
    parser.add_argument("--server-timeout", type=float, default=30)
    parser.add_argument("--init-timeout", type=float, default=600)
    parser.add_argument("--search-timeout", type=float, default=900)
    parser.add_argument("--action-timeout", type=float, default=300)
    parser.add_argument("--pdf-timeout", type=float, default=900)
    parser.add_argument("--read-timeout", type=float, default=1200)
    args = parser.parse_args()
    runner = LiveE2E(args)
    code = runner.run()
    print(json.dumps({"ok": runner.report["ok"], "report": str(runner.report_path), "run_dir": str(runner.run_dir)}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
