from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable, Protocol

from .bib import list_library
from .codex_session import AppServerCodexSessionManager
from .html import build_html
from .paths import TopicPaths, repo_root
from .read import (
    NOTE_PLAN_NAME,
    SOURCE_MAP_NAME,
    audit_deep_read_quality,
    audit_reading_library,
    parse_pdf,
    rebuild_note,
    validate_deep_read_report,
)

READ_POOL_SCHEMA_VERSION = "v3-read-pool-2026-07"
READ_POOL_READER_RECORD = "reader.json"
READ_POOL_REVIEW_RECORD = "review.json"
READ_POOL_ARTIFACTS = [SOURCE_MAP_NAME, NOTE_PLAN_NAME, "deep_read.json"]
DATASET_PATCH_NAME = "dataset_section_patch.json"
DEFAULT_READ_POOL_PARALLEL = 5
DEV_READ_POOL_PARALLEL = 3
MAX_READ_POOL_PARALLEL = 20
DEFAULT_READER_REVIEW_CYCLES = 3
MAX_READER_REVIEW_CYCLES = 7
READ_POOL_CODEX_REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_READER_TIMEOUT_SECONDS = 1800
DEFAULT_REVIEWER_TIMEOUT_SECONDS = 900
_SOURCE_REF_RE = re.compile(r"\b[SCFTME]\d{3,}\b")


class PaperAgentSession(Protocol):
    def ensure_session(self, topic_root: Path, model: str | None, effort: str | None) -> dict[str, object]:
        ...

    def send_message_until_outputs(
        self,
        message: str,
        required_outputs: list[Path],
        *,
        stable_seconds: float = 5.0,
        timeout_seconds: float | None = None,
        require_output_updates: bool = False,
    ) -> dict[str, object]:
        ...

    def state(self) -> dict[str, object]:
        ...

    def close(self) -> None:
        ...


SessionFactory = Callable[[str, str], PaperAgentSession]


def run_read_pool(
    root: str | Path,
    *,
    bibkeys: list[str] | None = None,
    all_library: bool = False,
    force_reread: bool = False,
    refresh_section: str | None = None,
    run_id: str | None = None,
    max_parallel: int | None = None,
    max_cycles: int = DEFAULT_READER_REVIEW_CYCLES,
    accept_last_on_max_cycles: bool = False,
    model: str | None = None,
    effort: str | None = None,
    session_factory: SessionFactory | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    if refresh_section not in {None, "dataset"}:
        return {"ok": False, "error": f"unsupported refresh section: {refresh_section}"}
    if refresh_section and force_reread:
        return {"ok": False, "error": "--refresh-section cannot be combined with --force-reread"}
    if refresh_section and accept_last_on_max_cycles:
        return {"ok": False, "error": "scoped section refresh cannot accept a draft with unresolved reviewer issues"}
    targets = _resolve_targets(paths.root, bibkeys=bibkeys, all_library=all_library)
    if not targets:
        return {"ok": False, "error": "read-many needs at least one target bibkey"}
    run_id = run_id or f"read_pool_{time.strftime('%Y%m%d_%H%M%S')}"
    if not _valid_run_id(run_id):
        return {"ok": False, "error": "invalid read pool run_id"}
    requested_max_parallel = int(max_parallel) if max_parallel is not None else None
    limit = _effective_max_parallel(requested_max_parallel, len(targets))
    requested_max_cycles = int(max_cycles)
    effective_max_cycles = _effective_max_cycles(requested_max_cycles)
    run_dir = paths.root / ".tmp" / "read_pool" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": READ_POOL_SCHEMA_VERSION,
        "run_id": run_id,
        "root": str(paths.root),
        "targets": targets,
        "force_reread": bool(force_reread),
        "refresh_section": refresh_section,
        "requested_max_parallel": requested_max_parallel,
        "max_parallel": limit,
        "max_parallel_cap": MAX_READ_POOL_PARALLEL,
        "codex_session_budget": limit * 2,
        "requested_max_cycles": requested_max_cycles,
        "max_cycles": effective_max_cycles,
        "accept_last_on_max_cycles": bool(accept_last_on_max_cycles),
        "reader_reviewer_sessions": True,
        "batch_mode": False,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    factory = session_factory or _default_session_factory()

    if progress:
        progress(f"read-many: starting {len(targets)} paper job(s), max_parallel={limit}, run_id={run_id}")
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=limit) as executor:
        future_map = {
            executor.submit(
                _run_one_read_job,
                paths.root,
                run_id,
                bibkey,
                force_reread=force_reread,
                refresh_section=refresh_section,
                max_cycles=effective_max_cycles,
                accept_last_on_max_cycles=accept_last_on_max_cycles,
                model=model,
                effort=effort,
                session_factory=factory,
            ): bibkey
            for bibkey in targets
        }
        pending = set(future_map)
        last_progress = time.monotonic()
        while pending:
            done, pending = wait(pending, timeout=30.0, return_when=FIRST_COMPLETED)
            if not done:
                now = time.monotonic()
                if progress and now - last_progress >= 60.0:
                    progress("read-many: waiting for " + ", ".join(sorted(future_map[item] for item in pending)))
                    last_progress = now
                continue
            for future in done:
                bibkey = future_map[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {"bibkey": bibkey, "ok": False, "error": str(exc)}
                results.append(result)
                if progress:
                    progress(f"read-many: {bibkey} {'ok' if result.get('ok') else 'failed'}")

    completed = [str(item.get("bibkey")) for item in results if item.get("ok")]
    reduce_result = {"ok": True, "skipped": True, "reason": "no completed papers"}
    if completed:
        reduce_result = audit_reading_library(paths.root, bibkeys=completed)
        if reduce_result.get("ok"):
            try:
                build_html(paths.root)
            except Exception as exc:  # pragma: no cover - defensive closeout
                reduce_result = {"ok": False, "errors": [f"html build failed after read-many: {exc}"], "html_error": str(exc)}

    ok = all(item.get("ok") for item in results) and bool(reduce_result.get("ok"))
    return {
        "ok": ok,
        "run_id": run_id,
        "targets": targets,
        "requested_max_parallel": requested_max_parallel,
        "max_parallel": limit,
        "max_parallel_cap": MAX_READ_POOL_PARALLEL,
        "codex_session_budget": limit * 2,
        "requested_max_cycles": requested_max_cycles,
        "max_cycles": effective_max_cycles,
        "accept_last_on_max_cycles": bool(accept_last_on_max_cycles),
        "refresh_section": refresh_section,
        "results": sorted(results, key=lambda item: str(item.get("bibkey") or "")),
        "reduce_audit": reduce_result,
    }


def _run_one_read_job(
    root: Path,
    run_id: str,
    bibkey: str,
    *,
    force_reread: bool,
    refresh_section: str | None,
    max_cycles: int,
    accept_last_on_max_cycles: bool,
    model: str | None,
    effort: str | None,
    session_factory: SessionFactory,
) -> dict[str, Any]:
    job_dir = root / ".tmp" / "read_pool" / run_id / bibkey
    draft_dir = job_dir / "draft"
    draft_dir.mkdir(parents=True, exist_ok=True)
    reader_record = job_dir / READ_POOL_READER_RECORD
    review_record = job_dir / READ_POOL_REVIEW_RECORD
    reader = session_factory("reader", bibkey)
    reviewer = session_factory("reviewer", bibkey)
    cycles: list[dict[str, Any]] = []
    feedback: dict[str, Any] | None = None
    try:
        reader_state = reader.ensure_session(root, model, effort)
        reviewer_state = reviewer.ensure_session(root, model, effort)
        if not reader_state.get("ok"):
            return {"bibkey": bibkey, "ok": False, "error": f"reader session failed: {reader_state.get('blocker') or reader_state}"}
        if not reviewer_state.get("ok"):
            return {"bibkey": bibkey, "ok": False, "error": f"reviewer session failed: {reviewer_state.get('blocker') or reviewer_state}"}
        parsed = (
            _existing_dataset_parse(root, bibkey)
            if refresh_section == "dataset"
            else _ensure_parse(root, bibkey, force_reread=force_reread)
        )
        if not parsed.get("ok"):
            return {"bibkey": bibkey, "ok": False, "error": parsed.get("error") or "parse failed", "parse": parsed}

        section_context: dict[str, Any] | None = None
        artifact_names = READ_POOL_ARTIFACTS
        if refresh_section == "dataset":
            section_context = _prepare_dataset_context(root, bibkey, job_dir)
            if not section_context.get("ok"):
                return {"bibkey": bibkey, "ok": False, "error": section_context.get("error"), "errors": section_context.get("errors") or []}
            artifact_names = [DATASET_PATCH_NAME]

        for cycle in range(1, max_cycles + 1):
            reader_outputs = [draft_dir / name for name in artifact_names] + [reader_record]
            reader_message = (
                _dataset_reader_prompt(root, run_id, bibkey, draft_dir, reader_record, section_context or {}, cycle=cycle, feedback=feedback)
                if refresh_section == "dataset"
                else _reader_prompt(root, run_id, bibkey, draft_dir, reader_record, cycle=cycle, feedback=feedback)
            )
            reader_result = reader.send_message_until_outputs(
                reader_message,
                reader_outputs,
                stable_seconds=3.0,
                timeout_seconds=DEFAULT_READER_TIMEOUT_SECONDS,
                require_output_updates=cycle > 1,
            )
            cycle_result: dict[str, Any] = {"cycle": cycle, "reader": reader_result}
            if not reader_result.get("ok"):
                cycle_result["ok"] = False
                cycles.append(cycle_result)
                return {"bibkey": bibkey, "ok": False, "error": "reader did not produce required outputs", "cycles": cycles}
            reader_errors = _validate_reader_record(root, run_id, bibkey, reader_record, draft_dir, artifact_names=artifact_names)
            if reader_errors:
                feedback = _feedback("reader_provenance", reader_errors)
                cycle_result["reader_record_errors"] = reader_errors
                cycles.append(cycle_result)
                continue

            reviewer_message = (
                _dataset_reviewer_prompt(root, run_id, bibkey, draft_dir, review_record, cycle=cycle)
                if refresh_section == "dataset"
                else _reviewer_prompt(root, run_id, bibkey, draft_dir, review_record, cycle=cycle)
            )
            reviewer_result = reviewer.send_message_until_outputs(
                reviewer_message,
                [review_record],
                stable_seconds=2.0,
                timeout_seconds=DEFAULT_REVIEWER_TIMEOUT_SECONDS,
                require_output_updates=cycle > 1,
            )
            cycle_result["reviewer"] = reviewer_result
            if not reviewer_result.get("ok"):
                cycle_result["ok"] = False
                cycles.append(cycle_result)
                return {"bibkey": bibkey, "ok": False, "error": "reviewer did not produce review", "cycles": cycles}
            review = _load_json(review_record)
            review_errors = _validate_review_record(review, bibkey)
            if review_errors:
                feedback = _feedback("review_record", review_errors)
                cycle_result["review_record_errors"] = review_errors
                cycles.append(cycle_result)
                continue
            if review.get("verdict") == "block":
                cycle_result["ok"] = False
                cycle_result["review"] = review
                cycles.append(cycle_result)
                return {"bibkey": bibkey, "ok": False, "error": "reviewer blocked reading", "cycles": cycles}
            if review.get("verdict") == "revise":
                feedback = _feedback("reviewer", review.get("issues") or [])
                cycle_result["review"] = review
                cycles.append(cycle_result)
                continue

            finalized = (
                _finalize_dataset_section(root, run_id, bibkey, draft_dir, section_context or {})
                if refresh_section == "dataset"
                else _finalize_one(root, run_id, bibkey, draft_dir)
            )
            cycle_result["finalize"] = finalized
            cycles.append(cycle_result)
            if finalized.get("ok"):
                return {
                    "bibkey": bibkey,
                    "ok": True,
                    "cycles": cycles,
                    "reader_thread_id": reader.state().get("thread_id"),
                    "reviewer_thread_id": reviewer.state().get("thread_id"),
                    "changed": finalized.get("changed") or [],
                    "verification": finalized.get("verification") or [],
                }
            feedback = _feedback("cli_gate", finalized.get("errors") or [finalized.get("error") or "finalize failed"])
        if accept_last_on_max_cycles:
            accepted = _try_accept_last_on_max_cycles(root, run_id, bibkey, draft_dir, reader_record, review_record, max_cycles, cycles)
            if accepted.get("ok"):
                accepted["reader_thread_id"] = reader.state().get("thread_id")
                accepted["reviewer_thread_id"] = reviewer.state().get("thread_id")
                return accepted
            return {
                "bibkey": bibkey,
                "ok": False,
                "error": f"max reader-review cycles reached ({max_cycles}); accept-last failed",
                "cycles": cycles,
                "accept_last": accepted,
            }
        return {"bibkey": bibkey, "ok": False, "error": f"max reader-review cycles reached ({max_cycles})", "cycles": cycles}
    finally:
        _close_session(reader)
        _close_session(reviewer)


def _ensure_parse(root: Path, bibkey: str, *, force_reread: bool) -> dict[str, Any]:
    paper_dir = root / "papers" / bibkey
    required = [paper_dir / "paper_index.json", paper_dir / "math_index.json", paper_dir / "visual_index.md"]
    if force_reread or not all(path.exists() for path in required):
        return parse_pdf(root, bibkey)
    return {"ok": True, "skipped": "parser artifacts already present"}


def _existing_dataset_parse(root: Path, bibkey: str) -> dict[str, Any]:
    paper_dir = root / "papers" / bibkey
    required = [paper_dir / "parsed.md", paper_dir / "paper_index.json", paper_dir / "visual_index.md"]
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    if missing:
        return {
            "ok": False,
            "error": "dataset refresh requires existing parser artifacts; run parse-only first",
            "missing": missing,
        }
    return {"ok": True, "skipped": "dataset refresh reuses existing parser artifacts"}


def _try_accept_last_on_max_cycles(
    root: Path,
    run_id: str,
    bibkey: str,
    draft_dir: Path,
    reader_record: Path,
    review_record: Path,
    max_cycles: int,
    cycles: list[dict[str, Any]],
) -> dict[str, Any]:
    missing = [name for name in READ_POOL_ARTIFACTS if not (draft_dir / name).exists()]
    if missing:
        return {"ok": False, "error": "missing last draft artifacts", "errors": missing}
    reader_errors = _validate_reader_record(root, run_id, bibkey, reader_record, draft_dir)
    if reader_errors:
        return {"ok": False, "error": "reader provenance invalid", "errors": reader_errors}
    review = _load_json(review_record)
    review_errors = _validate_review_record(review, bibkey)
    if review_errors:
        return {"ok": False, "error": "review provenance invalid", "errors": review_errors}
    if review.get("verdict") == "block":
        return {"ok": False, "error": "reviewer blocked reading", "errors": _issue_strings(review.get("issues"))}

    warning = (
        "Accepted only because --accept-last-on-max-cycles was set; "
        "the reader-review cycle limit was reached before a clean reviewer pass."
    )
    _mark_draft_accepted_with_limitations(
        draft_dir / "deep_read.json",
        cycles_used=max_cycles,
        open_issues=_max_cycle_open_issues(cycles, review),
        controller_warnings=[warning],
    )
    finalized = _finalize_one(root, run_id, bibkey, draft_dir)
    if not finalized.get("ok"):
        return {"ok": False, "error": finalized.get("error") or "accept-last finalize failed", "errors": finalized.get("errors") or [], "finalize": finalized}
    return {
        "bibkey": bibkey,
        "ok": True,
        "accepted_with_limitations": True,
        "cycles": cycles,
        "changed": finalized.get("changed") or [],
        "verification": finalized.get("verification") or [],
        "warnings": [warning],
    }


def _mark_draft_accepted_with_limitations(
    path: Path,
    *,
    cycles_used: int,
    open_issues: list[str],
    controller_warnings: list[str],
) -> None:
    data = _load_json(path)
    data["reading_quality"] = {
        "status": "accepted_with_limitations",
        "acceptance_reason": "max_cycles_reached",
        "cycles_used": int(cycles_used),
        "open_issues": open_issues,
        "controller_warnings": controller_warnings,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _max_cycle_open_issues(cycles: list[dict[str, Any]], review: dict[str, Any]) -> list[str]:
    issues = _issue_strings(review.get("issues"))
    for cycle in reversed(cycles):
        issues.extend(str(item) for item in cycle.get("reader_record_errors") or [])
        issues.extend(str(item) for item in cycle.get("review_record_errors") or [])
        finalize = cycle.get("finalize") if isinstance(cycle.get("finalize"), dict) else {}
        issues.extend(str(item) for item in finalize.get("errors") or [])
        if issues:
            break
    if not issues:
        issues = ["The reviewer did not produce a clean pass before the cycle limit."]
    return list(dict.fromkeys(item for item in issues if item))[:8]


def _issue_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    rendered: list[str] = []
    for item in value:
        if isinstance(item, dict):
            parts = [str(item.get(key) or "").strip() for key in ["field_path", "problem", "reader_instruction"]]
            rendered.append(": ".join(part for part in parts if part))
        else:
            rendered.append(str(item))
    return [item for item in rendered if item]


def _finalize_one(root: Path, run_id: str, bibkey: str, draft_dir: Path) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    paper_dir = paths.paper_dir(bibkey)
    originals_dir = root / ".tmp" / "read_pool" / run_id / bibkey / "originals"
    _snapshot_originals(paper_dir, originals_dir)
    changed: list[str] = []
    verification: list[str] = []
    try:
        for name in READ_POOL_ARTIFACTS:
            shutil.copy2(draft_dir / name, paper_dir / name)
            changed.append(str((paper_dir / name).relative_to(root)))
        validate_result = validate_deep_read_report(root, bibkey)
        verification.append(f"battery_lit read {bibkey} --validate-report: {'pass' if validate_result.get('ok') else 'fail'}")
        if not validate_result.get("ok"):
            raise _ReadPoolFinalizeError("validate-report failed", validate_result.get("errors") or [])
        rebuild_result = rebuild_note(root, bibkey)
        verification.append(f"battery_lit read {bibkey} --rebuild-note: {'pass' if rebuild_result.get('ok') else 'fail'}")
        if not rebuild_result.get("ok"):
            raise _ReadPoolFinalizeError("rebuild-note failed", [rebuild_result.get("error") or str(rebuild_result)])
        for name in ["note.md", "note_zh.md", "reading_result.html"]:
            if (paper_dir / name).exists():
                changed.append(str((paper_dir / name).relative_to(root)))
        quality_result = audit_deep_read_quality(root, bibkey)
        verification.append(f"battery_lit read {bibkey} --quality-audit: {'pass' if quality_result.get('ok') else 'fail'}")
        if not quality_result.get("ok"):
            raise _ReadPoolFinalizeError("quality-audit failed", quality_result.get("errors") or [])
    except _ReadPoolFinalizeError as exc:
        _restore_originals(paper_dir, originals_dir)
        return {"ok": False, "error": exc.message, "errors": exc.errors, "restored": True, "verification": verification}
    except Exception as exc:
        _restore_originals(paper_dir, originals_dir)
        return {"ok": False, "error": str(exc), "errors": [str(exc)], "restored": True, "verification": verification}
    return {"ok": True, "changed": sorted(set(changed)), "verification": verification}


def _prepare_dataset_context(root: Path, bibkey: str, job_dir: Path) -> dict[str, Any]:
    paper_dir = root / "papers" / bibkey
    required = ["deep_read.json", SOURCE_MAP_NAME, NOTE_PLAN_NAME, "parsed.md", "paper_index.json", "visual_index.md"]
    missing = [name for name in required if not (paper_dir / name).exists()]
    if missing:
        return {"ok": False, "error": "missing dataset refresh inputs", "errors": missing}
    baseline = validate_deep_read_report(root, bibkey)
    if not baseline.get("ok"):
        return {
            "ok": False,
            "error": "existing knowledge card must validate before a scoped refresh",
            "errors": baseline.get("errors") or [],
        }
    report = _load_json(paper_dir / "deep_read.json")
    profile = report.get("paper_profile") if isinstance(report.get("paper_profile"), dict) else {}
    if "dataset_benchmark" not in [str(item) for item in profile.get("active_lenses") or []]:
        return {"ok": False, "error": f"{bibkey} does not have an active dataset_benchmark lens"}
    source_map = _load_json(paper_dir / SOURCE_MAP_NAME)
    context = {
        "ok": True,
        "bibkey": bibkey,
        "base_report_sha256": _file_sha256(paper_dir / "deep_read.json"),
        "base_source_map_sha256": _file_sha256(paper_dir / SOURCE_MAP_NAME),
        "source_id_starts": _next_source_ids(source_map),
        "style_context": {
            "title": report.get("title"),
            "paper_profile": profile,
            "one_sentence_summary": report.get("one_sentence_summary"),
            "quick_read": [
                str(item.get("text") or "")
                for item in report.get("quick_read") or []
                if isinstance(item, dict)
            ],
        },
    }
    return context


def _dataset_reader_prompt(
    root: Path,
    run_id: str,
    bibkey: str,
    draft_dir: Path,
    reader_record: Path,
    context: dict[str, Any],
    *,
    cycle: int,
    feedback: dict[str, Any] | None,
) -> str:
    feedback_block = json.dumps(feedback or {}, ensure_ascii=False, indent=2, sort_keys=True)
    style_block = json.dumps(context.get("style_context") or {}, ensure_ascii=False, indent=2)
    ids_block = json.dumps(context.get("source_id_starts") or {}, ensure_ascii=False, sort_keys=True)
    patch_path = draft_dir / DATASET_PATCH_NAME
    return f"""Refresh only the dataset module of one existing knowledge card.

Topic root: {root}
Run id: {run_id}
Target bibkey: {bibkey}
Cycle: {cycle}
Dataset patch: {patch_path.relative_to(root)}
Reader record: {reader_record.relative_to(root)}

Use the existing parser outputs; do not run PDF parsing. Read only metadata.yml, parsed.md, and paper_index.json for paper evidence. Do not inspect project code, tests, templates, schemas, old reading artifacts, visual files, or external websites. Do not read the old dataset_benchmark_understanding or its Chinese translation as evidence or as a writing template. Do not rewrite any complete reading artifact.

Use this small context only for terminology and prose style, not as evidence:
```json
{style_block}
```

Feedback to address:
```json
{feedback_block}
```

Start new source block IDs at or above these unused IDs: {ids_block}. Body/caption blocks must retain paper_index paragraph IDs; external availability evidence must use an E-prefixed block.

Write {patch_path.relative_to(root)} with exactly these fields:
{{
  "schema_version": "{READ_POOL_SCHEMA_VERSION}",
  "bibkey": "{bibkey}",
  "base_report_sha256": "{context.get('base_report_sha256')}",
  "base_source_map_sha256": "{context.get('base_source_map_sha256')}",
  "dataset_benchmark_understanding": {{
    "format": "structured_v2",
    "key_numbers": [{{"label": "Cases", "value": "8,000", "unit": "cases", "context": "What this number means.", "source_refs": ["S019"]}}],
    "construction_steps": [{{"stage": "Geometry sampling", "action": "What the authors do.", "output": "What this stage produces.", "quality_control": "How quality is checked.", "source_refs": ["S019"]}}],
    "biases_or_limits": [{{"text": "A concrete coverage limit and its consequence.", "source_refs": ["S019"], "confidence": "high"}}]
  }},
  "translation_zh": {{"dataset_benchmark_understanding": {{
    "key_numbers": [{{"label": "算例", "context": "该数字的实际含义。"}}],
    "construction_steps": [{{"stage": "几何采样", "action": "作者执行的操作。", "output": "该阶段的产物。", "quality_control": "质量控制方式。"}}],
    "biases_or_limits": ["具体的覆盖局限及其后果。"]
  }}}},
  "source_blocks": [
    {{
      "id": "S019",
      "page": 1,
      "section": "Dataset",
      "section_id": "sec:001",
      "paragraph_ids": ["p:0001"],
      "type": "dataset_scope",
      "source_kind": "body_text",
      "source_text": "Faithful evidence summary.",
      "confidence": "high"
    }}
  ]
}}

Replace all example rows and the example source block with real content, repeating rows as needed. Keep exactly the shown field names and value types; do not add synonyms such as `meaning`, `description`, `outputs`, `quality_controls`, `issue`, `detail`, or `implication`. Use exactly `id`, not `block_id`; `source_text`, not `text`; and `paragraph_ids`, not `paragraph_id`. The module must state concrete corpus numbers, ordered construction stages and outputs, quality controls, and coverage limits. Every fact needs source_refs that point to one of these new source block IDs. Chinese arrays must have the same row counts and order as English and mirror all displayed prose in natural Chinese. Leave availability and visual cards outside this module unchanged.

Write as if this module had always been part of the final knowledge card. Reader-facing text must not mention rereading, updating, old results, patches, prompts, schemas, validators, reviewers, parsing workflow, or the current task. Use direct present-tense paper interpretation, not process narration.

Then write {reader_record.relative_to(root)} with this exact JSON shape:
{{
  "schema_version": "{READ_POOL_SCHEMA_VERSION}",
  "role": "paper_read_reader",
  "run_id": "{run_id}",
  "bibkey": "{bibkey}",
  "cycle": {cycle},
  "thread_role": "reader",
  "forbidden_inputs_checked": true,
  "writes_final_artifacts": false,
  "draft_artifacts_written": ["{patch_path.relative_to(root)}"],
  "allowed_inputs": ["papers/{bibkey}/metadata.yml", "papers/{bibkey}/parsed.md", "papers/{bibkey}/paper_index.json"],
  "notes": []
}}
Stop after both files are written.
"""


def _dataset_reviewer_prompt(
    root: Path,
    run_id: str,
    bibkey: str,
    draft_dir: Path,
    review_record: Path,
    *,
    cycle: int,
) -> str:
    patch_path = draft_dir / DATASET_PATCH_NAME
    return f"""Review one staged dataset-module patch as an independent reviewer.

Topic root: {root}
Run id: {run_id}
Target bibkey: {bibkey}
Cycle: {cycle}
Patch: {patch_path.relative_to(root)}
Review record: {review_record.relative_to(root)}

Read the patch and only the paper-local metadata, parsed text, and paper_index needed to verify it. Do not inspect project code, tests, templates, schemas, old reading artifacts, visual files, or external websites. Do not use the old dataset module as evidence or as a template. Do not edit the patch or final artifacts.

Check that corpus numbers, construction stages, outputs, quality controls, limitations, and source refs are concrete and supported. Chinese must fully mirror the English in natural Chinese. Treat visual_consistent as not applicable and true because this patch cannot change visuals. The prose must match a permanent reader-facing knowledge card and must not discuss rereading, updates, old results, patches, prompts, schemas, validators, reviewers, parsing workflow, or the current task.

Write {review_record.relative_to(root)} with this exact JSON shape:
{{
  "schema_version": "{READ_POOL_SCHEMA_VERSION}",
  "role": "paper_read_reviewer",
  "run_id": "{run_id}",
  "bibkey": "{bibkey}",
  "cycle": {cycle},
  "thread_role": "reviewer",
  "verdict": "pass",
  "checks": {{
    "paper_specific": true,
    "source_grounded": true,
    "zh_complete": true,
    "visual_consistent": true,
    "no_template_reuse": true,
    "no_prompt_leak": true
  }},
  "issues": []
}}
Use only "pass", "revise", or "block" for verdict. Set verdict to "revise" for any fixable problem and "block" only when the evidence cannot support a valid dataset module. Each issue must include field_path, severity, problem, evidence_ref, and reader_instruction. Stop after writing the review record.
"""


def _finalize_dataset_section(
    root: Path,
    run_id: str,
    bibkey: str,
    draft_dir: Path,
    context: dict[str, Any],
) -> dict[str, Any]:
    paper_dir = root / "papers" / bibkey
    patch = _load_json(draft_dir / DATASET_PATCH_NAME)
    errors = _validate_dataset_patch(patch, context)
    if errors:
        return {"ok": False, "error": "invalid dataset section patch", "errors": errors}
    if _file_sha256(paper_dir / "deep_read.json") != context.get("base_report_sha256"):
        return {"ok": False, "error": "deep_read.json changed during dataset refresh", "errors": ["concurrent report update"]}
    if _file_sha256(paper_dir / SOURCE_MAP_NAME) != context.get("base_source_map_sha256"):
        return {"ok": False, "error": "source_map.json changed during dataset refresh", "errors": ["concurrent source-map update"]}

    report = _load_json(paper_dir / "deep_read.json")
    source_map = _load_json(paper_dir / SOURCE_MAP_NAME)
    existing_blocks = source_map.get("blocks") if isinstance(source_map.get("blocks"), list) else []
    existing_ids = {str(item.get("id")) for item in existing_blocks if isinstance(item, dict)}
    patch_blocks = patch.get("source_blocks") if isinstance(patch.get("source_blocks"), list) else []
    patch_ids = {str(item.get("id")) for item in patch_blocks if isinstance(item, dict)}
    collisions = sorted(existing_ids.intersection(patch_ids))
    if collisions:
        return {"ok": False, "error": "dataset patch source ids collide", "errors": collisions}

    merged = copy.deepcopy(report)
    merged["dataset_benchmark_understanding"] = copy.deepcopy(patch["dataset_benchmark_understanding"])
    zh = merged["translations"]["zh"]
    translation = patch["translation_zh"]
    zh.setdefault("type_sections", {})["dataset_benchmark_understanding"] = copy.deepcopy(
        translation["dataset_benchmark_understanding"]
    )

    used_ids = {_source_ref_id(ref) for ref in _collect_source_refs(merged)}
    merged_source_map = copy.deepcopy(source_map)
    merged_source_map["blocks"] = [
        block
        for block in [*copy.deepcopy(existing_blocks), *copy.deepcopy(patch_blocks)]
        if isinstance(block, dict) and str(block.get("id")) in used_ids
    ]

    (draft_dir / SOURCE_MAP_NAME).write_text(
        json.dumps(merged_source_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (draft_dir / "deep_read.json").write_text(
        json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    shutil.copy2(paper_dir / NOTE_PLAN_NAME, draft_dir / NOTE_PLAN_NAME)
    result = _finalize_one(root, run_id, bibkey, draft_dir)
    if result.get("ok"):
        result["parser_skipped"] = True
        result["refresh_section"] = "dataset"
    return result


def _validate_dataset_patch(patch: dict[str, Any], context: dict[str, Any]) -> list[str]:
    required = {
        "schema_version",
        "bibkey",
        "base_report_sha256",
        "base_source_map_sha256",
        "dataset_benchmark_understanding",
        "translation_zh",
        "source_blocks",
    }
    errors: list[str] = []
    missing = sorted(required - set(patch))
    extra = sorted(set(patch) - required)
    if missing:
        errors.append(f"missing patch fields: {', '.join(missing)}")
    if extra:
        errors.append(f"unsupported patch fields: {', '.join(extra)}")
    if patch.get("schema_version") != READ_POOL_SCHEMA_VERSION:
        errors.append(f"schema_version must be {READ_POOL_SCHEMA_VERSION}")
    for key in ["bibkey", "base_report_sha256", "base_source_map_sha256"]:
        if patch.get(key) != context.get(key):
            errors.append(f"patch {key} does not match dataset refresh context")
    dataset = patch.get("dataset_benchmark_understanding")
    if not isinstance(dataset, dict) or dataset.get("format") != "structured_v2":
        errors.append("dataset_benchmark_understanding must use structured_v2")
    translation = patch.get("translation_zh")
    if not isinstance(translation, dict):
        errors.append("translation_zh must be an object")
    elif set(translation) != {"dataset_benchmark_understanding"}:
        errors.append("translation_zh must contain only dataset_benchmark_understanding")
    blocks = patch.get("source_blocks")
    if not isinstance(blocks, list) or not blocks:
        errors.append("source_blocks must be a non-empty list")
    block_ids: list[str] = []
    for index, item in enumerate(blocks or []):
        block_id = str(item.get("id") or "") if isinstance(item, dict) else ""
        if not block_id:
            errors.append(f"source_blocks[{index}] is missing id")
        else:
            block_ids.append(block_id)
    if len(block_ids) != len(set(block_ids)):
        errors.append("source_blocks contain duplicate ids")
    dataset_refs = {_source_ref_id(ref) for ref in _collect_source_refs(dataset)}
    missing_refs = sorted(ref for ref in dataset_refs if ref and ref not in set(block_ids))
    if missing_refs:
        errors.append(f"dataset section has source refs missing from patch blocks: {', '.join(missing_refs)}")
    return errors


def _next_source_ids(source_map: dict[str, Any]) -> dict[str, str]:
    maxima = {prefix: 0 for prefix in "SCFTME"}
    for block in source_map.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        match = _SOURCE_REF_RE.fullmatch(str(block.get("id") or ""))
        if match:
            value = match.group(0)
            maxima[value[0]] = max(maxima[value[0]], int(value[1:]))
    return {prefix: f"{prefix}{value + 1:03d}" for prefix, value in maxima.items()}


def _collect_source_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "source_refs" and isinstance(item, list):
                refs.extend(str(ref) for ref in item)
            else:
                refs.extend(_collect_source_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_collect_source_refs(item))
    return refs


def _source_ref_id(ref: str) -> str:
    match = _SOURCE_REF_RE.search(str(ref))
    return match.group(0) if match else str(ref).split()[0]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reader_prompt(root: Path, run_id: str, bibkey: str, draft_dir: Path, reader_record: Path, *, cycle: int, feedback: dict[str, Any] | None) -> str:
    feedback_block = json.dumps(feedback or {}, ensure_ascii=False, indent=2, sort_keys=True)
    return f"""Read one paper and write a staged deep-read bundle.

Topic root: {root}
Run id: {run_id}
Target bibkey: {bibkey}
Cycle: {cycle}
Draft directory: {draft_dir.relative_to(root)}
Reader record: {reader_record.relative_to(root)}

Use only paper-local evidence under papers/{bibkey}/ and project-root schemas/skills. Do not read old reading artifacts as evidence:
- papers/{bibkey}/source_map.json
- papers/{bibkey}/note_plan.json
- papers/{bibkey}/deep_read.json
- papers/{bibkey}/note.md
- papers/{bibkey}/note_zh.md
- papers/{bibkey}/reading_result.html

Allowed paper evidence includes metadata.yml, parsed.md, paper_index.json, math_index.json, formula_vision.json, visual_index.md, page_images/*, math_pages/*, and at most one external availability lookup when the paper gives a code/data clue.

Feedback to address in this cycle:
```json
{feedback_block}
```

Write these three staged artifacts, not final paper artifacts:
- {draft_dir.relative_to(root)}/source_map.json
- {draft_dir.relative_to(root)}/note_plan.json
- {draft_dir.relative_to(root)}/deep_read.json

Then write {reader_record.relative_to(root)} with this exact JSON shape:
{{
  "schema_version": "{READ_POOL_SCHEMA_VERSION}",
  "role": "paper_read_reader",
  "run_id": "{run_id}",
  "bibkey": "{bibkey}",
  "cycle": {cycle},
  "thread_role": "reader",
  "forbidden_inputs_checked": true,
  "writes_final_artifacts": false,
  "draft_artifacts_written": [
    "{(draft_dir / SOURCE_MAP_NAME).relative_to(root)}",
    "{(draft_dir / NOTE_PLAN_NAME).relative_to(root)}",
    "{(draft_dir / 'deep_read.json').relative_to(root)}"
  ],
  "allowed_inputs": ["papers/{bibkey}/metadata.yml", "papers/{bibkey}/paper_index.json"],
  "notes": []
}}

Reader-facing text must be paper-specific, Chinese translations must be real Chinese prose, visual cards must cite matching page/source refs, and no workflow or validator wording may appear in the final reader content. Stop after the record is written.
"""


def _reviewer_prompt(root: Path, run_id: str, bibkey: str, draft_dir: Path, review_record: Path, *, cycle: int) -> str:
    return f"""Review one staged paper-reading draft. You are an independent reviewer, not the reader.

Topic root: {root}
Run id: {run_id}
Target bibkey: {bibkey}
Cycle: {cycle}
Draft directory: {draft_dir.relative_to(root)}
Review record: {review_record.relative_to(root)}

Read the staged draft files and only the paper-local evidence needed to verify claims:
- {draft_dir.relative_to(root)}/source_map.json
- {draft_dir.relative_to(root)}/note_plan.json
- {draft_dir.relative_to(root)}/deep_read.json
- papers/{bibkey}/metadata.yml
- papers/{bibkey}/paper_index.json
- papers/{bibkey}/math_index.json when theory/formulas are active
- papers/{bibkey}/visual_index.md or selected page_images when visual cards are present

Do not edit any draft or final artifact. Write only {review_record.relative_to(root)}.

Use this JSON shape:
{{
  "schema_version": "{READ_POOL_SCHEMA_VERSION}",
  "role": "paper_read_reviewer",
  "run_id": "{run_id}",
  "bibkey": "{bibkey}",
  "cycle": {cycle},
  "thread_role": "reviewer",
  "verdict": "pass",
  "checks": {{
    "paper_specific": true,
    "source_grounded": true,
    "zh_complete": true,
    "visual_consistent": true,
    "no_template_reuse": true,
    "no_prompt_leak": true
  }},
  "issues": []
}}

Set verdict to "revise" if any fixable issue remains. Each issue must include field_path, severity, problem, evidence_ref, and reader_instruction. Set verdict to "block" only for missing PDF/evidence or unsafe provenance that the reader cannot fix.
"""


def _validate_reader_record(
    root: Path,
    run_id: str,
    bibkey: str,
    path: Path,
    draft_dir: Path,
    *,
    artifact_names: list[str] | None = None,
) -> list[str]:
    record = _load_json(path)
    errors: list[str] = []
    expected_artifacts = artifact_names or READ_POOL_ARTIFACTS
    if record.get("schema_version") != READ_POOL_SCHEMA_VERSION:
        errors.append(f"{path.name}: schema_version must be {READ_POOL_SCHEMA_VERSION}")
    if record.get("role") != "paper_read_reader":
        errors.append(f"{path.name}: role must be paper_read_reader")
    if record.get("run_id") != run_id or record.get("bibkey") != bibkey:
        errors.append(f"{path.name}: run_id/bibkey mismatch")
    if record.get("forbidden_inputs_checked") is not True:
        errors.append(f"{path.name}: forbidden_inputs_checked must be true")
    if record.get("writes_final_artifacts") is True:
        errors.append(f"{path.name}: reader must not write final artifacts")
    expected = {str((draft_dir / name).relative_to(root)) for name in expected_artifacts}
    actual = {str(item) for item in record.get("draft_artifacts_written") or []}
    if expected - actual:
        errors.append(f"{path.name}: missing draft_artifacts_written entries: {', '.join(sorted(expected - actual))}")
    for name in expected_artifacts:
        if not (draft_dir / name).exists() or (draft_dir / name).stat().st_size <= 0:
            errors.append(f"{path.name}: missing staged {name}")
    return errors


def _validate_review_record(record: dict[str, Any], bibkey: str) -> list[str]:
    errors: list[str] = []
    if record.get("schema_version") != READ_POOL_SCHEMA_VERSION:
        errors.append(f"{READ_POOL_REVIEW_RECORD}: schema_version must be {READ_POOL_SCHEMA_VERSION}")
    if record.get("role") != "paper_read_reviewer":
        errors.append(f"{READ_POOL_REVIEW_RECORD}: role must be paper_read_reviewer")
    if record.get("bibkey") != bibkey:
        errors.append(f"{READ_POOL_REVIEW_RECORD}: bibkey mismatch")
    if record.get("verdict") not in {"pass", "revise", "block"}:
        errors.append(f"{READ_POOL_REVIEW_RECORD}: verdict must be pass, revise, or block")
    checks = record.get("checks") if isinstance(record.get("checks"), dict) else {}
    if record.get("verdict") == "pass":
        for field in ["paper_specific", "source_grounded", "zh_complete", "visual_consistent", "no_template_reuse", "no_prompt_leak"]:
            if checks.get(field) is not True:
                errors.append(f"{READ_POOL_REVIEW_RECORD}: checks.{field} must be true for pass verdict")
    issues = record.get("issues")
    if issues is not None and not isinstance(issues, list):
        errors.append(f"{READ_POOL_REVIEW_RECORD}: issues must be a list")
    for index, issue in enumerate(issues or []):
        if not isinstance(issue, dict):
            errors.append(f"{READ_POOL_REVIEW_RECORD}: issues[{index}] must be an object")
            continue
        for field in ["field_path", "severity", "problem", "reader_instruction"]:
            if not str(issue.get(field) or "").strip():
                errors.append(f"{READ_POOL_REVIEW_RECORD}: issues[{index}] missing {field}")
    return errors


def _feedback(kind: str, payload: Any) -> dict[str, Any]:
    return {"kind": kind, "items": payload}


def _resolve_targets(root: Path, *, bibkeys: list[str] | None, all_library: bool) -> list[str]:
    if all_library:
        return [str(item["bibkey"]) for item in list_library(root) if str(item.get("bibkey") or "").strip()]
    seen: set[str] = set()
    targets: list[str] = []
    for bibkey in bibkeys or []:
        value = str(bibkey).strip()
        if value and value not in seen:
            seen.add(value)
            targets.append(value)
    return targets


def _default_session_factory() -> SessionFactory:
    project_root = repo_root()
    return lambda role, bibkey: AppServerCodexSessionManager(
        project_root=project_root,
        request_timeout=READ_POOL_CODEX_REQUEST_TIMEOUT_SECONDS,
    )


def _snapshot_originals(paper_dir: Path, originals_dir: Path) -> None:
    originals_dir.mkdir(parents=True, exist_ok=True)
    for name in [*READ_POOL_ARTIFACTS, "note.md", "note_zh.md", "reading_result.html"]:
        source = paper_dir / name
        if source.exists():
            shutil.copy2(source, originals_dir / name)
        else:
            marker = originals_dir / f"{name}.missing"
            marker.write_text("missing\n", encoding="utf-8")


def _restore_originals(paper_dir: Path, originals_dir: Path) -> None:
    for name in [*READ_POOL_ARTIFACTS, "note.md", "note_zh.md", "reading_result.html"]:
        target = paper_dir / name
        source = originals_dir / name
        missing_marker = originals_dir / f"{name}.missing"
        if source.exists():
            shutil.copy2(source, target)
        elif missing_marker.exists() and target.exists():
            target.unlink()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _valid_run_id(value: str) -> bool:
    return bool(value) and value not in {".", ".."} and all(char.isalnum() or char in "_.-" for char in value)


def _close_session(session: PaperAgentSession) -> None:
    close = getattr(session, "close", None)
    if callable(close):
        close()


def _effective_max_cycles(value: int) -> int:
    return max(1, min(int(value), MAX_READER_REVIEW_CYCLES))


def _effective_max_parallel(requested: int | None, target_count: int) -> int:
    desired = DEFAULT_READ_POOL_PARALLEL if requested is None else int(requested)
    return max(1, min(desired, int(target_count), MAX_READ_POOL_PARALLEL))


class _ReadPoolFinalizeError(RuntimeError):
    def __init__(self, message: str, errors: list[Any]) -> None:
        super().__init__(message)
        self.message = message
        self.errors = [str(error) for error in errors]
