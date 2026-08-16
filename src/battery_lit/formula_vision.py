from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Protocol

from .codex_paths import codex_env, resolve_codex_bin
from .paths import TopicPaths
from .schemas import validate_with_schema

FORMULA_VISION_NAME = "formula_vision.json"
MATH_INDEX_NAME = "math_index.json"
SOURCE_MAP_NAME = "source_map.json"
FORMULA_VISION_SCHEMA_VERSION = "v3-formula-vision-2026-06"
COMPLETED_STATUSES = {"completed", "completed_no_formula"}
TERMINAL_STATUSES = COMPLETED_STATUSES | {"blocked", "exhausted"}


class FormulaVisionError(RuntimeError):
    pass


class FormulaVisionRunner(Protocol):
    def run(self, prompt: str, cwd: Path, images: list[Path]) -> str:
        ...


class SubprocessFormulaVisionRunner:
    def __init__(self, codex_bin: str | None = None, model: str | None = None, effort: str | None = None) -> None:
        self.codex_bin = resolve_codex_bin(codex_bin)
        self.model = model or os.environ.get("BATTERY_LIT_CODEX_MODEL")
        self.effort = effort or os.environ.get("BATTERY_LIT_CODEX_EFFORT") or "medium"

    def command(self, cwd: Path, images: list[Path]) -> list[str]:
        command = [
            self.codex_bin,
            "exec",
            "--json",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "-C",
            str(cwd),
        ]
        for image in images:
            command.extend(["--image", str(image)])
        if self.model:
            command.extend(["--model", self.model])
        if self.effort:
            command.extend(["-c", f'model_reasoning_effort="{self.effort}"'])
        command.append("-")
        return command

    def run(self, prompt: str, cwd: Path, images: list[Path]) -> str:
        proc = subprocess.Popen(
            self.command(cwd, images),
            cwd=str(cwd),
            env=codex_env(None),
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert proc.stdin is not None
        proc.stdin.write(prompt)
        proc.stdin.close()
        assert proc.stdout is not None
        text_parts: list[str] = []
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                text_parts.append(line)
                continue
            text = _payload_text(payload)
            if text:
                text_parts.append(text)
        return_code = proc.wait()
        if return_code != 0:
            raise FormulaVisionError(f"codex image transcription failed with exit code {return_code}")
        return "\n".join(text_parts).strip()


def transcribe_formulas(
    root: str | Path,
    bibkey: str,
    runner: FormulaVisionRunner | None = None,
    *,
    batch_size: int = 3,
) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    paper_dir = paths.paper_dir(bibkey)
    math_index_path = paper_dir / MATH_INDEX_NAME
    if not math_index_path.exists():
        return {"ok": False, "errors": [f"missing {MATH_INDEX_NAME} for {bibkey}; run `battery_lit read {bibkey} --parse-only` first"]}
    try:
        math_index = json.loads(math_index_path.read_text(encoding="utf-8"))
        validate_with_schema(math_index, "math_index.schema.json")
    except Exception as exc:
        return {"ok": False, "errors": [f"{MATH_INDEX_NAME}: {exc}"]}

    fallback = math_index.get("vision_fallback") if isinstance(math_index.get("vision_fallback"), dict) else {}
    image_paths = [str(item) for item in fallback.get("image_paths") or math_index.get("math_page_images") or []]
    existing_status = str(fallback.get("status") or "").strip().lower()
    if existing_status in COMPLETED_STATUSES and (paper_dir / FORMULA_VISION_NAME).exists():
        return {"ok": True, "status": "skipped_existing", "formula_vision": str((paper_dir / FORMULA_VISION_NAME).relative_to(paths.root))}
    if not image_paths:
        result = _write_blocked(paths.root, paper_dir, math_index, "blocked", ["no math page images available"])
        return {"ok": True, **result}

    images: list[Path] = []
    missing: list[str] = []
    for rel in image_paths:
        path = paths.root / rel
        if path.exists():
            images.append(path)
        else:
            missing.append(rel)
    if not images:
        result = _write_blocked(paths.root, paper_dir, math_index, "blocked", [f"math page images are missing: {', '.join(missing)}"])
        return {"ok": True, **result}

    runner = runner or SubprocessFormulaVisionRunner()
    equations: list[dict[str, Any]] = []
    errors: list[str] = []
    for batch in _chunks(images, max(1, batch_size)):
        try:
            raw = runner.run(_prompt_for_batch(paths.root, bibkey, batch), paths.root, batch)
            payload = _extract_json_object(raw)
            equations.extend(_normalize_equations(payload.get("equations") or [], paths.root, batch))
        except Exception as exc:
            errors.append(str(exc))

    status = "completed" if equations else "completed_no_formula" if not errors else "blocked"
    if status == "blocked":
        reasons = [f"formula vision failed: {'; '.join(errors)}"]
    elif status == "completed_no_formula":
        reasons = ["Codex image transcription completed but no visible key equations were returned"]
    else:
        reasons = []
    output = {
        "schema_version": FORMULA_VISION_SCHEMA_VERSION,
        "bibkey": bibkey,
        "backend": "codex_cli_image_input",
        "status": status,
        "image_inputs": [str(path.relative_to(paths.root)) for path in images],
        "equations": equations,
        "errors": errors,
    }
    validate_with_schema(output, "formula_vision.schema.json")
    (paper_dir / FORMULA_VISION_NAME).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    _update_math_index(math_index_path, math_index, status, reasons)
    merged = _merge_formula_vision_into_source_map(paths.root, paper_dir, output)
    return {
        "ok": True,
        "status": status,
        "formula_vision": str((paper_dir / FORMULA_VISION_NAME).relative_to(paths.root)),
        "equations": len(equations),
        "source_map_merged": merged,
        "errors": errors,
    }


def _write_blocked(root: Path, paper_dir: Path, math_index: dict[str, Any], status: str, reasons: list[str]) -> dict[str, Any]:
    output = {
        "schema_version": FORMULA_VISION_SCHEMA_VERSION,
        "bibkey": paper_dir.name,
        "backend": "codex_cli_image_input",
        "status": status,
        "image_inputs": [],
        "equations": [],
        "errors": reasons,
    }
    validate_with_schema(output, "formula_vision.schema.json")
    (paper_dir / FORMULA_VISION_NAME).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    _update_math_index(paper_dir / MATH_INDEX_NAME, math_index, status, reasons)
    return {"status": status, "formula_vision": str((paper_dir / FORMULA_VISION_NAME).relative_to(root)), "equations": 0, "source_map_merged": False, "errors": reasons}


def _prompt_for_batch(root: Path, bibkey: str, images: list[Path]) -> str:
    rels = [str(path.relative_to(root)) for path in images]
    return (
        "You are a bounded formula-vision transcriber for battery_lit.\n"
        f"Paper bibkey: {bibkey}\n"
        f"Attached page images: {', '.join(rels)}\n"
        "Task: inspect only the attached images and transcribe important visible mathematical formulas that a reader would need for the paper's theory/method understanding.\n"
        "Do not summarize the paper. Do not infer equations from memory. Do not invent notation. If uncertain, lower confidence.\n"
        "Return exactly one JSON object and no markdown, with this shape:\n"
        '{"equations":[{"page":1,"label":"short name","latex":"LaTeX formula","plain_text":"readable formula","meaning":"one sentence meaning","variables":["x: state"],"confidence":"high|medium|low","region_note":"where on the page"}]}\n'
        "If there are no useful visible equations, return {\"equations\":[]}."
    )


def _normalize_equations(items: Any, root: Path, images: list[Path]) -> list[dict[str, Any]]:
    image_by_page = {_page_from_image(path): path for path in images if _page_from_image(path) is not None}
    normalized: list[dict[str, Any]] = []
    for raw in items if isinstance(items, list) else []:
        if not isinstance(raw, dict):
            continue
        latex = str(raw.get("latex") or "").strip()
        plain = str(raw.get("plain_text") or raw.get("equation") or "").strip()
        if not latex and not plain:
            continue
        page = _coerce_page(raw.get("page")) or next(iter(image_by_page), 1)
        image_path = image_by_page.get(page) or images[0]
        confidence = str(raw.get("confidence") or "medium").strip().lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        normalized.append(
            {
                "id": f"M{len(normalized) + 1:03d}",
                "page": page,
                "image_path": str(image_path.relative_to(root)),
                "label": str(raw.get("label") or f"Equation {len(normalized) + 1}").strip(),
                "latex": latex,
                "plain_text": plain or latex,
                "meaning": str(raw.get("meaning") or "").strip(),
                "variables": [str(item).strip() for item in raw.get("variables") or [] if str(item).strip()],
                "confidence": confidence,
                "region_note": str(raw.get("region_note") or "").strip(),
            }
        )
    return normalized


def _merge_formula_vision_into_source_map(root: Path, paper_dir: Path, formula_vision: dict[str, Any]) -> bool:
    source_map_path = paper_dir / SOURCE_MAP_NAME
    if not source_map_path.exists():
        return False
    source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
    blocks = source_map.get("blocks") if isinstance(source_map.get("blocks"), list) else []
    existing_keys = {(str(item.get("image_path") or ""), str(item.get("latex") or "")) for item in blocks if isinstance(item, dict)}
    next_index = _next_m_index(blocks)
    section = _fallback_section(blocks)
    changed = False
    for equation in formula_vision.get("equations") or []:
        key = (str(equation.get("image_path") or ""), str(equation.get("latex") or ""))
        if key in existing_keys:
            continue
        block = {
            "id": f"M{next_index:03d}",
            "page": int(equation.get("page") or 1),
            "section": section["section"],
            "section_id": section["section_id"],
            "paragraph_ids": [],
            "type": "equation",
            "source_kind": "equation",
            "source_text": str(equation.get("plain_text") or equation.get("latex") or ""),
            "latex": str(equation.get("latex") or ""),
            "image_path": str(equation.get("image_path") or ""),
            "backend": "codex_cli_image_input",
            "confidence": str(equation.get("confidence") or "medium"),
            "notes": str(equation.get("meaning") or ""),
        }
        blocks.append(block)
        existing_keys.add(key)
        next_index += 1
        changed = True
    if changed:
        validate_with_schema(source_map, "source_map.schema.json")
        source_map_path.write_text(json.dumps(source_map, indent=2, ensure_ascii=False), encoding="utf-8")
    return changed


def _update_math_index(path: Path, math_index: dict[str, Any], status: str, reasons: list[str]) -> None:
    fallback = math_index.setdefault("vision_fallback", {})
    fallback["status"] = status
    existing = [str(item) for item in fallback.get("reasons") or []]
    fallback["reasons"] = existing + [item for item in reasons if item and item not in existing]
    validate_with_schema(math_index, "math_index.schema.json")
    path.write_text(json.dumps(math_index, indent=2, ensure_ascii=False), encoding="utf-8")


def _payload_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        parts: list[str] = []
        for key in ["message", "text", "content", "delta", "output_text"]:
            value = payload.get(key)
            if isinstance(value, str):
                parts.append(value)
            elif isinstance(value, list):
                parts.extend(_payload_text(item) for item in value)
        if payload.get("type") in {"message", "agent_message", "assistant_message"}:
            parts.append(_payload_text(payload.get("payload")))
        return "\n".join(part for part in parts if part)
    if isinstance(payload, list):
        return "\n".join(_payload_text(item) for item in payload)
    return ""


def _extract_json_object(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        raise FormulaVisionError("empty Codex formula transcription")
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise FormulaVisionError("Codex formula transcription did not contain JSON")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise FormulaVisionError("Codex formula transcription JSON is not an object")
    return payload


def _chunks(items: list[Path], size: int) -> list[list[Path]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _page_from_image(path: Path) -> int | None:
    match = re.search(r"page-(\d+)", path.name)
    return int(match.group(1)) if match else None


def _coerce_page(value: Any) -> int | None:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page > 0 else None


def _next_m_index(blocks: list[Any]) -> int:
    numbers: list[int] = []
    for item in blocks:
        if not isinstance(item, dict):
            continue
        match = re.fullmatch(r"M(\d+)", str(item.get("id") or ""))
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def _fallback_section(blocks: list[Any]) -> dict[str, str]:
    for item in blocks:
        if isinstance(item, dict) and item.get("section_id"):
            return {"section": str(item.get("section") or "Formula vision"), "section_id": str(item.get("section_id"))}
    return {"section": "Formula vision", "section_id": "sec:001"}
