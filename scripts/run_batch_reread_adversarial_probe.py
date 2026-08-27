#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from paper_engine.read import audit_reading_library, parse_pdf
from paper_engine.read_batch import finalize_read_batch, prepare_read_batch
from paper_engine.sidecars import READ_DRAFT_WORKER_SCHEMA_VERSION
from paper_engine.topic import init_topic


def _fixture(name: str) -> Path:
    return ROOT / "tests" / "fixtures" / name


def _load_json(name: str) -> dict[str, Any]:
    return json.loads(_fixture(name).read_text(encoding="utf-8"))


def _paper(root: Path, bibkey: str) -> Path:
    paper_dir = root / "papers" / bibkey
    paper_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_fixture("example.pdf"), paper_dir / "paper.pdf")
    parse_pdf(root, bibkey)
    return paper_dir


def _write_final_bundle(root: Path, bibkey: str) -> None:
    paper_dir = _paper(root, bibkey)
    data = _load_json("deep_read_report.json")
    source_map = _load_json("source_map.json")
    note_plan = _load_json("note_plan.json")
    paper_index = _load_json("paper_index.json")
    data["bibkey"] = bibkey
    source_map["paper"]["bibkey"] = bibkey
    for name, payload in [
        ("paper_index.json", paper_index),
        ("source_map.json", source_map),
        ("note_plan.json", note_plan),
        ("deep_read.json", data),
    ]:
        (paper_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_draft(root: Path, run_id: str, bibkey: str, data: dict[str, Any]) -> None:
    draft_dir = root / ".tmp" / "read_batch" / run_id / "drafts" / bibkey
    draft_dir.mkdir(parents=True, exist_ok=True)
    source_map = _load_json("source_map.json")
    note_plan = _load_json("note_plan.json")
    data["bibkey"] = bibkey
    source_map["paper"]["bibkey"] = bibkey
    for name, payload in [
        ("source_map.json", source_map),
        ("note_plan.json", note_plan),
        ("deep_read.json", data),
    ]:
        (draft_dir / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_draft_worker(root: Path, run_id: str, bibkey: str) -> None:
    finding_dir = root / ".tmp" / "read_batch" / run_id / "findings" / bibkey
    finding_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": READ_DRAFT_WORKER_SCHEMA_VERSION,
        "role": "paper_read_draft_worker",
        "run_id": run_id,
        "bibkey": bibkey,
        "producer": {"mode": "adversarial_probe"},
        "forbidden_inputs_checked": True,
        "allowed_inputs": [f"papers/{bibkey}/metadata.yml", f"papers/{bibkey}/paper_index.json"],
        "forbidden_inputs": [],
        "writes_final_artifacts": False,
        "final_artifacts_written": [],
        "draft_artifacts_written": [
            f".tmp/read_batch/{run_id}/drafts/{bibkey}/source_map.json",
            f".tmp/read_batch/{run_id}/drafts/{bibkey}/note_plan.json",
            f".tmp/read_batch/{run_id}/drafts/{bibkey}/deep_read.json",
        ],
        "evidence_items": [
            {
                "kind": "method",
                "claim": f"{bibkey} draft worker references paper-local evidence before drafting.",
                "source_path": f"papers/{bibkey}/paper_index.json",
                "paragraph_ids": ["p:0001"],
                "page": 1,
                "confidence": "high",
            }
        ],
        "self_review": {
            "paper_specific": True,
            "no_template_reuse": True,
            "chinese_complete": True,
            "old_artifacts_unused": True,
        },
    }
    (finding_dir / "draft_worker.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")


def _check(name: str, ok: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "ok": ok, "details": details or {}}


def _all_error_text(value: Any) -> str:
    parts: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "errors" and isinstance(item, list):
                parts.extend(str(error) for error in item)
            else:
                parts.append(_all_error_text(item))
    elif isinstance(value, list):
        for item in value:
            parts.append(_all_error_text(item))
    elif isinstance(value, str):
        parts.append(value)
    return "\n".join(part for part in parts if part)


def check_template_draft_rejected(work_dir: Path) -> dict[str, Any]:
    root = work_dir / "template_draft"
    init_topic(root, "Batch Template Probe", "Reject prompt-shaped paper reading cards")
    bibkey = "Bodmer2026Grounding"
    _write_final_bundle(root, bibkey)
    original = (root / "papers" / bibkey / "deep_read.json").read_text(encoding="utf-8")
    prepare_read_batch(root, bibkeys=[bibkey], force_reread=True, run_id="template")
    data = _load_json("deep_read_report.json")
    data["one_sentence_summary"] = (
        "Grounding Generative Policies in Physics is reread as an application contribution with "
        "conclusions tied to selected motivation, method, result, and limitation evidence."
    )
    data["quick_read"][0]["text"] = (
        "Define the target task as the paper-specific objective and judge the result through experiments, "
        "benchmark comparisons, derivations, or survey evidence."
    )
    _write_draft(root, "template", bibkey, data)
    result = finalize_read_batch(root, "template")
    restored = (root / "papers" / bibkey / "deep_read.json").read_text(encoding="utf-8") == original
    return _check(
        "template_draft_rejected",
        (not result["ok"]) and restored,
        {"result": result, "restored": restored},
    )


def check_oversized_batch_rejected(work_dir: Path) -> dict[str, Any]:
    root = work_dir / "oversized_batch"
    init_topic(root, "Batch Size Probe", "Reject oversized read-batch jobs")
    bibkeys = [f"Probe2026{i}" for i in range(6)]
    result = prepare_read_batch(root, bibkeys=bibkeys, force_reread=True, run_id="too_big")
    return _check(
        "oversized_batch_rejected",
        (not result["ok"]) and result.get("max_targets") == 5 and len(result.get("suggested_chunks") or []) == 2,
        {"result": result},
    )


def check_staging_helper_rejected(work_dir: Path) -> dict[str, Any]:
    root = work_dir / "staging_helper"
    init_topic(root, "Batch Helper Probe", "Reject helper scripts in staging")
    bibkey = "Alpha2024A"
    _write_final_bundle(root, bibkey)
    prepare_read_batch(root, bibkeys=[bibkey], force_reread=True, run_id="helper")
    data = _load_json("deep_read_report.json")
    data["quick_read"][0]["text"] = "Use this fixture to verify schema, source refs, Markdown, HTML rendering, and helper rejection behavior."
    _write_draft(root, "helper", bibkey, data)
    helper = root / ".tmp" / "read_batch" / "helper" / "deterministic_draft_generator.py"
    helper.write_text("print('generic schema-valid drafts')\n", encoding="utf-8")
    result = finalize_read_batch(root, "helper")
    return _check(
        "staging_helper_rejected",
        (not result["ok"]) and "unsupported helper" in result.get("error", ""),
        {"result": result},
    )


def check_generator_workflow_leakage_rejected(work_dir: Path) -> dict[str, Any]:
    root = work_dir / "generator_leakage"
    init_topic(root, "Batch Generator Leak Probe", "Reject bulk generator workflow text")
    bibkey = "Beta2024B"
    _write_final_bundle(root, bibkey)
    prepare_read_batch(root, bibkeys=[bibkey], force_reread=True, run_id="leak")
    data = _load_json("deep_read_report.json")
    data["one_sentence_summary"] = (
        "A deterministic draft writer built schema-valid drafts from parsed/index-only evidence before read-batch staging finalized the result."
    )
    data["quick_read"][0]["text"] = (
        "The staging helper creates a generic bulk draft generator output rather than a paper-specific interpretation."
    )
    _write_draft(root, "leak", bibkey, data)
    result = finalize_read_batch(root, "leak")
    errors = _all_error_text(result.get("details", {}))
    return _check(
        "generator_workflow_leakage_rejected",
        (not result["ok"]) and "internal prompt text leaked" in errors,
        {"result": result},
    )


def check_repeated_library_cards_rejected(work_dir: Path) -> dict[str, Any]:
    root = work_dir / "repeated_cards"
    init_topic(root, "Batch Repeated Probe", "Reject cross-paper repeated reading cards")
    bibkeys = ["Alpha2024A", "Beta2024B"]
    for bibkey in bibkeys:
        _write_final_bundle(root, bibkey)
    prepare_read_batch(root, bibkeys=bibkeys, force_reread=True, run_id="repeat")
    repeated = (
        "The method links shooting intervals through boundary matching and uses the resulting nonlinear "
        "equations to guide the solver under the stated control assumptions."
    )
    for bibkey in bibkeys:
        data = _load_json("deep_read_report.json")
        data["one_sentence_summary"] = repeated
        _write_draft(root, "repeat", bibkey, data)
        _write_draft_worker(root, "repeat", bibkey)
    result = finalize_read_batch(root, "repeat")
    errors = "\n".join(result.get("details", {}).get("errors", []))
    return _check(
        "repeated_library_cards_rejected",
        (not result["ok"]) and "repeated reader-facing text blocks" in errors,
        {"result": result},
    )


def check_missing_parallel_draft_worker_blocks_finalize(work_dir: Path) -> dict[str, Any]:
    root = work_dir / "missing_parallel_draft_worker"
    init_topic(root, "Batch Draft Worker Probe", "Reject multi-paper finalize without draft-worker provenance")
    bibkeys = ["Alpha2024A", "Beta2024B"]
    for bibkey in bibkeys:
        _write_final_bundle(root, bibkey)
    prepare_read_batch(root, bibkeys=bibkeys, force_reread=True, run_id="workers")
    for bibkey in bibkeys:
        data = _load_json("deep_read_report.json")
        data["quick_read"][0]["text"] = f"{bibkey} draft is present but draft-worker provenance is intentionally missing."
        _write_draft(root, "workers", bibkey, data)
    result = finalize_read_batch(root, "workers")
    return _check(
        "missing_parallel_draft_worker_blocks_finalize",
        (not result["ok"]) and result.get("error") == "missing or invalid read-batch draft-worker records",
        {"result": result},
    )


def check_dirty_library_chunk_commit_allowed(work_dir: Path) -> dict[str, Any]:
    root = work_dir / "dirty_library_chunk"
    init_topic(root, "Dirty Library Chunk Probe", "Allow chunk commits while stale readings remain")
    target = "Alpha2024A"
    stale = "Stale2024Bad"
    _write_final_bundle(root, target)
    _write_final_bundle(root, stale)
    stale_path = root / "papers" / stale / "deep_read.json"
    stale_data = json.loads(stale_path.read_text(encoding="utf-8"))
    stale_data["quick_read"][0]["text"] = (
        "This reread uses selected evidence and an evidence block instead of a finished reader-facing interpretation."
    )
    stale_path.write_text(json.dumps(stale_data, indent=2, ensure_ascii=False), encoding="utf-8")
    prepare_read_batch(root, bibkeys=[target], force_reread=True, run_id="dirty")
    data = _load_json("deep_read_report.json")
    data["quick_read"][0]["text"] = (
        "The probe target receives a fresh paper-specific card while an unrelated stale paper remains to be fixed later."
    )
    _write_draft(root, "dirty", target, data)
    result = finalize_read_batch(root, "dirty")
    library_result = audit_reading_library(root)
    return _check(
        "dirty_library_chunk_commit_allowed",
        result.get("ok") is True and library_result.get("ok") is False and stale in library_result.get("failed_papers", {}),
        {"result": result, "library_result": library_result},
    )


def check_missing_draft_blocks_finalize(work_dir: Path) -> dict[str, Any]:
    root = work_dir / "missing_draft"
    init_topic(root, "Batch Missing Probe", "Reject incomplete batch drafts")
    bibkey = "Alpha2024A"
    _write_final_bundle(root, bibkey)
    prepare_read_batch(root, bibkeys=[bibkey], force_reread=True, run_id="missing")
    result = finalize_read_batch(root, "missing")
    return _check(
        "missing_draft_blocks_finalize",
        (not result["ok"]) and result.get("error") == "missing draft artifacts",
        {"result": result},
    )


def run_probe(*, keep_work_dir: bool = False) -> dict[str, Any]:
    work_dir = Path(tempfile.mkdtemp(prefix="paper-engine-batch-reread-adversarial-"))
    checks = [
        check_template_draft_rejected(work_dir),
        check_oversized_batch_rejected(work_dir),
        check_staging_helper_rejected(work_dir),
        check_generator_workflow_leakage_rejected(work_dir),
        check_repeated_library_cards_rejected(work_dir),
        check_missing_parallel_draft_worker_blocks_finalize(work_dir),
        check_dirty_library_chunk_commit_allowed(work_dir),
        check_missing_draft_blocks_finalize(work_dir),
    ]
    result = {"ok": all(item["ok"] for item in checks), "work_dir": str(work_dir), "checks": checks}
    if not keep_work_dir:
        shutil.rmtree(work_dir, ignore_errors=True)
        result["cleanup"] = {"removed": True}
    else:
        result["cleanup"] = {"removed": False}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic adversarial probes for batch reread quality gates.")
    parser.add_argument("--keep-work-dir", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run_probe(keep_work_dir=args.keep_work_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"ok={result['ok']} work_dir={result['work_dir']}")
        for check in result["checks"]:
            print(f"- {check['name']}: {'PASS' if check['ok'] else 'FAIL'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
