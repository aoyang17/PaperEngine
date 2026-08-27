#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from paper_engine.codex_worker import CodexEvent, FakeCodexRunner
from paper_engine.jobs import JobAlreadyActive, JobManager
from paper_engine.sidecars import SidecarTempWorkspace, merge_score_shards, split_shards
from paper_engine.topic import init_topic


class BlockingRunner:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def run(self, prompt: str, cwd: Path, job_dir: Path):
        self.calls += 1
        self.started.set()
        self.release.wait(timeout=5)
        yield CodexEvent(kind="result", payload={"ok": True, "summary": "released"})


def _check(name: str, ok: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "ok": ok, "details": details or {}}


def check_topic_job_lock(work_dir: Path) -> dict[str, Any]:
    topic = work_dir / "source_topic"
    init_topic(topic, "Sidecar Probe", "adversarial sidecar scheduling probe")
    runner = BlockingRunner()
    first = JobManager(topic, runner=runner, project_root=ROOT)
    second = JobManager(topic, runner=FakeCodexRunner([]), project_root=ROOT)

    queued = first.start_job("long task", action="probe")
    blocked = False
    try:
        if not runner.started.wait(timeout=2):
            return _check("topic_job_lock", False, {"reason": "first job did not start", "queued": queued})
        try:
            second.run_job("parallel write attempt", action="probe")
        except JobAlreadyActive:
            blocked = True
    finally:
        runner.release.set()
        for _ in range(100):
            if not (topic / ".paper_engine" / "active_job.json").exists():
                break
            time.sleep(0.02)

    return _check(
        "topic_job_lock",
        blocked and runner.calls == 1 and not (topic / ".paper_engine" / "active_job.json").exists(),
        {"parallel_write_blocked": blocked, "runner_calls": runner.calls},
    )


def check_score_shard_merge(work_dir: Path) -> dict[str, Any]:
    candidates = [
        {"record_id": "r1", "candidate_id": "CAND-001", "score": 0.72, "content": 0.65, "preference": 0.05, "credibility": 0.02, "score_confidence": "high", "reasons": ["direct match"]},
        {"record_id": "r2", "candidate_id": "CAND-002", "score": -0.55, "content": -0.5, "preference": -0.05, "credibility": 0.0, "score_confidence": "medium", "reasons": ["off topic"]},
        {"record_id": "r3", "candidate_id": "CAND-003", "score": 0.05, "content": 0.05, "preference": 0.0, "credibility": 0.0, "score_confidence": "low", "reasons": ["weak signal"]},
        {"record_id": "r4", "candidate_id": "CAND-003", "score": 0.34, "content": 0.32, "preference": 0.0, "credibility": 0.02, "score_confidence": "medium", "reasons": ["same candidate id but stable record id"]},
    ]
    shards_dir = work_dir / "scratch" / "score_shards"
    shards_dir.mkdir(parents=True)
    shard_paths: list[Path] = []
    for index, shard in enumerate(split_shards(candidates, 2), start=1):
        path = shards_dir / f"score_shard_{index}.jsonl"
        path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in shard) + "\n", encoding="utf-8")
        shard_paths.append(path)

    output = work_dir / "reports" / "candidate_scores_merged.jsonl"
    result = merge_score_shards(shard_paths, output)
    merged = output.read_text(encoding="utf-8").splitlines() if output.exists() else []
    return _check(
        "score_shard_merge",
        result["ok"] and result["records"] == len(candidates) and len(merged) == len(candidates),
        {"result": result, "merged_lines": len(merged)},
    )


def check_malformed_shard_block(work_dir: Path) -> dict[str, Any]:
    shards_dir = work_dir / "scratch" / "bad_shards"
    shards_dir.mkdir(parents=True)
    good = shards_dir / "good.jsonl"
    bad = shards_dir / "bad.jsonl"
    good.write_text(json.dumps({"candidate_id": "CAND-010", "score": 0.2}) + "\n", encoding="utf-8")
    bad.write_text('{"candidate_id": "CAND-011", "score": 1.5}\nnot-json\n', encoding="utf-8")
    output = work_dir / "reports" / "bad_merge.jsonl"
    result = merge_score_shards([good, bad], output)
    return _check(
        "malformed_shard_block",
        (not result["ok"]) and (not output.exists()) and len(result["errors"]) >= 2,
        {"result": result},
    )


def check_readonly_findings_isolation(work_dir: Path) -> dict[str, Any]:
    topic = work_dir / "read_topic"
    init_topic(topic, "Read Isolation", "read-only sidecar findings isolation")
    sidecar_dir = work_dir / "scratch" / "read_findings" / "Bonalli2017Solving"
    sidecar_dir.mkdir(parents=True)
    finding = {
        "bibkey": "Bonalli2017Solving",
        "role": "method_math",
        "allowed_output": "findings_only",
        "writes_final_artifacts": False,
        "source_scope": ["papers/Bonalli2017Solving/metadata.yml", "papers/Bonalli2017Solving/parsed.md"],
    }
    (sidecar_dir / "method_math_findings.json").write_text(json.dumps(finding, indent=2), encoding="utf-8")
    final_artifacts = [
        topic / "papers" / "Bonalli2017Solving" / "source_map.json",
        topic / "papers" / "Bonalli2017Solving" / "note_plan.json",
        topic / "papers" / "Bonalli2017Solving" / "deep_read.json",
    ]
    return _check(
        "readonly_findings_isolation",
        all(not path.exists() for path in final_artifacts) and (sidecar_dir / "method_math_findings.json").exists(),
        {"findings": str(sidecar_dir / "method_math_findings.json")},
    )


def run_probe(*, keep_work_dir: bool = False) -> dict[str, Any]:
    workspace = SidecarTempWorkspace.create(prefix="paper-engine-subagent-adversarial-", keep=keep_work_dir)
    result: dict[str, Any] = {
        "ok": False,
        "work_dir": str(workspace.root),
        "checks": [],
        "cleanup": None,
    }
    try:
        (workspace.root / "reports").mkdir(parents=True, exist_ok=True)
        checks = [
            check_topic_job_lock(workspace.root),
            check_score_shard_merge(workspace.root),
            check_malformed_shard_block(workspace.root),
            check_readonly_findings_isolation(workspace.root),
        ]
        result["checks"] = checks
        result["ok"] = all(check["ok"] for check in checks)
        report = workspace.root / "reports" / "acceptance.json"
        report.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["report"] = str(report)
    finally:
        cleanup = workspace.cleanup()
        result["cleanup"] = {
            "path": cleanup.path,
            "removed": cleanup.removed,
            "kept": cleanup.kept,
            "errors": list(cleanup.errors),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run adversarial sidecar safety probe.")
    parser.add_argument("--keep-work-dir", action="store_true", help="Keep /tmp probe directory for debugging.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    args = parser.parse_args()

    result = run_probe(keep_work_dir=args.keep_work_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"ok={result['ok']} work_dir={result['work_dir']} cleanup={result['cleanup']}")
        for check in result["checks"]:
            print(f"- {check['name']}: {'PASS' if check['ok'] else 'FAIL'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
