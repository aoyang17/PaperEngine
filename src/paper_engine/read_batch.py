from __future__ import annotations

import json
import os
import re
import shutil
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable

from .bib import list_library
from .codex_worker import SubprocessCodexRunner
from .paths import TopicPaths
from .read import (
    NOTE_PLAN_NAME,
    SOURCE_MAP_NAME,
    audit_deep_read_quality,
    audit_reading_library,
    rebuild_note,
    validate_deep_read_report,
)
from .sidecars import (
    READ_DRAFT_WORKER_SCHEMA_VERSION,
    READ_DRAFT_WORKER_ROLE,
    normalize_read_draft_worker_record_paths,
    validate_read_draft_worker_record,
    validate_read_harvest_finding,
)

MAX_READ_BATCH_TARGETS = 5
DEFAULT_READ_BATCH_PARALLEL_WORKERS = 5
MAX_READ_BATCH_PARALLEL_WORKERS = 5
READ_BATCH_HARVEST_NAME = "harvest.json"
READ_BATCH_DRAFT_WORKER_NAME = "draft_worker.json"
READ_BATCH_ARTIFACTS = [
    SOURCE_MAP_NAME,
    NOTE_PLAN_NAME,
    "deep_read.json",
]
READ_BATCH_EVIDENCE_PACK_NAME = "evidence_pack.md"
READ_BATCH_GENERATED_ARTIFACTS = [
    *READ_BATCH_ARTIFACTS,
    "note.md",
    "note_zh.md",
    "reading_result.html",
]
DEFAULT_READ_BATCH_WORKER_TIMEOUT_SECONDS = 1500


def prepare_read_batch(
    root: str | Path,
    *,
    bibkeys: list[str] | None = None,
    all_library: bool = False,
    force_reread: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    targets = _resolve_targets(paths.root, bibkeys=bibkeys, all_library=all_library)
    if not targets:
        return {"ok": False, "error": "read-batch needs at least one target bibkey"}
    if len(targets) > MAX_READ_BATCH_TARGETS:
        return {
            "ok": False,
            "error": f"read-batch target count exceeds maximum {MAX_READ_BATCH_TARGETS}; split the job into chunks",
            "target_count": len(targets),
            "max_targets": MAX_READ_BATCH_TARGETS,
            "suggested_chunks": _suggest_chunks(targets),
        }
    run_id = run_id or f"read_batch_{time.strftime('%Y%m%d_%H%M%S')}"
    if not _valid_run_id(run_id):
        return {"ok": False, "error": "invalid read-batch run_id"}
    run_dir = paths.root / ".tmp" / "read_batch" / run_id
    drafts_dir = run_dir / "drafts"
    findings_dir = run_dir / "findings"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    findings_dir.mkdir(parents=True, exist_ok=True)
    parallel_required = len(targets) > 1
    manifest = {
        "schema_version": "v3-read-batch-2026-07",
        "run_id": run_id,
        "root": str(paths.root),
        "targets": targets,
        "force_reread": bool(force_reread),
        "drafts_dir": str(drafts_dir.relative_to(paths.root)),
        "findings_dir": str(findings_dir.relative_to(paths.root)),
        "draft_worker_mode": "parallel_required" if parallel_required else "single_paper_optional",
        "harvest_mode": "parallel_required" if parallel_required else "single_paper_optional",
        "max_parallel_subagents": min(DEFAULT_READ_BATCH_PARALLEL_WORKERS, len(targets)),
        "max_parallel_cap": MAX_READ_BATCH_PARALLEL_WORKERS,
        "allowed_findings_roles": ["paper_read_draft_worker"],
        "final_writer": "parallel_sidecar_draft_workers" if parallel_required else "current_worker",
        "finalize_only_writes": True,
        "fallback_policy": "block_not_sequential" if parallel_required else "single_paper_may_use_current_worker",
        "required_artifacts": READ_BATCH_ARTIFACTS,
        "max_targets": MAX_READ_BATCH_TARGETS,
        "instructions": [
            "Generate each paper's reading bundle in drafts/<bibkey>/ only.",
            "For multi-paper batches, create one parallel draft worker per paper; each worker must write drafts/<bibkey>/source_map.json, note_plan.json, deep_read.json, and findings/<bibkey>/draft_worker.json.",
            "If parallel draft workers are unavailable for a multi-paper batch, stop and report the blocker; do not silently process the batch sequentially in the main session.",
            "Use the code-generated evidence_packs/<bibkey>/evidence_pack.md as a navigation aid before running broad evidence searches.",
            "Workers should read the evidence pack first and then write a complete draft bundle; do not spend the worker turn on open-ended evidence exploration.",
            "Do not create or run deterministic helper scripts, draft generators, or parsed/index-only bulk writers in this staging directory.",
            "Each draft must come from a per-paper paper_deep_read workflow, not one generic schema filler shared across papers.",
            "Do not read existing deep_read.json, note_plan.json, reading_result.html, note.md, or note_zh.md as evidence when force_reread is true.",
            "Run finalize only after every target draft contains source_map.json, note_plan.json, and deep_read.json.",
        ],
    }
    for bibkey in targets:
        (drafts_dir / bibkey).mkdir(parents=True, exist_ok=True)
        (findings_dir / bibkey).mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "ok": True,
        "run_id": run_id,
        "targets": targets,
        "manifest": str((run_dir / "manifest.json").relative_to(paths.root)),
        "drafts_dir": str(drafts_dir.relative_to(paths.root)),
        "findings_dir": str(findings_dir.relative_to(paths.root)),
        "draft_worker_mode": manifest["draft_worker_mode"],
        "harvest_mode": manifest["harvest_mode"],
        "max_parallel_subagents": manifest["max_parallel_subagents"],
        "required_artifacts": READ_BATCH_ARTIFACTS,
        "force_reread": bool(force_reread),
    }


def finalize_read_batch(root: str | Path, run_id: str, *, rebuild: bool = True) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    if not _valid_run_id(run_id):
        return {"ok": False, "error": "invalid read-batch run_id"}
    run_dir = paths.root / ".tmp" / "read_batch" / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return {"ok": False, "error": f"missing read-batch manifest: {manifest_path}"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    targets = [str(item) for item in manifest.get("targets") or [] if str(item).strip()]
    try:
        drafts_dir = _resolve_drafts_dir(paths.root, run_dir, str(manifest.get("drafts_dir") or ""))
        findings_dir = _resolve_findings_dir(paths.root, run_dir, str(manifest.get("findings_dir") or ""))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    missing = _missing_drafts(drafts_dir, targets)
    if missing:
        return {"ok": False, "error": "missing draft artifacts", "missing": missing}
    harvest_errors = _validate_required_worker_records(paths.root, manifest, findings_dir, targets)
    if harvest_errors:
        return {"ok": False, "error": "missing or invalid read-batch draft-worker records", "errors": harvest_errors}
    hygiene_errors = _staging_hygiene_errors(run_dir, drafts_dir, findings_dir, targets)
    if hygiene_errors:
        return {"ok": False, "error": "read-batch staging contains unsupported helper or scratch files", "errors": hygiene_errors}
    preflight_repairs = _preflight_draft_consistency(paths.root, drafts_dir, targets)

    originals_dir = run_dir / "originals"
    _snapshot_originals(paths, targets, originals_dir)
    changed: list[str] = []
    verification: list[str] = []
    try:
        if bool(manifest.get("force_reread")):
            noops = _no_op_drafts(paths, drafts_dir, targets)
            if noops:
                raise _ReadBatchError("force-reread draft is identical to existing artifacts", None, {"no_op_bibkeys": noops})
        for bibkey in targets:
            paper_dir = paths.paper_dir(bibkey)
            paper_dir.mkdir(parents=True, exist_ok=True)
            for name in READ_BATCH_ARTIFACTS:
                shutil.copy2(drafts_dir / bibkey / name, paper_dir / name)
                changed.append(str((paper_dir / name).relative_to(paths.root)))

        validate_failures: dict[str, Any] = {}
        for bibkey in targets:
            validate_result = validate_deep_read_report(paths.root, bibkey)
            verification.append(f"paper_engine read {bibkey} --validate-report: {'pass' if validate_result.get('ok') else 'fail'}")
            if not validate_result.get("ok"):
                validate_failures[bibkey] = validate_result
        if validate_failures:
            raise _ReadBatchError("batch validate-report failed", None, {"failed_papers": validate_failures})

        if rebuild:
            rebuild_failures: dict[str, Any] = {}
            for bibkey in targets:
                rebuild_result = rebuild_note(paths.root, bibkey)
                verification.append(f"paper_engine read {bibkey} --rebuild-note: {'pass' if rebuild_result.get('ok') else 'fail'}")
                if not rebuild_result.get("ok"):
                    rebuild_failures[bibkey] = rebuild_result
                else:
                    for name in ["note.md", "note_zh.md", "reading_result.html"]:
                        if (paths.paper_dir(bibkey) / name).exists():
                            changed.append(str((paths.paper_dir(bibkey) / name).relative_to(paths.root)))
            if rebuild_failures:
                raise _ReadBatchError("batch rebuild-note failed", None, {"failed_papers": rebuild_failures})

        quality_failures: dict[str, Any] = {}
        for bibkey in targets:
            quality_result = audit_deep_read_quality(paths.root, bibkey)
            verification.append(f"paper_engine read {bibkey} --quality-audit: {'pass' if quality_result.get('ok') else 'fail'}")
            if not quality_result.get("ok"):
                quality_failures[bibkey] = quality_result
        if quality_failures:
            raise _ReadBatchError("batch quality-audit failed", None, {"failed_papers": quality_failures})

        batch_result = audit_reading_library(paths.root, bibkeys=targets)
        verification.append(f"paper_engine tool audit-readings --selected-batch: {'pass' if batch_result.get('ok') else 'fail'}")
        if not batch_result.get("ok"):
            raise _ReadBatchError("batch audit failed", None, batch_result)
    except _ReadBatchError as exc:
        _restore_originals(paths, targets, originals_dir)
        return {
            "ok": False,
            "error": exc.message,
            "bibkey": exc.bibkey,
            "details": exc.details,
            "restored": True,
            "verification": verification,
        }
    except Exception as exc:
        _restore_originals(paths, targets, originals_dir)
        return {
            "ok": False,
            "error": f"read-batch finalize exception: {exc}",
            "restored": True,
            "verification": verification,
        }

    return {
        "ok": True,
        "run_id": run_id,
        "targets": targets,
        "draft_worker_mode": manifest.get("draft_worker_mode") or manifest.get("harvest_mode") or "unknown",
        "harvest_mode": manifest.get("harvest_mode") or "unknown",
        "findings_dir": manifest.get("findings_dir"),
        "max_parallel_subagents": manifest.get("max_parallel_subagents"),
        "changed": sorted(set(changed)),
        "verification": verification,
        "preflight_repairs": preflight_repairs,
        "audit_scope": "batch",
        "batch_audit": {"ok": True, "target_bibkeys": targets},
        "library_audit": {
            "ok": None,
            "skipped": True,
            "reason": "run `paper_engine tool audit-readings --json` after all read-batch chunks are finalized",
        },
    }


def _preflight_draft_consistency(root: Path, drafts_dir: Path, targets: list[str]) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    for bibkey in targets:
        draft_dir = drafts_dir / bibkey
        note_plan_path = draft_dir / NOTE_PLAN_NAME
        deep_read_path = draft_dir / "deep_read.json"
        source_map_path = draft_dir / SOURCE_MAP_NAME
        try:
            note_plan = json.loads(note_plan_path.read_text(encoding="utf-8"))
            deep_read = json.loads(deep_read_path.read_text(encoding="utf-8"))
            source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        changed: list[str] = []
        if _sync_source_map_section_ids(root, bibkey, source_map):
            changed.append("source_map.section_id")
        if _sync_note_plan_central_claims(note_plan, deep_read):
            changed.append("note_plan.central_claims")
        if _sanitize_deep_read_schema_shape(deep_read):
            changed.append("deep_read.schema_shape")
        if _sync_visual_card_pages(source_map, deep_read):
            changed.append("visual_cards.page")
        if changed:
            source_map_path.write_text(json.dumps(source_map, indent=2, ensure_ascii=False), encoding="utf-8")
            note_plan_path.write_text(json.dumps(note_plan, indent=2, ensure_ascii=False), encoding="utf-8")
            deep_read_path.write_text(json.dumps(deep_read, indent=2, ensure_ascii=False), encoding="utf-8")
            repairs.append({"bibkey": bibkey, "fields": changed})
    return repairs


def _sync_source_map_section_ids(root: Path, bibkey: str, source_map: dict[str, Any]) -> bool:
    paper_index = _load_json_object(root / "papers" / bibkey / "paper_index.json")
    sections = paper_index.get("sections") if isinstance(paper_index.get("sections"), list) else []
    section_ids = {str(item.get("section_id") or "") for item in sections if isinstance(item, dict)}
    if not section_ids:
        return False
    first_section_id = next((str(item.get("section_id") or "") for item in sections if isinstance(item, dict) and item.get("section_id")), "")
    paragraph_sections = {
        str(item.get("paragraph_id") or ""): str(item.get("section_id") or "")
        for item in (paper_index.get("paragraphs") or [])
        if isinstance(item, dict)
    }
    changed = False
    for block in source_map.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        if str(block.get("source_kind") or "") == "external" or str(block.get("id") or "").startswith("E"):
            continue
        section_id = str(block.get("section_id") or "")
        if section_id in section_ids:
            continue
        replacement = ""
        for paragraph_id in block.get("paragraph_ids") or []:
            candidate = paragraph_sections.get(str(paragraph_id))
            if candidate in section_ids:
                replacement = candidate
                break
        replacement = replacement or first_section_id
        if replacement:
            block["section_id"] = replacement
            changed = True
    return changed


def _sync_note_plan_central_claims(note_plan: dict[str, Any], deep_read: dict[str, Any]) -> bool:
    actual = deep_read.get("central_claims") if isinstance(deep_read.get("central_claims"), list) else []
    if not actual:
        return False
    planned = note_plan.get("central_claims")
    if not isinstance(planned, list):
        planned = []
    changed = False
    existing = {_normalize_claim_text(item) for item in planned if _normalize_claim_text(item)}
    for item in actual:
        claim = _claim_text(item)
        if not claim:
            continue
        normalized = _normalize_claim_text(claim)
        if normalized in existing:
            continue
        planned.append(claim)
        existing.add(normalized)
        changed = True
    if changed or not isinstance(note_plan.get("central_claims"), list):
        note_plan["central_claims"] = planned
    return changed


def _claim_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("claim") or "").strip()
    return str(item or "").strip()


def _normalize_claim_text(item: Any) -> str:
    return re.sub(r"\s+", " ", _claim_text(item)).strip().lower()


def _sanitize_deep_read_schema_shape(deep_read: dict[str, Any]) -> bool:
    changed = False
    evaluation = deep_read.get("evaluation") if isinstance(deep_read.get("evaluation"), dict) else {}
    numeric_results = evaluation.get("numeric_results") if isinstance(evaluation.get("numeric_results"), list) else []
    allowed_numeric_keys = {
        "dataset_or_task",
        "metric",
        "value",
        "unit",
        "baseline",
        "comparison",
        "higher_is_better",
        "source_refs",
        "interpretation",
        "what_it_does_not_prove",
    }
    for item in numeric_results:
        if not isinstance(item, dict):
            continue
        for key in list(item):
            if key not in allowed_numeric_keys:
                item.pop(key, None)
                changed = True

    translations = deep_read.get("translations") if isinstance(deep_read.get("translations"), dict) else {}
    zh = translations.get("zh") if isinstance(translations.get("zh"), dict) else {}
    quick_read = zh.get("quick_read") if isinstance(zh, dict) else None
    if isinstance(quick_read, list):
        normalized: list[Any] = []
        for item in quick_read:
            if isinstance(item, dict) and "text" in item:
                normalized.append(str(item.get("text") or ""))
                changed = True
            else:
                normalized.append(item)
        zh["quick_read"] = normalized
    return changed


def _sync_visual_card_pages(source_map: dict[str, Any], deep_read: dict[str, Any]) -> bool:
    blocks = {
        str(block.get("id") or ""): block
        for block in source_map.get("blocks") or []
        if isinstance(block, dict)
    }
    changed = False
    for card in deep_read.get("visual_cards") or []:
        if not isinstance(card, dict):
            continue
        image_page = _page_from_visual_image_path(str(card.get("image_path") or ""))
        ref_ids = [_source_ref_block_id(str(ref)) for ref in card.get("source_refs") or []]
        visual_blocks = [
            blocks[ref_id]
            for ref_id in ref_ids
            if ref_id in blocks and _is_visual_source_block(blocks[ref_id])
        ]
        ref_pages = {
            int(block["page"])
            for block in visual_blocks
            if isinstance(block.get("page"), int) and int(block.get("page") or 0) > 0
        }
        desired_page = image_page or (next(iter(ref_pages)) if len(ref_pages) == 1 else None)
        if desired_page is not None and card.get("page") != desired_page:
            card["page"] = desired_page
            changed = True
        if image_page is not None:
            for block in visual_blocks:
                if block.get("page") != image_page:
                    block["page"] = image_page
                    changed = True
    return changed


def _page_from_visual_image_path(value: str) -> int | None:
    match = re.search(r"page-(\d{3,})", value)
    return int(match.group(1)) if match else None


def _is_visual_source_block(block: dict[str, Any]) -> bool:
    kind = str(block.get("source_kind") or block.get("type") or "").lower()
    return kind in {"caption", "figure", "table", "visual"}


def _source_ref_block_id(ref: str) -> str:
    match = re.search(r"\b[SCFTME]\d{3,}\b", str(ref))
    if match:
        return match.group(0)
    return str(ref).split()[0].split("/")[0]


def run_read_batch_harvest(
    root: str | Path,
    run_id: str,
    *,
    max_parallel: int | None = None,
    model: str | None = None,
    effort: str | None = None,
    runner_factory: Callable[[], Any] | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    return run_read_batch_draft_workers(
        root,
        run_id,
        max_parallel=max_parallel,
        model=model,
        effort=effort,
        runner_factory=runner_factory,
        progress=progress,
    )


def run_read_batch_draft_workers(
    root: str | Path,
    run_id: str,
    *,
    max_parallel: int | None = None,
    model: str | None = None,
    effort: str | None = None,
    repair_bibkeys: list[str] | None = None,
    repair_errors: list[str] | None = None,
    runner_factory: Callable[[], Any] | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    if not _valid_run_id(run_id):
        return {"ok": False, "error": "invalid read-batch run_id"}
    run_dir = paths.root / ".tmp" / "read_batch" / run_id
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return {"ok": False, "error": f"missing read-batch manifest: {manifest_path}"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    targets = [str(item) for item in manifest.get("targets") or [] if str(item).strip()]
    try:
        drafts_dir = _resolve_drafts_dir(paths.root, run_dir, str(manifest.get("drafts_dir") or ""))
        findings_dir = _resolve_findings_dir(paths.root, run_dir, str(manifest.get("findings_dir") or ""))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if not targets:
        return {"ok": False, "error": "read-batch manifest has no targets"}
    repair_set = {str(item).strip() for item in repair_bibkeys or [] if str(item).strip()}
    unknown_repair_targets = sorted(repair_set - set(targets))
    if unknown_repair_targets:
        return {"ok": False, "error": "repair target is not in read-batch manifest", "unknown_targets": unknown_repair_targets}
    active_targets = [bibkey for bibkey in targets if not repair_set or bibkey in repair_set]
    if not active_targets:
        return {"ok": False, "error": "no read-batch targets selected"}
    limit = max(
        1,
        min(
            int(max_parallel or manifest.get("max_parallel_subagents") or DEFAULT_READ_BATCH_PARALLEL_WORKERS),
            len(active_targets),
            MAX_READ_BATCH_PARALLEL_WORKERS,
        ),
    )
    runner_factory = runner_factory or (lambda: SubprocessCodexRunner(model=model, effort=effort, project_bin=_project_root() / "bin"))
    if progress:
        mode = "repair" if repair_set else "draft"
        progress(f"read-batch draft-workers: starting {len(active_targets)} {mode} target(s), max_parallel={limit}, run_id={run_id}")

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=limit) as executor:
        future_map = {
            executor.submit(
                _run_one_draft_worker,
                paths.root,
                run_id,
                drafts_dir,
                findings_dir,
                bibkey,
                runner_factory(),
                repair_errors=_repair_errors_for_bibkey(repair_errors or [], bibkey) if bibkey in repair_set else None,
            ): bibkey
            for bibkey in active_targets
        }
        pending = set(future_map)
        last_wait_progress = time.monotonic()
        while pending:
            done, pending = wait(pending, timeout=30.0, return_when=FIRST_COMPLETED)
            if not done:
                now = time.monotonic()
                if progress and now - last_wait_progress >= 60.0:
                    pending_bibkeys = sorted(future_map[future] for future in pending)
                    progress(
                        "read-batch draft-workers: waiting for "
                        f"{len(pending_bibkeys)} target(s): {', '.join(pending_bibkeys)}"
                    )
                    last_wait_progress = now
                continue
            last_wait_progress = time.monotonic()
            for future in done:
                bibkey = future_map[future]
                try:
                    item = future.result()
                    results.append(item)
                    if progress:
                        status = "ok" if item.get("ok") else "failed"
                        duration = item.get("duration_s")
                        suffix = f", duration_s={duration}" if duration is not None else ""
                        progress(f"read-batch draft-workers: {bibkey} {status}{suffix}")
                except Exception as exc:
                    results.append({"bibkey": bibkey, "ok": False, "error": str(exc)})
                    if progress:
                        progress(f"read-batch draft-workers: {bibkey} failed, error={exc}")

    validation_errors = _validate_required_worker_records(paths.root, manifest, findings_dir, targets)
    if progress:
        progress(
            "read-batch draft-workers: completed "
            f"{sum(1 for item in results if item.get('ok'))}/{len(targets)} target(s), "
            f"record_errors={len(validation_errors)}"
        )
    return {
        "ok": not validation_errors and all(item.get("ok") for item in results),
        "run_id": run_id,
        "targets": targets,
        "active_targets": active_targets,
        "repair_mode": bool(repair_set),
        "repair_errors": repair_errors or [],
        "drafts_dir": str(drafts_dir.relative_to(paths.root)),
        "findings_dir": str(findings_dir.relative_to(paths.root)),
        "max_parallel": limit,
        "paper_scale": {bibkey: _paper_scale(paths.root, bibkey) for bibkey in targets},
        "results": sorted(results, key=lambda item: str(item.get("bibkey") or "")),
        "errors": validation_errors,
        "artifact_state": _draft_artifact_state(paths.root, drafts_dir, findings_dir, targets),
    }


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


def _suggest_chunks(targets: list[str], chunk_size: int = MAX_READ_BATCH_TARGETS) -> list[list[str]]:
    return [targets[index:index + chunk_size] for index in range(0, len(targets), chunk_size)]


def _valid_run_id(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value)) and value not in {".", ".."}


def _resolve_drafts_dir(root: Path, run_dir: Path, raw_value: str) -> Path:
    if not raw_value:
        raise ValueError("read-batch manifest missing drafts_dir")
    candidate = (root / raw_value).resolve()
    expected = (run_dir / "drafts").resolve()
    if candidate != expected:
        raise ValueError("read-batch manifest drafts_dir is outside the expected run directory")
    return candidate


def _resolve_findings_dir(root: Path, run_dir: Path, raw_value: str) -> Path:
    if not raw_value:
        return run_dir / "findings"
    candidate = (root / raw_value).resolve()
    expected = (run_dir / "findings").resolve()
    if candidate != expected:
        raise ValueError("read-batch manifest findings_dir is outside the expected run directory")
    return candidate


def _missing_drafts(drafts_dir: Path, targets: list[str]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for bibkey in targets:
        missing_names = [name for name in READ_BATCH_ARTIFACTS if not (drafts_dir / bibkey / name).exists()]
        if missing_names:
            missing.append({"bibkey": bibkey, "missing": missing_names})
    return missing


def _draft_artifact_state(root: Path, drafts_dir: Path, findings_dir: Path, targets: list[str]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for bibkey in targets:
        draft_dir = drafts_dir / bibkey
        finding = findings_dir / bibkey / READ_BATCH_DRAFT_WORKER_NAME
        artifact_paths = {name: draft_dir / name for name in READ_BATCH_ARTIFACTS}
        artifact_paths[READ_BATCH_DRAFT_WORKER_NAME] = finding
        state[bibkey] = {
            name: {
                "exists": path.exists(),
                "bytes": path.stat().st_size if path.exists() else 0,
                "path": str(path.relative_to(root)) if path.exists() else str(path.relative_to(root)),
            }
            for name, path in artifact_paths.items()
        }
    return state


def _paper_scale(root: Path, bibkey: str) -> dict[str, Any]:
    paper_dir = root / "papers" / bibkey
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
    rendered_pages = len(list((paper_dir / "page_images").glob("page-*.png")))
    math_pages = len(list((paper_dir / "math_pages").glob("page-*.png")))
    return {
        "pdf_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
        "parsed_bytes": parsed_path.stat().st_size if parsed_path.exists() else 0,
        "paper_index_paragraphs": paragraphs,
        "paper_index_figures_tables": figures_tables,
        "paper_index_page_label_count": len(page_labels),
        "paper_index_max_page_label": max(page_labels) if page_labels else 0,
        "rendered_pages": rendered_pages,
        "math_pages": math_pages,
        "scale_basis": "rendered_pages plus paragraph/figure counts; paper_index page labels may collapse on parser defects",
    }


def _staging_hygiene_errors(run_dir: Path, drafts_dir: Path, findings_dir: Path, targets: list[str]) -> list[str]:
    allowed_files = {(run_dir / "manifest.json").resolve()}
    evidence_packs_dir = run_dir / "evidence_packs"
    allowed_dirs = {
        run_dir.resolve(),
        drafts_dir.resolve(),
        findings_dir.resolve(),
        evidence_packs_dir.resolve(),
        (run_dir / "originals").resolve(),
    }
    for bibkey in targets:
        draft_dir = (drafts_dir / bibkey).resolve()
        finding_dir = (findings_dir / bibkey).resolve()
        evidence_dir = (evidence_packs_dir / bibkey).resolve()
        allowed_dirs.add(draft_dir)
        allowed_dirs.add(finding_dir)
        allowed_dirs.add(evidence_dir)
        for name in READ_BATCH_ARTIFACTS:
            allowed_files.add((draft_dir / name).resolve())
        allowed_files.add((finding_dir / READ_BATCH_HARVEST_NAME).resolve())
        allowed_files.add((finding_dir / READ_BATCH_DRAFT_WORKER_NAME).resolve())
        allowed_files.add((evidence_dir / READ_BATCH_EVIDENCE_PACK_NAME).resolve())

    errors: list[str] = []
    suspicious_name_re = re.compile(r"(?:helper|generator|generate|draft_writer|writer|bulk|script)", re.IGNORECASE)
    suspicious_suffixes = {".py", ".sh", ".bash", ".ipynb", ".js", ".ts"}
    for path in sorted(run_dir.rglob("*")):
        resolved = path.resolve()
        if resolved in allowed_dirs or _is_under_originals(run_dir, resolved):
            continue
        if path.is_file() and resolved in allowed_files:
            continue
        relative = path.relative_to(run_dir)
        if path.is_file() and (path.suffix.lower() in suspicious_suffixes or suspicious_name_re.search(path.name)):
            errors.append(f"unsupported helper/generator file in read-batch staging: {relative}")
        elif path.is_file():
            errors.append(f"unsupported scratch file in read-batch staging: {relative}")
        elif path.is_dir():
            errors.append(f"unsupported directory in read-batch staging: {relative}")
    return errors


def _validate_required_worker_records(root: Path, manifest: dict[str, Any], findings_dir: Path, targets: list[str]) -> list[str]:
    if manifest.get("draft_worker_mode") != "parallel_required" and manifest.get("harvest_mode") != "parallel_required":
        return []
    errors: list[str] = []
    legacy_manifest = "draft_worker_mode" not in manifest
    for bibkey in targets:
        path = findings_dir / bibkey / READ_BATCH_DRAFT_WORKER_NAME
        legacy_path = findings_dir / bibkey / READ_BATCH_HARVEST_NAME
        legacy = False
        if not path.exists() and legacy_manifest and legacy_path.exists():
            path = legacy_path
            legacy = True
        if not path.exists():
            errors.append(f"{bibkey}: missing findings/{bibkey}/{READ_BATCH_DRAFT_WORKER_NAME}")
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{bibkey}: invalid worker JSON: {exc.msg}")
            continue
        if not legacy:
            record, warnings, changed = normalize_read_draft_worker_record_paths(record, topic_root=root, bibkey=bibkey)
            if changed:
                path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        if legacy:
            result = validate_read_harvest_finding(record, topic_root=root, bibkey=bibkey)
        else:
            result = validate_read_draft_worker_record(record, topic_root=root, bibkey=bibkey, run_id=str(manifest.get("run_id") or ""))
        if not result["ok"]:
            errors.extend(f"{bibkey}: {error}" for error in result["errors"])
    return errors


def _run_one_draft_worker(
    root: Path,
    run_id: str,
    drafts_dir: Path,
    findings_dir: Path,
    bibkey: str,
    runner: Any,
    *,
    repair_errors: list[str] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    job_dir = root / ".paper_engine" / "jobs" / f"{run_id}-{bibkey}-draft-worker"
    job_dir.mkdir(parents=True, exist_ok=True)
    event_log = job_dir / "events.jsonl"
    draft_dir = drafts_dir / bibkey
    draft_dir.mkdir(parents=True, exist_ok=True)
    output_path = findings_dir / bibkey / READ_BATCH_DRAFT_WORKER_NAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    required_outputs = [draft_dir / name for name in READ_BATCH_ARTIFACTS] + [output_path]
    if not repair_errors and all(path.exists() and path.stat().st_size > 0 for path in required_outputs):
        normalization_warnings: list[str] = []
        try:
            record = json.loads(output_path.read_text(encoding="utf-8"))
            record, normalization_warnings, changed = normalize_read_draft_worker_record_paths(record, topic_root=root, bibkey=bibkey)
            if changed:
                output_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
            validation = validate_read_draft_worker_record(record, topic_root=root, bibkey=bibkey, run_id=run_id)
        except json.JSONDecodeError as exc:
            validation = {"ok": False, "errors": [f"invalid draft worker JSON: {exc.msg}"], "warnings": []}
        if validation["ok"]:
            return {
                "bibkey": bibkey,
                "ok": True,
                "errors": [],
                "warnings": validation["warnings"],
                "events": 0,
                "duration_s": 0.0,
                "event_log": str(event_log.relative_to(root)),
                "reused_existing_draft": True,
                "warnings": [*validation.get("warnings", []), *normalization_warnings],
                "paper_scale": _paper_scale(root, bibkey),
            }
    evidence_pack_path = _write_evidence_pack(root, run_id, bibkey)
    prompt = _build_draft_worker_prompt(
        root,
        run_id,
        bibkey,
        draft_dir,
        output_path,
        evidence_pack_path=evidence_pack_path,
        repair_errors=repair_errors,
    )
    events: list[dict[str, Any]] = []
    event_iter = (
        runner.run_until_outputs(
            prompt,
            root,
            job_dir,
            required_outputs,
            stable_seconds=float(os.environ.get("PAPER_ENGINE_READ_BATCH_OUTPUT_STABLE_SECONDS", "5")),
            timeout_seconds=float(os.environ.get("PAPER_ENGINE_READ_BATCH_WORKER_TIMEOUT", str(DEFAULT_READ_BATCH_WORKER_TIMEOUT_SECONDS))),
            require_output_updates=bool(repair_errors),
        )
        if isinstance(runner, SubprocessCodexRunner)
        else runner.run(prompt, root, job_dir)
    )
    try:
        for event in event_iter:
            item = {"kind": getattr(event, "kind", "event"), "payload": getattr(event, "payload", {})}
            events.append(item)
            with event_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    except Exception as exc:
        duration = time.monotonic() - started
        return {
            "bibkey": bibkey,
            "ok": False,
            "error": str(exc),
            "events": len(events),
            "duration_s": round(duration, 3),
            "event_log": str(event_log.relative_to(root)),
            "artifact_state": _single_draft_artifact_state(root, draft_dir, output_path),
        }
    duration = time.monotonic() - started
    base_result = {
        "bibkey": bibkey,
        "events": len(events),
        "duration_s": round(duration, 3),
        "event_log": str(event_log.relative_to(root)),
        "artifact_state": _single_draft_artifact_state(root, draft_dir, output_path),
        "paper_scale": _paper_scale(root, bibkey),
    }
    missing = [name for name in READ_BATCH_ARTIFACTS if not (draft_dir / name).exists()]
    if missing:
        return {**base_result, "ok": False, "error": f"sidecar did not write required drafts: {', '.join(missing)}"}
    if not output_path.exists():
        return {**base_result, "ok": False, "error": f"sidecar did not write {output_path.relative_to(root)}"}
    try:
        record = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {**base_result, "ok": False, "error": f"invalid draft worker JSON: {exc.msg}"}
    record, normalization_warnings, changed = normalize_read_draft_worker_record_paths(record, topic_root=root, bibkey=bibkey)
    if changed:
        output_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    validation = validate_read_draft_worker_record(record, topic_root=root, bibkey=bibkey, run_id=run_id)
    return {
        **base_result,
        "ok": validation["ok"],
        "errors": validation["errors"],
        "warnings": [*validation["warnings"], *normalization_warnings],
    }


def _single_draft_artifact_state(root: Path, draft_dir: Path, output_path: Path) -> dict[str, Any]:
    paths = {name: draft_dir / name for name in READ_BATCH_ARTIFACTS}
    paths[READ_BATCH_DRAFT_WORKER_NAME] = output_path
    return {
        name: {
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
            "path": str(path.relative_to(root)),
        }
        for name, path in paths.items()
    }


def _write_evidence_pack(root: Path, run_id: str, bibkey: str) -> Path:
    paper_dir = root / "papers" / bibkey
    evidence_dir = root / ".tmp" / "read_batch" / run_id / "evidence_packs" / bibkey
    evidence_dir.mkdir(parents=True, exist_ok=True)
    output = evidence_dir / READ_BATCH_EVIDENCE_PACK_NAME

    metadata = _read_text_head(paper_dir / "metadata.yml", max_chars=5000)
    visual_index = _read_text_head(paper_dir / "visual_index.md", max_chars=5000)
    index = _load_json_object(paper_dir / "paper_index.json")
    math_index = _load_json_object(paper_dir / "math_index.json")
    formula_vision = _load_json_object(paper_dir / "formula_vision.json")
    paragraph_hits = _select_evidence_pack_paragraphs(index)
    figure_hits = _select_evidence_pack_figures(index)
    math_hits = _select_evidence_pack_math(math_index)
    availability_hits = _select_availability_hits(paragraph_hits)

    lines = [
        f"# Evidence Pack: {bibkey}",
        "",
        "This file is a navigation aid generated from paper-local evidence. Do not cite this file directly; cite the original paths and anchors shown here.",
        "",
        "## Paper Scale",
        "```json",
        json.dumps(_paper_scale(root, bibkey), ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Metadata Head",
        "```yaml",
        metadata or "(metadata.yml missing or empty)",
        "```",
        "",
        "## Selected Paragraphs",
    ]
    if paragraph_hits:
        for item in paragraph_hits:
            lines.extend(
                [
                    f"- {item['paragraph_id']} | page {item['page']} | {item['section_id']} | source: papers/{bibkey}/paper_index.json",
                    f"  {item['text']}",
                ]
            )
    else:
        lines.append("- No indexed paragraphs were available.")

    lines.extend(["", "## Figures And Tables"])
    if figure_hits:
        for item in figure_hits:
            paths = ", ".join(item.get("candidate_image_paths") or [])
            lines.extend(
                [
                    f"- {item['label']} | {item['kind']} | page {item['page']} | source: papers/{bibkey}/paper_index.json",
                    f"  caption: {item['caption']}",
                    f"  image_paths: {paths or '(none listed)'}",
                ]
            )
    else:
        lines.append("- No indexed figures or tables were available.")

    lines.extend(["", "## Math Cues"])
    if math_hits:
        for item in math_hits:
            lines.extend(
                [
                    f"- {item['id']} | page {item['page']} | confidence {item['confidence']} | source: papers/{bibkey}/math_index.json",
                    f"  {item['text']}",
                ]
            )
    else:
        lines.append("- No math_index equation candidates were available.")
    if formula_vision:
        lines.extend(
            [
                "",
                "## Formula Vision Status",
                "```json",
                json.dumps(_compact_formula_vision(formula_vision), ensure_ascii=False, indent=2, sort_keys=True),
                "```",
            ]
        )

    lines.extend(["", "## Availability Clues"])
    if availability_hits:
        for item in availability_hits:
            lines.extend(
                [
                    f"- {item['paragraph_id']} | page {item['page']} | source: papers/{bibkey}/paper_index.json",
                    f"  {item['text']}",
                ]
            )
    else:
        lines.append("- No strong code/data/repository availability clue was found in selected indexed paragraphs.")

    lines.extend(["", "## Visual Index Head", "```markdown", visual_index or "(visual_index.md missing or empty)", "```", ""])
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def _read_text_head(path: Path, *, max_chars: int) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    text = text[:max_chars]
    return text.rstrip()


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _select_evidence_pack_paragraphs(index: dict[str, Any]) -> list[dict[str, Any]]:
    paragraphs = [item for item in index.get("paragraphs") or [] if isinstance(item, dict)]
    if not paragraphs:
        return []
    keyword_re = re.compile(
        r"\b("
        r"abstract|contribution|we propose|we present|method|algorithm|pipeline|framework|"
        r"formulation|objective|theorem|proof|lemma|assumption|equation|shooting|collocation|"
        r"sqp|pmp|hjb|optimality|experiment|benchmark|dataset|result|table|figure|"
        r"ablation|limitation|future work|conclusion|code|data|github|zenodo|repository|available"
        r")\b",
        re.IGNORECASE,
    )
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(paragraph: dict[str, Any]) -> None:
        pid = str(paragraph.get("paragraph_id") or "").strip()
        text = _clean_pack_text(str(paragraph.get("text") or ""), max_chars=700)
        if not pid or not text or pid in seen:
            return
        seen.add(pid)
        selected.append(
            {
                "paragraph_id": pid,
                "section_id": str(paragraph.get("section_id") or ""),
                "page": _safe_int(paragraph.get("page")),
                "text": text,
            }
        )

    for paragraph in paragraphs[:10]:
        add(paragraph)
    for paragraph in paragraphs:
        if len(selected) >= 60:
            break
        text = str(paragraph.get("text") or "")
        if keyword_re.search(text):
            add(paragraph)
    for paragraph in paragraphs[-8:]:
        if len(selected) >= 60:
            break
        add(paragraph)
    return selected


def _select_evidence_pack_figures(index: dict[str, Any]) -> list[dict[str, Any]]:
    figures = [item for item in index.get("figures_tables") or [] if isinstance(item, dict)]
    selected: list[dict[str, Any]] = []
    for item in figures[:24]:
        selected.append(
            {
                "label": _clean_pack_text(str(item.get("label") or "Figure/Table"), max_chars=100),
                "kind": _clean_pack_text(str(item.get("kind") or ""), max_chars=80),
                "page": _safe_int(item.get("page")),
                "caption": _clean_pack_text(str(item.get("caption") or ""), max_chars=500),
                "candidate_image_paths": [str(path) for path in item.get("candidate_image_paths") or []][:4],
            }
        )
    return selected


def _select_evidence_pack_math(math_index: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [item for item in math_index.get("text_candidates") or [] if isinstance(item, dict)]
    selected: list[dict[str, Any]] = []
    for item in candidates[:16]:
        text = item.get("cleaned_equation") or item.get("raw_text") or item.get("label") or ""
        selected.append(
            {
                "id": str(item.get("id") or item.get("label") or "M"),
                "page": _safe_int(item.get("page")),
                "confidence": str(item.get("confidence") or "unknown"),
                "text": _clean_pack_text(str(text), max_chars=500),
            }
        )
    fallback = math_index.get("vision_fallback") if isinstance(math_index.get("vision_fallback"), dict) else {}
    if fallback:
        selected.append(
            {
                "id": "vision_fallback",
                "page": 0,
                "confidence": str(fallback.get("status") or "unknown"),
                "text": _clean_pack_text(json.dumps(fallback, ensure_ascii=False, sort_keys=True), max_chars=700),
            }
        )
    return selected


def _select_availability_hits(paragraph_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    availability_re = re.compile(r"\b(code|data|dataset|github|gitlab|zenodo|repository|available|availability|doi|url)\b", re.IGNORECASE)
    return [item for item in paragraph_hits if availability_re.search(item["text"])][:12]


def _compact_formula_vision(formula_vision: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in ["status", "reason", "error", "model", "created_at"]:
        if key in formula_vision:
            compact[key] = formula_vision[key]
    for key in ["results", "pages", "transcriptions"]:
        value = formula_vision.get(key)
        if isinstance(value, list):
            compact[key] = value[:5]
        elif value is not None:
            compact[key] = value
    return compact or formula_vision


def _clean_pack_text(text: str, *, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[: max_chars - 3].rstrip() + "..."
    return text


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _repair_errors_for_bibkey(repair_errors: list[str], bibkey: str) -> list[str]:
    """Keep repair prompts focused on the target paper.

    Finalize often returns one JSON object containing every failed paper in the
    batch. Passing that whole blob to every worker makes repair slower and lets
    the worker miss the target fields. This extracts only the messages that name
    the current bibkey, while preserving plain-text errors for single-paper
    repair calls.
    """
    targeted: list[str] = []
    for raw in repair_errors:
        text = str(raw or "").strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            embedded = _extract_embedded_repair_errors(text, bibkey)
            if embedded:
                targeted.extend(embedded)
            elif bibkey in text or len(repair_errors) == 1:
                targeted.append(text)
            continue
        extracted = _extract_repair_errors_from_payload(payload, bibkey)
        targeted.extend(extracted)
    return targeted or [str(item) for item in repair_errors if str(item).strip()]


def _extract_embedded_repair_errors(text: str, bibkey: str) -> list[str]:
    extracted: list[str] = []
    failed_payload = _json_object_after_marker(text, "details.failed_papers=")
    if isinstance(failed_payload, dict):
        target = failed_payload.get(bibkey)
        if isinstance(target, dict):
            extracted.extend(str(error).strip() for error in target.get("errors") or [] if str(error).strip())

    repeated_payload = _json_object_after_marker(text, "details.repeated_text=")
    if isinstance(repeated_payload, dict):
        extracted.extend(_extract_repair_errors_from_payload({"details": {"repeated_text": repeated_payload}}, bibkey))
    return extracted


def _json_object_after_marker(text: str, marker: str) -> dict[str, Any] | None:
    start = text.find(marker)
    if start < 0:
        return None
    object_start = text.find("{", start + len(marker))
    if object_start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(object_start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(text[object_start:index + 1])
                except json.JSONDecodeError:
                    return None
                return value if isinstance(value, dict) else None
    return None


def _extract_repair_errors_from_payload(payload: Any, bibkey: str) -> list[str]:
    if not isinstance(payload, dict):
        return []
    details = payload.get("details") if isinstance(payload.get("details"), dict) else payload
    extracted: list[str] = []

    failed = details.get("failed_papers") if isinstance(details.get("failed_papers"), dict) else {}
    target = failed.get(bibkey) if isinstance(failed, dict) else None
    if isinstance(target, dict):
        for error in target.get("errors") or []:
            if str(error).strip():
                extracted.append(str(error).strip())

    repeated = details.get("repeated_text") if isinstance(details.get("repeated_text"), dict) else {}
    for item in repeated.values() if isinstance(repeated, dict) else []:
        if not isinstance(item, dict):
            continue
        papers = {str(paper) for paper in item.get("papers") or []}
        if bibkey not in papers:
            continue
        paths = ", ".join(str(path) for path in item.get("paths") or [])
        text = str(item.get("text") or "").strip()
        if text:
            extracted.append(f"repeated_text for {bibkey}: {text}" + (f" | paths: {paths}" if paths else ""))
    return extracted


def _build_draft_worker_prompt(
    root: Path,
    run_id: str,
    bibkey: str,
    draft_dir: Path,
    output_path: Path,
    *,
    evidence_pack_path: Path | None = None,
    repair_errors: list[str] | None = None,
) -> str:
    rel_draft_dir = draft_dir.relative_to(root)
    rel_output = output_path.relative_to(root)
    rel_evidence_pack = (
        str(evidence_pack_path.relative_to(root))
        if evidence_pack_path is not None and evidence_pack_path.exists()
        else "not generated"
    )
    project_root = _project_root()
    scale = json.dumps(_paper_scale(root, bibkey), ensure_ascii=False, sort_keys=True)
    repair_block = ""
    if repair_errors:
        repair_block = f"""
Repair mode:
- This worker is repairing a staged draft that failed parent validation; it is not starting a new broad reread.
- The errors below are already filtered to `{bibkey}`. Ignore other papers unless a repeated-text error explicitly names this bibkey.
- Validation errors to fix:
{chr(10).join(f"  - {error}" for error in repair_errors)}
- You may read the current staged draft files under `{rel_draft_dir}` and the current provenance file `{rel_output}` as repair context only.
- Do not list staged draft files or `.tmp/read_batch/...` paths in `allowed_inputs`; provenance must still cite original paper-local evidence paths.
- Repair the failing fields and directly related translations/source refs, then rewrite the complete staged bundle and provenance file.
- If the error is a weak Chinese translation, repair the named field and scan sibling fields in the same subsection for the same English fallback pattern before rewriting.
- If the error is copied-source prose, rewrite the named field and any sibling field that repeats source-map wording rather than interpreting it.
- If the error is from `failed_papers`, `batch validate-report failed`, `batch quality-audit failed`, or `batch audit failed`, repair every listed field for `{bibkey}` instead of only the first visible message.
- If the error includes `repeated_text`, treat every repeated sentence listed for `{bibkey}` as forbidden. Rewrite all matching fields in this draft with concrete names from this paper.
- If the error says `visual_cards[...] page must match`, make `visual_cards[].page`, `image_path`, and any cited visual/caption/table/figure source-map block pages agree. Prefer the page number encoded in `page_images/page-###.png` when present.
- Do not broaden the draft, add unsupported sections, or run broad evidence searches during repair.
"""
    return f"""You are a paper_engine paper-reading draft worker for exactly one paper.

Topic root: {root}
Project root: {project_root}
Batch run_id: {run_id}
Target bibkey: {bibkey}
Paper scale summary: {scale}
Generated evidence pack: {rel_evidence_pack}
Required draft directory: {rel_draft_dir}
Required provenance output: {rel_output}
{repair_block}

Your job is to produce the full staged reading bundle for this paper:
- {rel_draft_dir}/source_map.json
- {rel_draft_dir}/note_plan.json
- {rel_draft_dir}/deep_read.json
- {rel_output}

Minimum required shape for {rel_draft_dir}/source_map.json:
{{
  "schema_version": "v3-source-map-2026-06",
  "paper": {{
    "bibkey": "{bibkey}",
    "title": "...",
    "source_type": "pdf",
    "pdf_path": "papers/{bibkey}/paper.pdf",
    "parsed_markdown_path": "papers/{bibkey}/parsed.md"
  }},
  "blocks": [
    {{
      "id": "S001",
      "page": 1,
      "section": "Abstract",
      "section_id": "sec:001",
      "paragraph_ids": ["p:0001"],
      "type": "paragraph",
      "source_kind": "body_text",
      "source_text": "short evidence text actually used by deep_read.json",
      "confidence": "high",
      "notes": ""
    }}
  ]
}}

Do not invent another source-map schema. Do not use top-level `run_id`, `bibkey`, `title`, `source_refs`, `coverage`, or `figures_and_tables_used` in source_map.json. Put evidence blocks only in top-level `blocks`, and cite those block IDs from deep_read.json as `source_refs`.

If availability includes a URL, says an external lookup/search/check was performed, or says an external lookup/search/check could not be performed, add an `E###` block to source_map.json:
{{
  "id": "E001",
  "page": 0,
  "section": "External availability",
  "section_id": "external_availability",
  "paragraph_ids": [],
  "type": "external",
  "source_kind": "external",
  "source_text": "External availability lookup result or blocker for this paper",
  "confidence": "medium",
  "notes": "URL: <opened URL or unavailable>; accessed: YYYY-MM-DD; query or lookup: <exact query/path>"
}}
Then cite that block from `availability.code.source_refs`, `availability.data.source_refs`, or `availability.models.source_refs` as appropriate. If you only use local paper text for availability and do not claim any external lookup or URL, do not mention external lookup/search/check in `availability.*.evidence` or `availability.*.notes`.

Minimum required contract for {rel_draft_dir}/deep_read.json:
- Read `{project_root}/schemas/deep_read_report.schema.json` before writing deep_read.json. This schema file is allowed contract context, not paper evidence.
- If you need workflow wording, read `{project_root}/templates/skills/paper_deep_read/references/output-contract.md`. Do not search for `skills/` or `schemas/` under the topic root; topic repositories are not required to contain project contracts.
- Use the current schema top-level fields: `schema_version`, `bibkey`, `title`, `authors`, `year`, `venue`, `pdf_path`, `parsed_markdown_path`, `source_map_path`, `one_sentence_summary`, `paper_profile`, `argument_map`, `quick_read`, `central_claims`, `method_understanding`, `evaluation`, `visual_cards`, `availability`, `extraction_notes`, and `translations`.
- Add optional type sections only when active lenses need them: `theory_understanding`, `dataset_benchmark_understanding`, `survey_understanding`, `application_understanding`, or `system_understanding`.
- Do not invent another deep-read schema. Do not use top-level fields like `paper`, `reader_facing`, `problem_setting`, `method_map`, `worked_examples`, `theory_and_algorithms`, `limitations_and_caveats`, `executive_summary`, `key_contributions`, `taxonomy`, `core_reading`, `sections`, or `bottom_line`.
- Every `source_refs` value in deep_read.json must point to an ID in source_map.json top-level `blocks`.
- `evaluation.numeric_results[]` must contain only the fields allowed by the schema: `dataset_or_task`, `metric`, `value`, `unit`, `baseline`, `comparison`, `higher_is_better`, `source_refs`, `interpretation`, and `what_it_does_not_prove`. Do not add `confidence`, `notes`, or extra keys there.
- `translations.zh.quick_read` must be a list of plain Chinese strings, not objects with `text`, `source_refs`, or `confidence`.

Read only this paper's evidence files under papers/{bibkey}/:
- metadata.yml
- paper.pdf only if needed for targeted visual/formula checks
- parsed.md
- paper_index.json
- math_index.json
- formula_vision.json when present
- visual_index.md
- page_images/*
- math_pages/*

Before running broad searches, read the generated evidence pack at `{rel_evidence_pack}` if it exists.
The evidence pack is a code-generated navigation aid built from approved paper-local evidence; it is not a cited source.
Use the paragraph IDs, figure/table cues, math cues, availability clues, and page-image counts in the pack to choose source-map blocks quickly.
Prefer the evidence pack plus at most a few targeted follow-up reads over open-ended `rg`/`sed` exploration.
Do not list `.tmp/read_batch/.../evidence_pack.md` in `allowed_inputs`; cite the original paper-local files and anchors named inside the pack.

Forbidden inputs:
- papers/{bibkey}/source_map.json
- papers/{bibkey}/note_plan.json
- papers/{bibkey}/deep_read.json
- papers/{bibkey}/note.md
- papers/{bibkey}/note_zh.md
- papers/{bibkey}/reading_result.html
- any sibling topic, any other papers/<other-bibkey>/ directory, and previous session logs.

Do not write final paper artifacts under papers/{bibkey}/. Write only the staged draft directory and {rel_output}.

Draft quality requirements:
- Hard budget: write the required draft bundle promptly. Do not spend the whole turn exploring; if enough evidence exists for a concrete paper-specific card, write the JSON artifacts.
- The generated evidence pack is designed to be sufficient for the first draft in normal cases. Read it first, then use at most three targeted follow-up commands for missing anchors, one external availability check, or one visual/formula check.
- Do not assume `jq` is installed. If you need to query JSON, use Python 3 or targeted `rg`/`sed` reads instead of wasting a command on `jq`.
- If the paper is long, prefer a complete evidence-pack-grounded draft over exhaustive section coverage. The parent finalizer/auditor will report concrete repairs if needed.
- Write `source_map.json`, `note_plan.json`, `deep_read.json`, and `{rel_output}` as one complete write phase. Do not leave only `source_map.json` or `note_plan.json` written while continuing exploration.
- Treat the worker as a bounded production job, not a literature-review conversation. Once you have metadata, 6-10 strong evidence blocks, core method/theory/evaluation/limitation evidence, and any local availability clue, write the bundle instead of searching for exhaustive coverage.
- Prefer local paper-visible availability evidence. Perform at most one external availability check, and only when the paper gives a DOI, arXiv URL, repository URL, Zenodo DOI, or explicit code/data clue. If no reliable external check is possible within the bounded job, record a concrete blocker in an E### source block and finish the draft.
- Keep the number of shell commands small. If you have read the evidence pack and run three targeted follow-up commands, stop gathering and write the draft with the evidence already collected.
- Do not repeat broad keyword sweeps already covered by the evidence pack. Use extra commands only for a specific missing field or to verify one cited source anchor.
- Use targeted evidence reads only. Do not dump full parsed.md, do not use `cat parsed.md`, and do not use sed ranges longer than 80 lines. Prefer paper_index paragraph IDs, `rg -n -m`, math_index, and selected page/visual evidence.
- Keep command output small. Do not print long paragraph ranges, large JSON snippets, or more than about 80 evidence lines total. Read evidence into files or variables silently, then write the staged JSON files.
- Do not read `source_map.schema.json` or `note_plan.schema.json`; the source-map shape is supplied above and note_plan should follow the output contract. Read only `deep_read_report.schema.json` and the output contract if needed.
- After the three draft JSON files are syntactically written, immediately write {rel_output}. Do not run `paper_engine read ... --validate-report`, `--quality-audit`, `--rebuild-note`, or `read-batch --finalize`; the parent batch finalizer owns validation and repair.
- Write `{rel_output}` only after a final self-review of the staged `deep_read.json`: every displayed English field has a Chinese counterpart where the contract requires one, Chinese paragraphs are real Chinese prose with only proper nouns left in English, visual-card pages agree with their cited visual/caption source blocks, and repeated generic sentences have been replaced with paper-specific anchors.
- Do not keep working after {rel_output} is written. Stop with a concise summary so the batch runner can detect completion and terminate this worker.
- Do not inspect project implementation source such as `src/paper_engine/*.py`, renderer code, validator code, or test files to predict hidden checks. If a schema detail is unclear, make the best contract-shaped draft and let the parent finalizer report the concrete validation error.
- Interpret the paper; do not copy schema prompts or workflow instructions into reader-facing fields.
- Every reader-facing claim must be paper-specific, concrete, and grounded in source refs.
- Before writing reader-facing fields, identify at least six paper anchors from this paper's title, abstract, evidence pack, figures, equations, datasets, solvers, benchmarks, or code/data clues. Anchors are concrete names such as a method name, theorem/equation family, benchmark, dataset, simulator, solver, figure/table subject, ablation name, repository, or domain application. Every one-sentence summary, quick-read item, central claim, argument-map item, method pipeline item, algorithm step, implementation detail, numeric result, and visual-card label/note should include at least one such anchor or an equally concrete paper-specific noun phrase. If a sentence would fit another paper in the same topic after replacing the title, rewrite it.
- Do not copy `source_map.blocks[].source_text` into reader-facing fields. `source_text` is evidence, while `argument_map.*.text`, `quick_read[].text`, `central_claims[].evidence_summary`, `method_understanding.*.text`, and `evaluation.*.text` must explain what that evidence means in your own words.
- `availability.code.evidence`, `availability.data.evidence`, and `availability.models.evidence` must interpret the availability check for the reader. Do not paste the `E###` source block text or HTTP/search result verbatim; say whether code/data/models appear available, where, and what caveat matters.
- Every `quick_read[].text` item must name a concrete paper-specific method, theorem, example, equation family, dataset, solver, benchmark, code artifact, or limitation. Do not write generic quick-read items such as "the paper is useful for understanding optimal control" or "check the assumptions before transfer."
- `argument_map.decisive_evidence[].text` must synthesize why the cited evidence is decisive. It must not be the same sentence as the cited source block.
- Avoid generic reusable sentences. Do not write a sentence whose main content is "this paper has a method/result/limitation"; name the actual method, theorem, objective, solver, dataset, metric, figure, repository, or caveat from this paper.
- Do not write batch-scaffold or workflow sentences. The reader-facing result must not mention rereading, validation, selected evidence blocks, batch runs, source-map IDs, prompt rules, or the worker process.
- Do not fill `method_understanding.algorithm_steps` with a generic three-step template. Each step must name the paper's actual operator, sampler, posterior, proof object, benchmark, theorem, dataset, or solver. If the paper is a survey or theory paper without an algorithm, steps should describe the paper-specific analytical or organizing workflow, not a fake algorithm.
- Chinese translations in deep_read.json must cover all reader-facing sections with actual Chinese prose, not English copied after Chinese labels.
- Chinese fields may keep proper nouns such as `DPS`, `D-Flow`, `ImageNet`, `D4RL`, or theorem names, but the surrounding phrase must be Chinese. Write "`DPS` 基线" or "`D-Flow` 采样规则", not "DPS baseline" or another mostly-English fallback.
- Do not mark `self_review.chinese_complete` true until you have checked `translations.zh` for the exact failure modes reported by the parent: missing list entries, mostly-English paragraphs, copied English captions, and untranslated nested fields.
- `translations.zh` must mirror structured English fields, not only section-level summaries. If you write `method_understanding.algorithm_steps`, translate every step object's `action`, `inputs`, and `outputs` in `translations.zh.method_understanding.algorithm_steps` with the same list length. If you write `evaluation.numeric_results`, translate every result object's `dataset_or_task`, `metric`, `interpretation`, and `what_it_does_not_prove` in `translations.zh.evaluation.numeric_results`. If you write `theory_understanding`, translate `assumptions`, `key_results`, `engineering_proof_sketch`, every `key_equations[].label/explanation`, and every `theorem_or_principle_chain[].principle/role/intuition` under `translations.zh.type_sections.theory_understanding`. If you write `survey_understanding`, translate `timeline_milestones` and every `method_family_matrix[].family/core_idea/strengths/limitations/best_for` under `translations.zh.type_sections.survey_understanding`.
- If `algorithm_pseudocode` is present and longer than one short sentence, format it as multiline pseudocode with newline characters. Do not write a long single-line numbered list.
- If math or visuals are degraded by parsing, record the concrete blocker and still summarize the paper-specific readable theory/method content.
- If this is a survey, include paper-specific taxonomy/timeline/method-family content when evidence supports it.
- For `survey_understanding.method_family_matrix`, include only method families with enough evidence to name a concrete mechanism, strength, limitation, and best use case. Do not add low-confidence filler rows that say the paper merely mentions a family, that more reading is needed, or that evidence is insufficient; put those in `coverage_gaps` or omit them.
- Every survey matrix `limitations` field, including its Chinese translation, must name a concrete limitation from the paper evidence: examples include initialization sensitivity, curse of dimensionality, state/path-constraint handling, local minima, discretization size, parser/visual limitation, or missing benchmark coverage. Do not write generic phrases such as "evidence is insufficient for detailed comparison."

First inspect the project-root paper_deep_read schema/output contract if needed. Then write the three draft JSON files in {rel_draft_dir}. Finally write {rel_output} with this exact shape.

Provenance constraints for {rel_output}:
- `allowed_inputs` must list only approved paper-local evidence paths under `papers/{bibkey}/`, such as `papers/{bibkey}/metadata.yml`, `papers/{bibkey}/paper_index.json`, `papers/{bibkey}/parsed.md`, `papers/{bibkey}/math_index.json`, `papers/{bibkey}/formula_vision.json`, `papers/{bibkey}/visual_index.md`, `papers/{bibkey}/page_images/...`, or `papers/{bibkey}/math_pages/...`.
- Do not put `AGENTS.md`, `policy.yml`, `topic.yml`, `preferences.yml`, `.tmp/read_batch/...`, project README, schemas, skills, source code, or tests in `allowed_inputs`; those are workflow context, not paper evidence.
- Every `evidence_items[]` entry must include a paper-local `source_path` plus at least one real source anchor: non-empty `paragraph_ids`, `section_id`, positive PDF `page`, `source_text`, `source_refs`, or a verified URL. Do not use `page: 0`.

Use this JSON shape:
{{
  "schema_version": "{READ_DRAFT_WORKER_SCHEMA_VERSION}",
  "role": "{READ_DRAFT_WORKER_ROLE}",
  "run_id": "{run_id}",
  "bibkey": "{bibkey}",
  "producer": {{"mode": "codex_sidecar_draft_worker"}},
  "forbidden_inputs_checked": true,
  "allowed_inputs": ["papers/{bibkey}/metadata.yml", "papers/{bibkey}/paper_index.json"],
  "forbidden_inputs": [],
  "writes_final_artifacts": false,
  "final_artifacts_written": [],
  "draft_artifacts_written": [
    "{rel_draft_dir}/source_map.json",
    "{rel_draft_dir}/note_plan.json",
    "{rel_draft_dir}/deep_read.json"
  ],
  "evidence_items": [
    {{
      "kind": "method|theory|experiment|visual|availability|limitation",
      "claim": "paper-specific evidence claim in your own words",
      "source_path": "papers/{bibkey}/paper_index.json",
      "paragraph_ids": ["p:0001"],
      "page": 1,
      "confidence": "high"
    }}
  ],
  "self_review": {{
    "paper_specific": true,
    "no_template_reuse": true,
    "chinese_complete": true,
    "old_artifacts_unused": true
  }},
  "notes": []
}}
"""


def _run_one_harvest(root: Path, run_id: str, findings_dir: Path, bibkey: str, runner: Any) -> dict[str, Any]:
    job_dir = root / ".paper_engine" / "jobs" / f"{run_id}-{bibkey}-harvest"
    job_dir.mkdir(parents=True, exist_ok=True)
    output_path = findings_dir / bibkey / READ_BATCH_HARVEST_NAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = _build_harvest_prompt(root, bibkey, output_path)
    events: list[dict[str, Any]] = []
    for event in runner.run(prompt, root, job_dir):
        events.append({"kind": getattr(event, "kind", "event"), "payload": getattr(event, "payload", {})})
    if not output_path.exists():
        return {"bibkey": bibkey, "ok": False, "error": f"sidecar did not write {output_path.relative_to(root)}", "events": len(events)}
    try:
        record = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"bibkey": bibkey, "ok": False, "error": f"invalid harvest JSON: {exc.msg}", "events": len(events)}
    validation = validate_read_harvest_finding(record, topic_root=root, bibkey=bibkey)
    return {"bibkey": bibkey, "ok": validation["ok"], "errors": validation["errors"], "warnings": validation["warnings"], "events": len(events)}


def _build_harvest_prompt(root: Path, bibkey: str, output_path: Path) -> str:
    rel_output = output_path.relative_to(root)
    return f"""You are a read-only paper_engine evidence-harvest sidecar for one paper.

Topic root: {root}
Target bibkey: {bibkey}
Required output: {rel_output}

Read only this paper's evidence files under papers/{bibkey}/:
- metadata.yml
- paper.pdf only if needed for evidence
- parsed.md
- paper_index.json
- math_index.json
- formula_vision.json when present
- visual_index.md
- page_images/*
- math_pages/*

Forbidden inputs:
- papers/{bibkey}/source_map.json
- papers/{bibkey}/note_plan.json
- papers/{bibkey}/deep_read.json
- papers/{bibkey}/note.md
- papers/{bibkey}/note_zh.md
- papers/{bibkey}/reading_result.html
- any sibling topic, any other papers/<other-bibkey>/ directory, and previous session logs.

Do not write final reading artifacts. Write only {rel_output}. Use JSON with this shape:
{{
  "schema_version": "v3-read-harvest-2026-07",
  "role": "paper_evidence_harvest",
  "bibkey": "{bibkey}",
  "producer": {{"mode": "codex_sidecar"}},
  "forbidden_inputs_checked": true,
  "allowed_inputs": ["papers/{bibkey}/metadata.yml"],
  "forbidden_inputs": [],
  "writes_final_artifacts": false,
  "final_artifacts_written": [],
  "evidence_items": [
    {{
      "kind": "method|theory|experiment|visual|availability|limitation",
      "claim": "paper-specific evidence claim in your own words",
      "source_path": "papers/{bibkey}/paper_index.json",
      "paragraph_ids": ["p:0001"],
      "page": 1,
      "confidence": "high"
    }}
  ],
  "critical_facts": {{
    "method": [],
    "theory": [],
    "experiments": [],
    "visuals": [],
    "availability": [],
    "limitations": []
  }},
  "notes": []
}}

Harvest evidence only. Do not draft source_map.json, note_plan.json, or deep_read.json.
"""


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_under_originals(run_dir: Path, resolved: Path) -> bool:
    originals = (run_dir / "originals").resolve()
    return resolved == originals or originals in resolved.parents


def _no_op_drafts(paths: TopicPaths, drafts_dir: Path, targets: list[str]) -> list[str]:
    noops: list[str] = []
    for bibkey in targets:
        paper_dir = paths.paper_dir(bibkey)
        if all(_same_file_bytes(drafts_dir / bibkey / name, paper_dir / name) for name in READ_BATCH_ARTIFACTS):
            noops.append(bibkey)
    return noops


def _same_file_bytes(left: Path, right: Path) -> bool:
    return left.exists() and right.exists() and left.read_bytes() == right.read_bytes()


def _snapshot_originals(paths: TopicPaths, targets: list[str], originals_dir: Path) -> None:
    if originals_dir.exists():
        shutil.rmtree(originals_dir)
    for bibkey in targets:
        source_dir = paths.paper_dir(bibkey)
        target_dir = originals_dir / bibkey
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in READ_BATCH_GENERATED_ARTIFACTS:
            source = source_dir / name
            if source.exists():
                shutil.copy2(source, target_dir / name)


def _restore_originals(paths: TopicPaths, targets: list[str], originals_dir: Path) -> None:
    for bibkey in targets:
        paper_dir = paths.paper_dir(bibkey)
        original_dir = originals_dir / bibkey
        for name in READ_BATCH_GENERATED_ARTIFACTS:
            destination = paper_dir / name
            original = original_dir / name
            if original.exists():
                shutil.copy2(original, destination)
            elif destination.exists():
                destination.unlink()


class _ReadBatchError(Exception):
    def __init__(self, message: str, bibkey: str | None, details: dict[str, Any]):
        super().__init__(message)
        self.message = message
        self.bibkey = bibkey
        self.details = details
