#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SHORTCUT_TERMS = [
    "deterministic draft writer",
    "draft generator",
    "schema-valid drafts",
    "parsed/index-only",
    "staging helper",
    "bulk draft generator",
]


def _run_json(command: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    try:
        payload = json.loads(proc.stdout or proc.stderr or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "raw_stdout": proc.stdout, "raw_stderr": proc.stderr}
    payload["returncode"] = proc.returncode
    return payload


def _copy_probe_topic(topic_root: Path, bibkeys: list[str], work_dir: Path) -> Path:
    probe_root = work_dir / f"{topic_root.name}-reading-quality-probe"
    if probe_root.exists():
        shutil.rmtree(probe_root)
    probe_root.mkdir(parents=True)
    for name in ["topic.yml", "policy.yml", "preferences.yml", "library.bib", "AGENTS.md", "README.md"]:
        source = topic_root / name
        if source.exists():
            shutil.copy2(source, probe_root / name)
    papers_out = probe_root / "papers"
    papers_out.mkdir()
    for bibkey in bibkeys:
        source = topic_root / "papers" / bibkey
        if source.exists():
            shutil.copytree(source, papers_out / bibkey)
    return probe_root


def _artifact_hashes(paper_dir: Path) -> dict[str, str | None]:
    hashes: dict[str, str | None] = {}
    for name in ["source_map.json", "note_plan.json", "deep_read.json"]:
        path = paper_dir / name
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    return hashes


def _latest_read_pool_run(probe_root: Path) -> Path | None:
    pool_root = probe_root / ".tmp" / "read_pool"
    if not pool_root.exists():
        return None
    runs = [path for path in pool_root.iterdir() if path.is_dir() and (path / "manifest.json").exists()]
    if not runs:
        return None
    return max(runs, key=lambda path: path.stat().st_mtime)


def _audit_read_pool_run(probe_root: Path, bibkeys: list[str]) -> dict[str, Any]:
    run_dir = _latest_read_pool_run(probe_root)
    if run_dir is None:
        return {"ok": None, "skipped": True, "reason": "no read-many read-pool run found"}
    try:
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"cannot read read-pool manifest: {exc}"}
    results: list[dict[str, Any]] = []
    for bibkey in bibkeys:
        job_dir = run_dir / bibkey
        draft_dir = job_dir / "draft"
        missing = []
        for name in ["source_map.json", "note_plan.json", "deep_read.json"]:
            if not (draft_dir / name).exists():
                missing.append(str((draft_dir / name).relative_to(probe_root)))
        for name in ["reader.json", "review.json"]:
            if not (job_dir / name).exists():
                missing.append(str((job_dir / name).relative_to(probe_root)))
        results.append({"bibkey": bibkey, "ok": not missing, "missing": missing})
    return {
        "ok": all(item.get("ok") for item in results),
        "run_id": run_dir.name,
        "manifest": manifest,
        "results": results,
    }


def _paper_scale(probe_root: Path, bibkey: str) -> dict[str, Any]:
    paper_dir = probe_root / "papers" / bibkey
    pdf_path = paper_dir / "paper.pdf"
    parsed_path = paper_dir / "parsed.md"
    index_path = paper_dir / "paper_index.json"
    paragraphs = 0
    figures_tables = 0
    page_labels: set[int] = set()
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            index = {}
        for paragraph in index.get("paragraphs") or []:
            if not isinstance(paragraph, dict):
                continue
            paragraphs += 1
            try:
                page = int(paragraph.get("page") or 0)
            except (TypeError, ValueError):
                page = 0
            if page > 0:
                page_labels.add(page)
        figures_tables = len(index.get("figures_tables") or [])
    return {
        "pdf_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
        "parsed_bytes": parsed_path.stat().st_size if parsed_path.exists() else 0,
        "paper_index_paragraphs": paragraphs,
        "paper_index_figures_tables": figures_tables,
        "paper_index_page_label_count": len(page_labels),
        "paper_index_max_page_label": max(page_labels) if page_labels else 0,
        "rendered_pages": len(list((paper_dir / "page_images").glob("page-*.png"))),
        "math_pages": len(list((paper_dir / "math_pages").glob("page-*.png"))),
        "scale_basis": "rendered_pages plus paragraph/figure counts; paper_index page labels may collapse on parser defects",
    }


def _codex_reread(
    project_root: Path,
    probe_root: Path,
    bibkey: str,
    model: str,
    effort: str,
    timeout_s: int,
    bypass_sandbox: bool,
    worker_timeout_s: int | None = None,
) -> dict[str, Any]:
    prompt = (
        f"@{project_root / 'README.md'} Use battery_lit in topic root {probe_root}. "
        f"Re-read {bibkey} using the controlled read-many reader/reviewer workflow. "
        f"Hard time budget: finish this one paper within {timeout_s} seconds. "
        f"Run `battery_lit read-many --bibkey {bibkey} --force-reread --max-parallel 1 --json`. "
        "Do not cat or dump full parsed.md. Use metadata, paper_index section/paragraph IDs, math_index, visual_index, "
        "and targeted rg/python snippets to harvest only the evidence needed for this paper. "
        "The read-many controller owns the staged draft path, reviewer gate, final copy, validation, note rebuild, quality audit, and selected reduce audit. "
        "Do not create or run a helper.py, deterministic draft writer, draft generator, parsed/index-only schema filler, or generic bulk draft generator. "
        "Do not write final `papers/<bibkey>/source_map.json`, `papers/<bibkey>/note_plan.json`, or `papers/<bibkey>/deep_read.json` directly. "
        "If the paper cannot be completed within the budget, stop after writing no partial user-facing artifact and report the blocker."
    )
    command = _codex_command(
        project_root=project_root,
        probe_root=probe_root,
        model=model,
        effort=effort,
        bypass_sandbox=bypass_sandbox,
        prompt=prompt,
    )
    if isinstance(command, dict):
        return command
    return _run_codex_command(command, probe_root, timeout_s, bypass_sandbox=bypass_sandbox, worker_timeout_s=worker_timeout_s)


def _codex_bulk_reread(
    project_root: Path,
    probe_root: Path,
    bibkeys: list[str],
    model: str,
    effort: str,
    timeout_s: int,
    bypass_sandbox: bool,
    worker_timeout_s: int | None = None,
    bulk_max_parallel: int = 3,
) -> dict[str, Any]:
    joined = ", ".join(bibkeys)
    bulk_max_parallel = max(1, min(int(bulk_max_parallel), 5))
    key_args = " ".join(f"--bibkey {bibkey}" for bibkey in bibkeys)
    prompt = (
        f"@{project_root / 'README.md'} Use battery_lit in topic root {probe_root}. "
        f"Re-read these library papers as one bounded bulk user task: {joined}. "
        "Do not use existing reading artifacts as evidence. Use one command only for the reading work: "
        f"`battery_lit read-many {key_args} --force-reread --max-parallel {bulk_max_parallel} --json`. "
        "The command must run one independent paper job per bibkey, with a persistent reader session and an independent reviewer session for each paper. "
        "If it reports per-bibkey failures, report the failing bibkeys and concrete reader/reviewer/CLI gate errors. Do not process the papers sequentially in the main session. "
        "The main session must not write `.tmp/read_pool/<run_id>/<bibkey>/draft/{source_map.json,note_plan.json,deep_read.json}` for multi-paper jobs; only the read-many controller may manage those staged files and final copies. "
        "Do not create or run helper.py, deterministic draft writer, draft generator, parsed/index-only schema filler, or generic bulk draft generator. "
        "Return a concise summary with the run_id, changed bibkeys, validation, quality-audit, selected reduce-audit, skipped, and blockers. "
        "If this is an all-library task, run full-library `battery_lit tool audit-readings --json` after read-many completes."
    )
    command = _codex_command(
        project_root=project_root,
        probe_root=probe_root,
        model=model,
        effort=effort,
        bypass_sandbox=bypass_sandbox,
        prompt=prompt,
    )
    if isinstance(command, dict):
        return command
    return _run_codex_command(command, probe_root, timeout_s, bypass_sandbox=bypass_sandbox, worker_timeout_s=worker_timeout_s)


def _codex_command(
    *,
    project_root: Path,
    probe_root: Path,
    model: str,
    effort: str,
    bypass_sandbox: bool,
    prompt: str,
) -> list[str] | dict[str, Any]:
    command = [
        "codex",
        "exec",
        "--json",
    ]
    if bypass_sandbox:
        if os.environ.get("BATTERY_LIT_ALLOW_UNSANDBOXED_PROBE") != "1":
            return {
                "ok": False,
                "returncode": None,
                "error": "set BATTERY_LIT_ALLOW_UNSANDBOXED_PROBE=1 to allow --codex-bypass-sandbox",
            }
        command.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        command.extend(["--sandbox", "workspace-write"])
    command.extend(
        [
            "--skip-git-repo-check",
            "-C",
            str(probe_root),
            "--add-dir",
            str(project_root),
            "--model",
            model,
            "-c",
            f'model_reasoning_effort="{effort}"',
            prompt,
        ]
    )
    return command


def _run_codex_command(
    command: list[str],
    probe_root: Path,
    timeout_s: int,
    *,
    bypass_sandbox: bool = False,
    worker_timeout_s: int | None = None,
) -> dict[str, Any]:
    env = os.environ.copy()
    if bypass_sandbox:
        env["BATTERY_LIT_CODEX_BYPASS_SANDBOX"] = "1"
    if worker_timeout_s:
        env["BATTERY_LIT_READ_BATCH_WORKER_TIMEOUT"] = str(worker_timeout_s)
    proc = subprocess.Popen(
        command,
        cwd=probe_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        assistant_text = _assistant_text_from_codex_stdout(stdout)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "timeout_s": timeout_s,
            "stdout_tail": stdout[-4000:],
            "assistant_stdout_tail": assistant_text[-4000:],
            "stderr_tail": stderr[-4000:],
        }
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = "", "timed out after SIGKILL while waiting for Codex probe pipes to close"
        assistant_text = _assistant_text_from_codex_stdout(stdout or "")
        return {
            "ok": False,
            "returncode": None,
            "timeout_s": timeout_s,
            "timed_out": True,
            "stdout_tail": (stdout or "")[-4000:],
            "assistant_stdout_tail": assistant_text[-4000:],
            "stderr_tail": (stderr or "")[-4000:],
        }


def _assistant_text_from_codex_stdout(stdout: str) -> str:
    chunks: list[str] = []
    for line in stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = payload.get("item") if isinstance(payload, dict) else None
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str):
                chunks.append(text)
        elif payload.get("type") in {"agent_message", "assistant_message", "message"}:
            text = payload.get("text") or payload.get("message")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks)


def _shortcut_transcript_hits(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    text = str(payload.get("assistant_stdout_tail") or "").lower()
    if not text:
        text = f"{payload.get('stdout_tail') or ''}\n{payload.get('stderr_tail') or ''}".lower()
    return [term for term in SHORTCUT_TERMS if term in text]


def _shortcut_artifacts(root: Path) -> list[str]:
    hits: list[str] = []
    for scan_root in [root / ".tmp" / "read_pool", root / ".tmp" / "read_batch"]:
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            if path.suffix.lower() in {".py", ".sh", ".bash", ".ipynb", ".js", ".ts"} or any(term.replace(" ", "_") in name for term in SHORTCUT_TERMS):
                hits.append(str(path.relative_to(root)))
    return sorted(hits)


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    topic_root = Path(args.topic_root).expanduser().resolve()
    requested_bibkeys = [item.strip() for item in args.bibkey if item.strip()]
    bibkeys = list(dict.fromkeys(requested_bibkeys))
    setup_errors: list[str] = []
    if len(bibkeys) != len(requested_bibkeys):
        setup_errors.append("duplicate bibkeys are not allowed in a reading quality probe")
    if len(bibkeys) < args.min_papers:
        setup_errors.append(f"probe requires at least {args.min_papers} paper(s), got {len(bibkeys)}")
    if not args.codex_reread and not args.audit_existing:
        setup_errors.append("real reading quality probes require --codex-reread; use --audit-existing to validate existing artifacts only")
    work_dir = Path(args.work_dir).expanduser().resolve() if args.work_dir else Path(tempfile.mkdtemp(prefix="battery-reading-probe-"))
    work_dir.mkdir(parents=True, exist_ok=True)
    probe_root = _copy_probe_topic(topic_root, bibkeys, work_dir)
    cli = project_root / "bin" / "battery_lit"
    results: list[dict[str, Any]] = []
    bulk_codex_result = None
    before_hashes_by_bibkey = {bibkey: _artifact_hashes(probe_root / "papers" / bibkey) for bibkey in bibkeys}
    paper_scales = {bibkey: _paper_scale(probe_root, bibkey) for bibkey in bibkeys}
    if args.codex_reread and args.bulk_prompt_probe and not setup_errors:
        bulk_codex_result = _codex_bulk_reread(
            project_root,
            probe_root,
            bibkeys,
            args.model,
            args.effort,
            args.bulk_timeout,
            args.codex_bypass_sandbox,
            args.worker_timeout,
            args.bulk_max_parallel,
        )
    read_pool_audit = _audit_read_pool_run(probe_root, bibkeys) if args.bulk_prompt_probe else None
    for bibkey in bibkeys:
        paper_dir = probe_root / "papers" / bibkey
        if not paper_dir.exists():
            results.append({"bibkey": bibkey, "ok": False, "errors": [f"missing papers/{bibkey} in topic copy"]})
            continue
        before_hashes = before_hashes_by_bibkey.get(bibkey) or _artifact_hashes(paper_dir)
        codex_result = (
            _codex_reread(
                project_root,
                probe_root,
                bibkey,
                args.model,
                args.effort,
                args.per_paper_timeout,
                args.codex_bypass_sandbox,
                args.worker_timeout,
            )
            if args.codex_reread and not args.bulk_prompt_probe
            else None
        )
        after_hashes = _artifact_hashes(paper_dir)
        changed_artifacts = [name for name, after in after_hashes.items() if after and after != before_hashes.get(name)]
        validate = _run_json([str(cli), "read", "--root", str(probe_root), bibkey, "--validate-report"], probe_root)
        rebuild = _run_json([str(cli), "read", "--root", str(probe_root), bibkey, "--rebuild-note"], probe_root)
        quality = _run_json([str(cli), "read", "--root", str(probe_root), bibkey, "--quality-audit"], probe_root)
        if args.bulk_prompt_probe:
            reread_ok = bool(bulk_codex_result and bulk_codex_result.get("ok")) and bool(changed_artifacts)
        else:
            reread_ok = codex_result is not None and bool(codex_result.get("ok")) and bool(changed_artifacts)
        codex_gate_ok = (not args.codex_reread) or reread_ok
        results.append(
            {
                "bibkey": bibkey,
                "paper_scale": paper_scales.get(bibkey, {}),
                "ok": bool(validate.get("ok")) and bool(rebuild.get("ok")) and bool(quality.get("ok")) and codex_gate_ok,
                "codex_reread": codex_result,
                "shortcut_transcript_hits": _shortcut_transcript_hits(codex_result),
                "changed_artifacts": changed_artifacts,
                "reread_ok": reread_ok,
                "validate": validate,
                "rebuild": rebuild,
                "quality": quality,
            }
        )
    library_audit = _run_json([str(cli), "tool", "audit-readings", "--root", str(probe_root), "--json"], probe_root)
    successful_rereads = sum(1 for item in results if item.get("reread_ok"))
    shortcut_artifacts = _shortcut_artifacts(probe_root)
    shortcut_transcript_hits = _shortcut_transcript_hits(bulk_codex_result)
    if not args.bulk_prompt_probe:
        for item in results:
            shortcut_transcript_hits.extend(item.get("shortcut_transcript_hits") or [])
    shortcut_transcript_hits = sorted(set(shortcut_transcript_hits))
    report = {
        "ok": (
            not setup_errors
            and all(item.get("ok") for item in results)
            and bool(library_audit.get("ok"))
            and (not args.bulk_prompt_probe or bool(read_pool_audit and read_pool_audit.get("ok")))
            and (not args.codex_reread or successful_rereads >= args.min_papers)
            and not shortcut_artifacts
            and not shortcut_transcript_hits
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_topic": str(topic_root),
        "probe_topic": str(probe_root),
        "min_papers": args.min_papers,
        "paper_count": len(bibkeys),
        "paper_scales": paper_scales,
        "successful_rereads": successful_rereads,
        "setup_errors": setup_errors,
        "codex_reread": bool(args.codex_reread),
        "bulk_prompt_probe": bool(args.bulk_prompt_probe),
        "bulk_codex_result": bulk_codex_result,
        "read_pool_audit": read_pool_audit,
        "bulk_max_parallel": args.bulk_max_parallel,
        "codex_bypass_sandbox": bool(args.codex_bypass_sandbox),
        "shortcut_artifacts": shortcut_artifacts,
        "shortcut_transcript_hits": shortcut_transcript_hits,
        "model": args.model,
        "effort": args.effort,
        "results": results,
        "library_audit": library_audit,
    }
    reports_dir = Path(args.report_dir).expanduser().resolve() if args.report_dir else project_root / "reports"
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        probe_file = reports_dir / ".write_check"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink()
    except OSError:
        reports_dir = work_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = reports_dir / f"reading_quality_probe_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report["report_path"] = str(out_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded reading quality probe on temporary topic copies.")
    parser.add_argument("--project-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--topic-root", required=True)
    parser.add_argument("--bibkey", action="append", required=True)
    parser.add_argument("--work-dir")
    parser.add_argument("--report-dir")
    parser.add_argument("--codex-reread", action="store_true", help="Run independent Codex CLI reread in the temporary topic copy before auditing.")
    parser.add_argument("--bulk-prompt-probe", action="store_true", help="Run one realistic multi-paper Codex prompt instead of one Codex process per paper.")
    parser.add_argument("--audit-existing", action="store_true", help="Validate existing reading artifacts without running Codex rereads.")
    parser.add_argument("--min-papers", type=int, default=15, help="Fail the probe unless at least this many unique bibkeys are provided.")
    parser.add_argument(
        "--codex-bypass-sandbox",
        action="store_true",
        help="For Docker-contained live probes only: bypass Codex sandbox in the temporary topic copy when bwrap namespaces are unavailable.",
    )
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--per-paper-timeout", type=int, default=1800)
    parser.add_argument("--bulk-timeout", type=int, default=7200)
    parser.add_argument("--worker-timeout", type=int, default=1200, help="Timeout in seconds for the Codex process spawned by the probe.")
    parser.add_argument("--bulk-max-parallel", type=int, default=5, help="read-many parallelism requested in realistic bulk Codex prompts; capped at 5 by read-many.")
    args = parser.parse_args()
    report = run_probe(args)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
