from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


ALLOWED_TEMP_PREFIXES = (
    "paper-engine-sidecar-",
    "paper-engine-subagent-adversarial-",
)
SCORE_CONFIDENCE = {"low", "medium", "high"}
READ_HARVEST_SCHEMA_VERSION = "v3-read-harvest-2026-07"
READ_HARVEST_ROLE = "paper_evidence_harvest"
READ_DRAFT_WORKER_SCHEMA_VERSION = "v3-read-draft-worker-2026-07"
READ_DRAFT_WORKER_ROLE = "paper_read_draft_worker"
READ_HARVEST_FINAL_ARTIFACTS = {
    "source_map.json",
    "note_plan.json",
    "deep_read.json",
    "note.md",
    "note_zh.md",
    "reading_result.html",
}
READ_HARVEST_ALLOWED_PREFIXES = {
    "metadata.yml",
    "paper.pdf",
    "parsed.md",
    "paper_index.json",
    "math_index.json",
    "formula_vision.json",
    "visual_index.md",
}
READ_HARVEST_ALLOWED_DIR_PREFIXES = (
    "page_images/",
    "math_pages/",
)


@dataclass(frozen=True)
class CleanupReport:
    path: str
    removed: bool
    kept: bool
    errors: tuple[str, ...] = ()


@dataclass
class SidecarTempWorkspace:
    root: Path
    keep: bool = False
    cleanup_errors: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        prefix: str = "paper-engine-sidecar-",
        keep: bool = False,
        base_dir: Path | None = None,
    ) -> "SidecarTempWorkspace":
        if not any(prefix.startswith(allowed) for allowed in ALLOWED_TEMP_PREFIXES):
            raise ValueError(f"unsafe sidecar temp prefix: {prefix}")
        root = Path(tempfile.mkdtemp(prefix=prefix, dir=base_dir))
        return cls(root=root.resolve(), keep=keep)

    def cleanup(self) -> CleanupReport:
        root = self.root.resolve()
        if self.keep:
            return CleanupReport(path=str(root), removed=False, kept=True)
        if not is_safe_sidecar_temp_path(root):
            error = f"refusing to remove non-sidecar temp path: {root}"
            self.cleanup_errors.append(error)
            return CleanupReport(path=str(root), removed=False, kept=False, errors=(error,))
        try:
            shutil.rmtree(root)
        except FileNotFoundError:
            return CleanupReport(path=str(root), removed=True, kept=False)
        except OSError as exc:
            error = str(exc)
            self.cleanup_errors.append(error)
            return CleanupReport(path=str(root), removed=False, kept=False, errors=(error,))
        return CleanupReport(path=str(root), removed=True, kept=False)

    def __enter__(self) -> "SidecarTempWorkspace":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()


def is_safe_sidecar_temp_path(path: Path) -> bool:
    resolved = path.resolve()
    tmp_root = Path(tempfile.gettempdir()).resolve()
    if resolved == tmp_root or tmp_root not in resolved.parents:
        return False
    return any(resolved.name.startswith(prefix) for prefix in ALLOWED_TEMP_PREFIXES)


def split_shards(items: Iterable[Any], shard_count: int) -> list[list[Any]]:
    if shard_count < 1:
        raise ValueError("shard_count must be >= 1")
    shards: list[list[Any]] = [[] for _ in range(shard_count)]
    for index, item in enumerate(items):
        shards[index % shard_count].append(item)
    return shards


def merge_score_shards(shard_paths: Iterable[Path], output_path: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_identities: set[str] = set()

    for shard_path in shard_paths:
        path = Path(shard_path)
        if not path.exists():
            errors.append(f"{path}: missing shard")
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path}:{line_number}: invalid JSON: {exc.msg}")
                continue
            record_errors = validate_score_record(record)
            if record_errors:
                errors.extend(f"{path}:{line_number}: {error}" for error in record_errors)
                continue
            identity = score_record_identity(record)
            if identity in seen_identities:
                errors.append(f"{path}:{line_number}: duplicate score identity {identity}")
                continue
            seen_identities.add(identity)
            records.append(record)

    if errors:
        return {"ok": False, "errors": errors, "records": 0, "written": False}

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return {"ok": True, "errors": [], "records": len(records), "written": True, "output": str(output_path)}


def score_record_identity(record: dict[str, Any]) -> str:
    record_id = str(record.get("record_id") or "").strip()
    candidate_id = str(record.get("candidate_id") or "").strip()
    if record_id:
        return f"record:{record_id}"
    return f"candidate:{candidate_id}"


def validate_score_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["score record must be an object"]
    candidate_id = str(record.get("candidate_id") or "").strip()
    if not candidate_id:
        errors.append("missing candidate_id")
    if "score" not in record:
        errors.append("missing score")
    elif not _is_number_in_range(record["score"], -1.0, 1.0):
        errors.append("score must be a number in [-1, 1]")
    for field in ("content", "preference", "credibility"):
        if field in record and not _is_number_in_range(record[field], -1.0, 1.0):
            errors.append(f"{field} must be a number in [-1, 1]")
    confidence = record.get("score_confidence")
    if confidence is not None and confidence not in SCORE_CONFIDENCE:
        errors.append("score_confidence must be low, medium, or high")
    if "reasons" in record and not isinstance(record["reasons"], list):
        errors.append("reasons must be a list when present")
    return errors


def _is_number_in_range(value: Any, low: float, high: float) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return low <= float(value) <= high


def validate_read_harvest_finding(record: dict[str, Any], *, topic_root: Path, bibkey: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(record, dict):
        return {"ok": False, "errors": ["read harvest finding must be an object"], "warnings": []}

    if record.get("schema_version") != READ_HARVEST_SCHEMA_VERSION:
        errors.append(f"schema_version must be {READ_HARVEST_SCHEMA_VERSION}")
    if str(record.get("role") or "") != READ_HARVEST_ROLE:
        errors.append(f"role must be {READ_HARVEST_ROLE}")
    if str(record.get("bibkey") or "") != bibkey:
        errors.append(f"bibkey mismatch: expected {bibkey}")
    if record.get("forbidden_inputs_checked") is not True:
        errors.append("forbidden_inputs_checked must be true")
    if record.get("writes_final_artifacts") is True:
        errors.append("harvest sidecar must not write final paper artifacts")
    final_written = record.get("final_artifacts_written") or []
    if final_written:
        errors.append("final_artifacts_written must be empty")

    producer = record.get("producer") or {}
    if not isinstance(producer, dict):
        errors.append("producer must be an object")
    else:
        mode = str(producer.get("mode") or "").strip()
        if not mode:
            errors.append("producer.mode is required")

    for field in ("allowed_inputs", "forbidden_inputs"):
        value = record.get(field, [])
        if value is not None and not isinstance(value, list):
            errors.append(f"{field} must be a list")

    for path_value in record.get("allowed_inputs") or []:
        path_error = _validate_harvest_input_path(str(path_value), topic_root=topic_root, bibkey=bibkey)
        if path_error:
            errors.append(path_error)

    for path_value in record.get("forbidden_inputs") or []:
        if _is_forbidden_reading_artifact(str(path_value)):
            errors.append(f"forbidden reading artifact was used as evidence: {path_value}")

    evidence_items = record.get("evidence_items")
    if not isinstance(evidence_items, list) or not evidence_items:
        errors.append("evidence_items must be a non-empty list")
    else:
        for index, item in enumerate(evidence_items):
            errors.extend(_validate_harvest_evidence_item(item, index, topic_root=topic_root, bibkey=bibkey))

    critical_facts = record.get("critical_facts")
    if not isinstance(critical_facts, dict):
        errors.append("critical_facts must be an object")
    else:
        if not any(critical_facts.get(key) for key in ("method", "theory", "experiments", "visuals", "availability", "limitations")):
            warnings.append("critical_facts is present but empty")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_read_draft_worker_record(
    record: dict[str, Any],
    *,
    topic_root: Path,
    bibkey: str,
    run_id: str,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(record, dict):
        return {"ok": False, "errors": ["read draft worker record must be an object"], "warnings": []}

    if record.get("schema_version") != READ_DRAFT_WORKER_SCHEMA_VERSION:
        errors.append(f"schema_version must be {READ_DRAFT_WORKER_SCHEMA_VERSION}")
    if str(record.get("role") or "") != READ_DRAFT_WORKER_ROLE:
        errors.append(f"role must be {READ_DRAFT_WORKER_ROLE}")
    if str(record.get("bibkey") or "") != bibkey:
        errors.append(f"bibkey mismatch: expected {bibkey}")
    if str(record.get("run_id") or "") != run_id:
        errors.append(f"run_id mismatch: expected {run_id}")
    if record.get("forbidden_inputs_checked") is not True:
        errors.append("forbidden_inputs_checked must be true")
    if record.get("writes_final_artifacts") is True:
        errors.append("draft worker must not write final paper artifacts")
    final_written = record.get("final_artifacts_written") or []
    if final_written:
        errors.append("final_artifacts_written must be empty")

    producer = record.get("producer") or {}
    if not isinstance(producer, dict):
        errors.append("producer must be an object")
    elif not str(producer.get("mode") or "").strip():
        errors.append("producer.mode is required")

    for path_value in record.get("allowed_inputs") or []:
        path_error = _validate_harvest_input_path(str(path_value), topic_root=topic_root, bibkey=bibkey)
        if path_error:
            errors.append(path_error)

    for path_value in record.get("forbidden_inputs") or []:
        if _is_forbidden_reading_artifact(str(path_value)):
            errors.append(f"forbidden reading artifact was used as evidence: {path_value}")

    drafts_written = record.get("draft_artifacts_written")
    expected = {
        f".tmp/read_batch/{run_id}/drafts/{bibkey}/source_map.json",
        f".tmp/read_batch/{run_id}/drafts/{bibkey}/note_plan.json",
        f".tmp/read_batch/{run_id}/drafts/{bibkey}/deep_read.json",
    }
    if not isinstance(drafts_written, list):
        errors.append("draft_artifacts_written must be a list")
    else:
        actual = {str(item) for item in drafts_written}
        missing = sorted(expected - actual)
        extra = sorted(item for item in actual if item not in expected)
        if missing:
            errors.append(f"draft_artifacts_written missing required drafts: {', '.join(missing)}")
        if extra:
            errors.append(f"draft_artifacts_written contains unsupported paths: {', '.join(extra)}")

    evidence_items = record.get("evidence_items")
    if not isinstance(evidence_items, list) or not evidence_items:
        errors.append("evidence_items must be a non-empty list")
    else:
        for index, item in enumerate(evidence_items):
            errors.extend(_validate_harvest_evidence_item(item, index, topic_root=topic_root, bibkey=bibkey))

    if not isinstance(record.get("self_review"), dict):
        errors.append("self_review must be an object")
    else:
        review = record["self_review"]
        for field in ("paper_specific", "no_template_reuse", "chinese_complete", "old_artifacts_unused"):
            if review.get(field) is not True:
                errors.append(f"self_review.{field} must be true")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def normalize_read_draft_worker_record_paths(
    record: dict[str, Any],
    *,
    topic_root: Path,
    bibkey: str,
) -> tuple[dict[str, Any], list[str], bool]:
    """Repair obvious paper-local evidence path typos without weakening safety.

    Codex workers sometimes mistype the bibkey segment in provenance paths while
    still referring to an approved file that exists under the target paper. This
    normalization fixes only that narrow case. Old reading artifacts, sibling
    paper paths that actually exist, absolute escapes, and unsupported files are
    still left for the validator to reject.
    """
    if not isinstance(record, dict):
        return record, [], False
    warnings: list[str] = []
    changed = False

    allowed_inputs = record.get("allowed_inputs")
    if isinstance(allowed_inputs, list):
        normalized_inputs: list[Any] = []
        for value in allowed_inputs:
            fixed, warning = _canonicalize_target_paper_path(value, topic_root=topic_root, bibkey=bibkey)
            normalized_inputs.append(fixed)
            if warning:
                warnings.append(f"normalized allowed_inputs path: {warning}")
                changed = True
            elif fixed != value:
                changed = True
        record["allowed_inputs"] = normalized_inputs

    evidence_items = record.get("evidence_items")
    if isinstance(evidence_items, list):
        for index, item in enumerate(evidence_items):
            if not isinstance(item, dict) or "source_path" not in item:
                continue
            original = item.get("source_path")
            fixed, warning = _canonicalize_target_paper_path(original, topic_root=topic_root, bibkey=bibkey)
            if fixed != original:
                item["source_path"] = fixed
                changed = True
            if warning:
                warnings.append(f"normalized evidence_items[{index}].source_path: {warning}")

    if warnings:
        notes = record.get("notes")
        if not isinstance(notes, list):
            notes = []
        for warning in warnings:
            if warning not in notes:
                notes.append(warning)
        record["notes"] = notes
        changed = True
    return record, warnings, changed


def _canonicalize_target_paper_path(value: Any, *, topic_root: Path, bibkey: str) -> tuple[Any, str | None]:
    if not isinstance(value, str):
        return value, None
    stripped = value.strip()
    if not stripped or stripped.startswith(("http://", "https://")):
        return value, None
    path = Path(stripped)
    root = Path(topic_root).resolve()
    try:
        relative = path.resolve().relative_to(root) if path.is_absolute() else path
    except ValueError:
        return value, None
    parts = relative.parts
    if len(parts) < 3 or parts[0] != "papers" or parts[1] == bibkey:
        return value, None
    paper_relative = "/".join(parts[2:])
    if _is_forbidden_reading_artifact(paper_relative):
        return value, None
    if paper_relative not in READ_HARVEST_ALLOWED_PREFIXES and not any(
        paper_relative.startswith(prefix) for prefix in READ_HARVEST_ALLOWED_DIR_PREFIXES
    ):
        return value, None
    wrong_target = root / relative
    correct_relative = Path("papers") / bibkey / paper_relative
    correct_target = root / correct_relative
    if correct_target.exists() and not wrong_target.exists():
        fixed = correct_relative.as_posix()
        return fixed, f"{stripped} -> {fixed}"
    return value, None


def merge_read_harvest_findings(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    evidence_items: list[dict[str, Any]] = []
    critical_facts: dict[str, list[Any]] = {}
    conflicts: list[dict[str, Any]] = []
    fact_values: dict[str, Any] = {}

    for record in records:
        for item in record.get("evidence_items") or []:
            evidence_items.append(item)
        for group, values in (record.get("critical_facts") or {}).items():
            if values is None:
                continue
            value_list = values if isinstance(values, list) else [values]
            critical_facts.setdefault(group, [])
            for value in value_list:
                identity = _critical_fact_identity(group, value)
                if identity:
                    existing = fact_values.get(identity)
                    if existing is not None and existing != value:
                        conflicts.append({"identity": identity, "left": existing, "right": value})
                    fact_values[identity] = value
                if value not in critical_facts[group]:
                    critical_facts[group].append(value)

    return {
        "ok": not conflicts,
        "evidence_items": evidence_items,
        "critical_facts": critical_facts,
        "conflicts": conflicts,
    }


def extract_critical_facts(deep_read: dict[str, Any]) -> dict[str, list[Any]]:
    facts: dict[str, list[Any]] = {
        "method": [],
        "theory": [],
        "experiments": [],
        "visuals": [],
        "availability": [],
        "limitations": [],
        "numeric": [],
    }
    method = deep_read.get("method_understanding") or {}
    for key in ("pipeline", "algorithm_steps", "implementation_details"):
        facts["method"].extend(_as_list(method.get(key)))
    theory = deep_read.get("theory_understanding") or {}
    for key in ("key_equations", "theorem_or_principle_chain", "engineering_proof_sketch"):
        facts["theory"].extend(_as_list(theory.get(key)))
    evaluation = deep_read.get("evaluation") or {}
    for key in ("tasks", "baselines", "metrics", "main_results", "limitations"):
        target = "limitations" if key == "limitations" else "experiments"
        facts[target].extend(_as_list(evaluation.get(key)))
    facts["numeric"].extend(_as_list(deep_read.get("numeric_results")))
    facts["visuals"].extend(_as_list(deep_read.get("visual_cards")))
    availability = deep_read.get("availability") or {}
    for key in ("code", "data", "models"):
        facts["availability"].extend(_as_list(availability.get(key)))
    facts["limitations"].extend(_as_list(deep_read.get("limitations")))
    return {key: value for key, value in facts.items() if value}


def compare_reading_equivalence(sequential: dict[str, Any], parallel: dict[str, Any]) -> dict[str, Any]:
    left = extract_critical_facts(sequential)
    right = extract_critical_facts(parallel)
    missing: list[dict[str, Any]] = []
    for group, items in left.items():
        right_text = "\n".join(_fact_text(item).lower() for item in right.get(group, []))
        for item in items:
            text = _fact_text(item)
            if not text.strip():
                continue
            anchors = _equivalence_anchors(text)
            if anchors and not any(anchor in right_text for anchor in anchors):
                missing.append({"group": group, "fact": text[:240]})
    return {"ok": not missing, "missing": missing, "left_groups": sorted(left), "right_groups": sorted(right)}


def _validate_harvest_input_path(path_value: str, *, topic_root: Path, bibkey: str) -> str | None:
    value = path_value.strip()
    if not value:
        return "empty allowed input path"
    if value.startswith(("http://", "https://")):
        return None
    if ".." in Path(value).parts:
        return f"harvest input path must not contain '..': {value}"
    root = Path(topic_root).resolve()
    candidate = Path(value)
    if candidate.is_absolute():
        try:
            relative = candidate.resolve().relative_to(root)
        except ValueError:
            return f"harvest input path is outside topic root: {value}"
    else:
        relative = candidate
    parts = relative.parts
    if len(parts) < 3 or parts[0] != "papers" or parts[1] != bibkey:
        return f"harvest input path must stay inside papers/{bibkey}: {value}"
    paper_relative = "/".join(parts[2:])
    if _is_forbidden_reading_artifact(paper_relative):
        return f"harvest input path references old reading artifact: {value}"
    if paper_relative in READ_HARVEST_ALLOWED_PREFIXES:
        return None
    if any(paper_relative.startswith(prefix) for prefix in READ_HARVEST_ALLOWED_DIR_PREFIXES):
        return None
    return f"harvest input path is not an approved paper evidence path: {value}"


def _validate_harvest_evidence_item(item: Any, index: int, *, topic_root: Path, bibkey: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"evidence_items[{index}] must be an object"]
    for field in ("kind", "claim", "source_path"):
        if not str(item.get(field) or "").strip():
            errors.append(f"evidence_items[{index}] missing {field}")
    path_error = _validate_harvest_input_path(str(item.get("source_path") or ""), topic_root=topic_root, bibkey=bibkey)
    if path_error:
        errors.append(f"evidence_items[{index}]: {path_error}")
    has_anchor = any(
        item.get(field)
        for field in ("source_refs", "paragraph_ids", "section_id", "page", "url", "source_text")
    )
    if not has_anchor:
        errors.append(f"evidence_items[{index}] lacks a source anchor")
    confidence = item.get("confidence")
    if confidence is not None and confidence not in SCORE_CONFIDENCE:
        errors.append(f"evidence_items[{index}].confidence must be low, medium, or high")
    return errors


def _is_forbidden_reading_artifact(path_value: str) -> bool:
    return Path(path_value).name in READ_HARVEST_FINAL_ARTIFACTS


def _critical_fact_identity(group: str, value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    fact_id = value.get("id") or value.get("label") or value.get("name") or value.get("title")
    if not fact_id:
        return None
    return f"{group}:{fact_id}"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _fact_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts: list[str] = []
        for key in ("text", "claim", "result", "finding", "summary", "label", "metric", "value", "action", "notes", "status", "url"):
            if value.get(key):
                parts.append(str(value[key]))
        return " ".join(parts)
    return str(value)


def _equivalence_anchors(text: str) -> list[str]:
    words = [word.lower() for word in text.replace("/", " ").replace("-", " ").split()]
    anchors = [word for word in words if len(word) >= 7][:4]
    numbers = [word.lower() for word in words if any(char.isdigit() for char in word)]
    return numbers[:4] + anchors
