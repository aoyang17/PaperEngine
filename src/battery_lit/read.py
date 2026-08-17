from __future__ import annotations

import json
import contextlib
import io
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .paths import TopicPaths
from .schemas import validate_with_schema

MAX_VISUAL_PAGES = 40
PAGE_RENDER_DPI = 110
MATH_PAGE_RENDER_DPI = 180
THUMB_WIDTH = 220
MAX_MATH_PAGES = 6
SOURCE_MAP_NAME = "source_map.json"
PAPER_INDEX_NAME = "paper_index.json"
NOTE_PLAN_NAME = "note_plan.json"
MATH_INDEX_NAME = "math_index.json"
FORMULA_VISION_NAME = "formula_vision.json"
ZH_MISSING_MARKER = "【中文翻译缺失】"
SOURCE_REF_RE = re.compile(r"\b[SCFTME]\d{3,}\b")
PAPER_TYPES = {"method", "theory", "dataset_benchmark", "survey", "application", "system_tooling"}
MATH_TERMS = {
    "equation",
    "theorem",
    "lemma",
    "proof",
    "optimality",
    "subject to",
    "s.t.",
    "min",
    "max",
    "argmin",
    "hamiltonian",
    "lagrange",
    "kkt",
    "costate",
    "adjoint",
    "euler",
    "pontryagin",
    "constraint",
    "differential",
    "variational",
}
EQUATION_SYMBOL_RE = re.compile(r"(=|<=|>=|\\le|\\ge|\\int|\\sum|\\dot|\\frac|->|\\rightarrow|∫|Σ|≤|≥|→|λ|μ|∂)")
INTERNAL_NUMERIC_TERMS = {
    "parsed pdf",
    "parsed pages",
    "rendered pages",
    "visual pages",
    "page count",
    "parser",
    "source map",
    "source-map",
    "deep_read",
    "reading artifact",
    "reading bundle",
}
BAD_READER_PHRASES = {
    "this reread",
    "the reread",
    "reread as",
    "reread identifies",
    "selected evidence",
    "selected boundary evidence",
    "evidence block",
    "validator requirement",
    "validation error",
    "reading bundle",
    "should highlight",
    "decisive evidence comes from",
}
BAD_ZH_READER_PHRASES = {
    "这次重读",
    "本次重读",
    "本次解读",
    "重新解读结果",
    "所选证据",
    "证据块",
    "验证器",
    "验证错误",
    "schema要求",
    "读者应结合证据",
    "中文解读应突出",
    "证据来自",
    "英文报告",
    "source_refs",
    "以原文为准",
    "结合英文证据",
    "该论文从流匹配或连续生成建模的具体问题出发",
    "围绕流匹配或连续生成建模，该步骤解释",
    "中文说明仅修正显示层翻译",
    "需要按论文原文定义为准",
    "精确符号以原文为准",
    "应回到英文报告对应",
    "should highlight",
    "decisive evidence comes from",
}
INTERNAL_PROMPT_LEAK_PHRASES = {
    "hard time budget",
    "do not cat or dump full parsed.md",
    "validator-shaped",
    "approved paper-local",
    "run validate-report",
    "run validate report",
    "run quality-audit",
    "run quality audit",
    "run rebuild-note",
    "run rebuild note",
    "write only the approved",
    "source_map.json, note_plan.json, and deep_read.json",
    "partial user-facing artifact",
    "quality-audit wording",
    "validation and quality-audit errors",
    "prompt text",
    "workflow words",
    "deterministic draft writer",
    "draft generator",
    "helper script",
    "schema-valid draft",
    "schema-valid drafts",
    "parsed/index-only",
    "bulk draft generator",
    "generic bulk draft",
    "staging helper",
    "read-batch staging",
    ".tmp/read_batch",
}
PARSER_ARTIFACT_TERMS = {"�", "<sup>", "</sup>", "<sub>", "</sub>"}
SECTION_NAME_ONLY_TERMS = {
    "abstract",
    "introduction",
    "background",
    "related work",
    "preliminaries",
    "method",
    "methods",
    "methodology",
    "approach",
    "model",
    "experiments",
    "experiment",
    "evaluation",
    "results",
    "discussion",
    "limitations",
    "future work",
    "conclusion",
    "conclusions",
    "appendix",
    "references",
}
EXTERNAL_AVAILABILITY_TERMS = {
    "arxiv",
    "external",
    "github",
    "lookup",
    "openalex",
    "publisher",
    "retrieval",
    "semantic scholar",
}
TYPE_SECTIONS = {
    "method": "method_understanding",
    "theory": "theory_understanding",
    "dataset_benchmark": "dataset_benchmark_understanding",
    "survey": "survey_understanding",
    "application": "application_understanding",
    "system_tooling": "system_understanding",
}
TYPE_REQUIRED_FIELDS = {
    "method": ["pipeline", "engineering_derivation_sketch", "implementation_details"],
    "theory": ["assumptions", "key_results", "engineering_proof_sketch", "limitations"],
    "dataset_benchmark": ["data_construction", "statistics", "availability", "biases_or_limits"],
    "survey": ["scope", "taxonomy", "timeline_milestones", "coverage_gaps"],
    "application": ["task_context", "experimental_setup", "constraints", "transfer_limits"],
    "system_tooling": ["architecture", "interfaces", "workflow", "failure_modes"],
}
SURVEY_TIMELINE_MISSING_TERMS = {"timeline", "milestone", "history", "historical"}


def _source_refs_text(value: Any, source_index: dict[str, dict[str, Any]] | None = None) -> str:
    refs = value.get("source_refs") if isinstance(value, dict) else None
    if not refs:
        return ""
    if source_index:
        return "Evidence: " + "; ".join(_source_label(str(ref), source_index) for ref in refs)
    return "Evidence: " + ", ".join(str(ref) for ref in refs)


def _append_sourced_items(
    lines: list[str],
    title: str,
    values: Any,
    source_index: dict[str, dict[str, Any]] | None = None,
) -> None:
    if not values:
        return
    lines.extend(["", f"## {title}"])
    for value in values:
        if isinstance(value, dict):
            lines.append(f"- {_item_summary_text(value)}")
            refs = _source_refs_text(value, source_index)
            if refs:
                lines.append(f"  - {refs}")
        else:
            lines.append(f"- {value}")


def _append_sourced_text(
    lines: list[str],
    label: str,
    value: Any,
    source_index: dict[str, dict[str, Any]] | None = None,
) -> None:
    if not isinstance(value, dict):
        return
    lines.append(f"- {label}: {value.get('text', '')}")
    refs = _source_refs_text(value, source_index)
    if refs:
        lines.append(f"  - {refs}")


def _item_summary_text(value: dict[str, Any]) -> str:
    if value.get("text"):
        return str(value["text"])
    for keys in [
        ("label", "equation", "explanation"),
        ("principle", "role", "intuition"),
        ("family", "core_idea", "strengths", "limitations", "best_for"),
    ]:
        parts = [str(value.get(key) or "").strip() for key in keys]
        parts = [part for part in parts if part]
        if parts:
            return " | ".join(parts)
    return str(value)


def parse_pdf(root: str | Path, bibkey: str) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    paper_dir = paths.paper_dir(bibkey)
    pdf_path = paper_dir / "paper.pdf"
    if not pdf_path.exists():
        return {"ok": False, "error": f"missing PDF for {bibkey}"}
    parsed_path = paper_dir / "parsed.md"
    report_path = paper_dir / "parser_report.json"
    text, parser, parser_error = _parse_pdf_text(pdf_path)
    parsed_path.write_text(text, encoding="utf-8")
    visual_report = _build_visual_index(paths.root, paper_dir, pdf_path)
    paper_index = _build_paper_index(text, visual_report, parser)
    parse_quality = _assess_math_parse_quality(text, paper_index)
    paper_index["coverage"]["math_parse_quality"] = parse_quality["quality"]
    paper_index["coverage"]["math_parse_reasons"] = parse_quality["reasons"]
    if parser_error:
        paper_index["coverage"]["known_limitations"].append(parser_error)
    (paper_dir / PAPER_INDEX_NAME).write_text(json.dumps(paper_index, indent=2), encoding="utf-8")
    _repair_source_map_after_parse(paper_dir, paper_index)
    math_index = _build_math_index(paths.root, paper_dir, pdf_path, text, paper_index, visual_report, parse_quality)
    (paper_dir / MATH_INDEX_NAME).write_text(json.dumps(math_index, indent=2), encoding="utf-8")
    report = {
        "ok": True,
        "parser": parser,
        "parser_error": parser_error,
        "parsed": str(parsed_path.relative_to(paths.root)),
        "paper_index": str((paper_dir / PAPER_INDEX_NAME).relative_to(paths.root)),
        "math_index": str((paper_dir / MATH_INDEX_NAME).relative_to(paths.root)),
        "math_parse_quality": parse_quality["quality"],
        "math_parse_reasons": parse_quality["reasons"],
        **visual_report,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _repair_source_map_after_parse(paper_dir: Path, paper_index: dict[str, Any]) -> None:
    source_map_path = paper_dir / SOURCE_MAP_NAME
    if not source_map_path.exists():
        return
    try:
        source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    paragraphs = [item for item in paper_index.get("paragraphs") or [] if isinstance(item, dict)]
    paragraph_ids = {str(item.get("paragraph_id")) for item in paragraphs}
    changed = False
    for block in source_map.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        refs = [str(ref) for ref in block.get("paragraph_ids") or []]
        if refs and all(ref in paragraph_ids for ref in refs):
            continue
        if str(block.get("source_kind") or "") not in {"body_text", "caption", "equation"}:
            continue
        matches = _match_source_block_to_paragraphs(block, paragraphs, target_count=max(1, len(refs)))
        if not matches:
            continue
        block["paragraph_ids"] = [str(match["paragraph_id"]) for match in matches]
        block["section_id"] = str(matches[0].get("section_id") or block.get("section_id") or "")
        block["page"] = int(matches[0].get("page") or block.get("page") or 1)
        changed = True
    if changed:
        source_map_path.write_text(json.dumps(source_map, indent=2), encoding="utf-8")


def _match_source_block_to_paragraphs(block: dict[str, Any], paragraphs: list[dict[str, Any]], target_count: int = 1) -> list[dict[str, Any]]:
    needle = _norm_match_text(str(block.get("source_text") or ""))[:800]
    if not needle:
        return paragraphs[:1]
    scored: list[tuple[float, dict[str, Any]]] = []
    for paragraph in paragraphs:
        haystack = _norm_match_text(str(paragraph.get("text") or ""))
        if not haystack:
            continue
        if needle[:160] and needle[:160] in haystack:
            return [paragraph]
        score = _overlap_score(needle, haystack)
        if score > 0:
            scored.append((score, paragraph))
    if not scored:
        return []
    best = max(score for score, _ in scored)
    if best < 0.25:
        return []
    cutoff = max(0.25, best * 0.65)
    selected = [paragraph for score, paragraph in sorted(scored, key=lambda item: (-item[0], str(item[1].get("paragraph_id") or ""))) if score >= cutoff]
    selected = selected[: max(1, min(target_count, 5))]
    return sorted(selected, key=lambda item: str(item.get("paragraph_id") or ""))


def _norm_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _overlap_score(needle: str, haystack: str) -> float:
    if not needle or not haystack:
        return 0.0
    needle_words = set(re.findall(r"[a-z0-9]{3,}", needle))
    haystack_words = set(re.findall(r"[a-z0-9]{3,}", haystack))
    if not needle_words:
        return 0.0
    return len(needle_words & haystack_words) / len(needle_words)


def _parse_pdf_text(pdf_path: Path) -> tuple[str, str, str | None]:
    backend = os.environ.get("BATTERY_LIT_PARSER_BACKEND", "pymupdf4llm").strip().lower() or "pymupdf4llm"
    if backend == "marker":
        marker = _parse_with_marker(pdf_path)
        if marker[0] is not None:
            return marker[0], "marker", None
        marker_error = marker[1] or "marker parser failed"
        default = _parse_with_pymupdf4llm(pdf_path)
        if default[0] is not None:
            return default[0], "pymupdf4llm", f"marker fallback: {marker_error}"
        return _fallback_parse_text(marker_error, default[1])
    default = _parse_with_pymupdf4llm(pdf_path)
    if default[0] is not None:
        return default[0], "pymupdf4llm", None
    return _fallback_parse_text(default[1])


def _parse_with_pymupdf4llm(pdf_path: Path) -> tuple[str | None, str | None]:
    try:
        import pymupdf4llm  # type: ignore

        # Recent parser releases may write progress through native code. Redirect
        # the stdout file descriptor as well as Python stdout so CLI JSON remains
        # machine-readable.
        saved_stdout = os.dup(1)
        try:
            with tempfile.TemporaryFile() as sink:
                os.dup2(sink.fileno(), 1)
                with contextlib.redirect_stdout(io.StringIO()):
                    markdown = pymupdf4llm.to_markdown(str(pdf_path), show_progress=False)
        finally:
            os.dup2(saved_stdout, 1)
            os.close(saved_stdout)
        return markdown, None
    except Exception as exc:
        return None, f"pymupdf4llm failed: {exc}"


def _parse_with_marker(pdf_path: Path) -> tuple[str | None, str | None]:
    marker = shutil.which("marker_single")
    if not marker:
        return None, "marker_single is not installed"
    try:
        with tempfile.TemporaryDirectory(prefix="battery-marker-") as tmp:
            command = [marker, str(pdf_path), "--output_format", "markdown", "--output_dir", tmp]
            proc = subprocess.run(command, text=True, capture_output=True, timeout=300, check=False)
            if proc.returncode != 0:
                return None, (proc.stderr or proc.stdout or f"marker_single exited {proc.returncode}").strip()
            markdowns = sorted(Path(tmp).rglob("*.md"), key=lambda path: path.stat().st_size, reverse=True)
            if not markdowns:
                return None, "marker_single produced no markdown output"
            return markdowns[0].read_text(encoding="utf-8", errors="ignore"), None
    except Exception as exc:
        return None, f"marker_single failed: {exc}"


def _fallback_parse_text(*errors: str | None) -> tuple[str, str, str]:
    joined = "; ".join(error for error in errors if error)
    text = "# Parsed text unavailable\n\nParser could not extract this PDF automatically."
    if joined:
        text += f"\n\nError: {joined}\n"
    return text, "fallback", joined or "automatic text parsing failed"


def _build_visual_index(root: Path, paper_dir: Path, pdf_path: Path) -> dict[str, Any]:
    page_image_dir = paper_dir / "page_images"
    visual_index_path = paper_dir / "visual_index.md"
    try:
        import pymupdf as fitz  # type: ignore
        from PIL import Image  # type: ignore
    except Exception as exc:
        visual_index_path.write_text(
            "# Visual index unavailable\n\n"
            f"Could not import PDF rendering dependencies: {exc}\n",
            encoding="utf-8",
        )
        return {
            "visual_ok": False,
            "visual_error": f"missing render dependencies: {exc}",
            "visual_index": str(visual_index_path.relative_to(root)),
            "page_images": [],
        }

    page_image_dir.mkdir(parents=True, exist_ok=True)
    for old in page_image_dir.glob("page-*.png"):
        old.unlink()
    contact_sheet_path = page_image_dir / "contact_sheet.jpg"
    if contact_sheet_path.exists():
        contact_sheet_path.unlink()

    page_images: list[str] = []
    thumbnails: list[Image.Image] = []
    try:
        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        render_count = min(page_count, MAX_VISUAL_PAGES)
        zoom = PAGE_RENDER_DPI / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        for page_index in range(render_count):
            page = doc[page_index]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            out = page_image_dir / f"page-{page_index + 1:03d}.png"
            pix.save(str(out))
            page_images.append(str(out.relative_to(root)))
            with Image.open(out) as image:
                thumb_height = max(1, int(image.height * (THUMB_WIDTH / image.width)))
                thumb = image.resize((THUMB_WIDTH, thumb_height))
                thumbnails.append(thumb.copy())
        doc.close()
        contact_sheet_rel = _write_contact_sheet(root, contact_sheet_path, thumbnails)
        _write_visual_index(root, visual_index_path, page_images, contact_sheet_rel, page_count, render_count)
        return {
            "visual_ok": True,
            "page_count": page_count,
            "visual_pages_rendered": render_count,
            "visual_pages_truncated": page_count > render_count,
            "visual_index": str(visual_index_path.relative_to(root)),
            "contact_sheet": contact_sheet_rel,
            "page_images": page_images,
        }
    except Exception as exc:
        visual_index_path.write_text(
            "# Visual index unavailable\n\n"
            f"Could not render this PDF automatically: {exc}\n",
            encoding="utf-8",
        )
        return {
            "visual_ok": False,
            "visual_error": str(exc),
            "visual_index": str(visual_index_path.relative_to(root)),
            "page_images": page_images,
        }


def _write_contact_sheet(root: Path, contact_sheet_path: Path, thumbnails: list[Any]) -> str | None:
    if not thumbnails:
        return None
    from PIL import Image, ImageDraw  # type: ignore

    columns = 4
    gap = 18
    label_height = 28
    rows = (len(thumbnails) + columns - 1) // columns
    cell_width = THUMB_WIDTH
    cell_height = max(image.height for image in thumbnails) + label_height
    sheet_width = columns * cell_width + (columns + 1) * gap
    sheet_height = rows * cell_height + (rows + 1) * gap
    sheet = Image.new("RGB", (sheet_width, sheet_height), "white")
    draw = ImageDraw.Draw(sheet)
    for index, thumb in enumerate(thumbnails):
        row, col = divmod(index, columns)
        x = gap + col * (cell_width + gap)
        y = gap + row * (cell_height + gap)
        sheet.paste(thumb, (x, y + label_height))
        draw.text((x, y), f"page {index + 1}", fill=(40, 40, 40))
    sheet.save(contact_sheet_path, quality=86)
    return str(contact_sheet_path.relative_to(root))


def _write_visual_index(
    root: Path,
    visual_index_path: Path,
    page_images: list[str],
    contact_sheet: str | None,
    page_count: int,
    render_count: int,
) -> None:
    lines = [
        "# Visual index",
        "",
        f"- Total pages: {page_count}",
        f"- Rendered pages: {render_count}",
    ]
    if page_count > render_count:
        lines.append(f"- Truncated: only the first {render_count} pages were rendered to control token and disk cost.")
    if contact_sheet:
        lines.extend(["", f"![Contact sheet]({Path(contact_sheet).relative_to(visual_index_path.parent.relative_to(root)).as_posix()})"])
    lines.extend(["", "## Page images"])
    for image_path in page_images:
        rel = Path(image_path).relative_to(visual_index_path.parent.relative_to(root)).as_posix()
        label = Path(image_path).stem.replace("-", " ")
        lines.append(f"- [{label}]({rel})")
    visual_index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _assess_math_parse_quality(text: str, paper_index: dict[str, Any]) -> dict[str, Any]:
    sections = [item for item in paper_index.get("sections") or [] if isinstance(item, dict)]
    paragraphs = [item for item in paper_index.get("paragraphs") or [] if isinstance(item, dict)]
    body_chars = len(text)
    pua_chars = sum(1 for char in text if "\ue000" <= char <= "\uf8ff")
    suspicious_sections = [
        str(item.get("title") or "")
        for item in sections
        if _is_suspicious_math_heading(str(item.get("title") or ""))
    ]
    equation_like_lines = _equation_like_lines(text)
    math_term_hits = _math_term_hits(text)
    reasons: list[str] = []
    if body_chars > 4000 and len(sections) <= 2:
        reasons.append("section_detection_collapsed")
    if len(sections) > 80 and len(suspicious_sections) > 8:
        reasons.append("formula_text_polluted_section_detection")
    if body_chars and pua_chars / body_chars > 0.002:
        reasons.append("high_private_use_symbol_ratio")
    if math_term_hits >= 20 and len(equation_like_lines) < 2:
        reasons.append("math_heavy_but_few_clean_equation_lines")
    quality = "poor" if reasons else "fair" if math_term_hits >= 8 else "good"
    return {
        "quality": quality,
        "reasons": reasons,
        "metrics": {
            "section_count": len(sections),
            "paragraph_count": len(paragraphs),
            "body_chars": body_chars,
            "private_use_chars": pua_chars,
            "suspicious_section_count": len(suspicious_sections),
            "equation_like_line_count": len(equation_like_lines),
            "math_term_hits": math_term_hits,
        },
    }


def _is_suspicious_math_heading(title: str) -> bool:
    compact = title.strip()
    if not compact:
        return False
    pua = sum(1 for char in compact if "\ue000" <= char <= "\uf8ff")
    math_symbols = len(EQUATION_SYMBOL_RE.findall(compact))
    if pua >= 2:
        return True
    if math_symbols >= 2 and len(compact) > 20:
        return True
    return len(compact) > 180


def _math_term_hits(text: str) -> int:
    lowered = text.lower()
    return sum(lowered.count(term) for term in MATH_TERMS)


def _equation_like_lines(text: str, limit: int = 80) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if len(line) < 6 or len(line) > 600:
            continue
        lowered = line.lower()
        symbol_count = len(EQUATION_SYMBOL_RE.findall(line))
        keyword_hit = any(term in lowered for term in ["subject to", "s.t.", "min", "max", "argmin", "hamiltonian", "kkt"])
        if symbol_count or keyword_hit:
            lines.append(line)
        if len(lines) >= limit:
            break
    return lines


def _build_math_index(
    root: Path,
    paper_dir: Path,
    pdf_path: Path,
    text: str,
    paper_index: dict[str, Any],
    visual_report: dict[str, Any],
    parse_quality: dict[str, Any],
) -> dict[str, Any]:
    selected_pages = _select_math_pages(pdf_path, text, visual_report, parse_quality)
    math_page_images = _render_math_pages(root, paper_dir, pdf_path, selected_pages)
    candidates = _math_candidates_from_text(text, paper_index)
    needs_vision = parse_quality.get("quality") == "poor" or len(candidates) < 2
    reasons = list(parse_quality.get("reasons") or [])
    if len(candidates) < 2:
        reasons.append("fewer_than_two_clean_formula_candidates")
    return {
        "schema_version": "v3-math-index-2026-06",
        "parse_quality": parse_quality,
        "selected_pages": selected_pages,
        "math_page_images": math_page_images,
        "text_candidates": candidates,
        "vision_fallback": {
            "needed": bool(needs_vision),
            "status": "pending" if needs_vision and math_page_images else "not_needed" if not needs_vision else "blocked",
            "reasons": reasons,
            "image_paths": math_page_images,
            "instruction": (
                "Run `battery_lit read <bibkey> --vision-formulas` when parsed text cannot safely recover key "
                "equations. The command attaches these page images to Codex through a bounded image-input "
                "runner. Transcribe only visible formulas, keep uncertainty, and do not invent notation from "
                "domain memory."
            ),
        },
    }


def _select_math_pages(
    pdf_path: Path,
    text: str,
    visual_report: dict[str, Any],
    parse_quality: dict[str, Any],
) -> list[int]:
    page_count = int(visual_report.get("page_count") or 0)
    if page_count <= 0:
        return []
    scores: dict[int, int] = {page: 0 for page in range(1, min(page_count, MAX_VISUAL_PAGES) + 1)}
    for page in list(scores)[:3]:
        scores[page] += 2
    try:
        import pymupdf as fitz  # type: ignore

        doc = fitz.open(str(pdf_path))
        for index in range(min(len(doc), MAX_VISUAL_PAGES)):
            page_text = doc[index].get_text("text") or ""
            lowered = page_text.lower()
            score = sum(lowered.count(term) for term in MATH_TERMS)
            score += min(8, len(EQUATION_SYMBOL_RE.findall(page_text)))
            if any("\ue000" <= char <= "\uf8ff" for char in page_text):
                score += 3
            scores[index + 1] += score
        doc.close()
    except Exception:
        lowered = text.lower()
        if any(term in lowered for term in ["theorem", "equation", "subject to", "hamiltonian", "lagrange", "kkt"]):
            for page in list(scores)[:MAX_MATH_PAGES]:
                scores[page] += 1
    if parse_quality.get("quality") == "poor":
        for page in list(scores)[:4]:
            scores[page] += 1
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [page for page, score in ranked[:MAX_MATH_PAGES] if score > 0]


def _render_math_pages(root: Path, paper_dir: Path, pdf_path: Path, selected_pages: list[int]) -> list[str]:
    if not selected_pages:
        return []
    out_dir = paper_dir / "math_pages"
    try:
        import pymupdf as fitz  # type: ignore
    except Exception:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("page-*.png"):
        old.unlink()
    rendered: list[str] = []
    try:
        doc = fitz.open(str(pdf_path))
        matrix = fitz.Matrix(MATH_PAGE_RENDER_DPI / 72.0, MATH_PAGE_RENDER_DPI / 72.0)
        for page_number in selected_pages:
            if page_number < 1 or page_number > len(doc):
                continue
            pix = doc[page_number - 1].get_pixmap(matrix=matrix, alpha=False)
            out = out_dir / f"page-{page_number:03d}.png"
            pix.save(str(out))
            rendered.append(str(out.relative_to(root)))
        doc.close()
    except Exception:
        return rendered
    return rendered


def _math_candidates_from_text(text: str, paper_index: dict[str, Any]) -> list[dict[str, Any]]:
    paragraphs = [item for item in paper_index.get("paragraphs") or [] if isinstance(item, dict)]
    paragraph_lookup = {str(item.get("text") or "")[:160]: item for item in paragraphs}
    candidates: list[dict[str, Any]] = []
    for line in _equation_like_lines(text, limit=30):
        paragraph = _nearest_paragraph(line, paragraphs, paragraph_lookup)
        candidates.append(
            {
                "id": f"M{len(candidates) + 1:03d}",
                "label": _equation_label(line),
                "page": int(paragraph.get("page") or 1) if paragraph else 1,
                "section_id": str(paragraph.get("section_id") or "sec:unknown") if paragraph else "sec:unknown",
                "paragraph_ids": [str(paragraph.get("paragraph_id"))] if paragraph and paragraph.get("paragraph_id") else [],
                "source_kind": "equation",
                "raw_text": line,
                "cleaned_equation": _clean_equation_text(line),
                "confidence": "medium" if "\uf000" not in line else "low",
                "backend": "parsed_text",
                "notes": "Candidate equation-like line from parsed text.",
            }
        )
        if len(candidates) >= 12:
            break
    return candidates


def _nearest_paragraph(line: str, paragraphs: list[dict[str, Any]], paragraph_lookup: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    for prefix, item in paragraph_lookup.items():
        if line[:60] and line[:60] in prefix:
            return item
    for item in paragraphs:
        text = str(item.get("text") or "")
        if line in text:
            return item
    return paragraphs[0] if paragraphs else None


def _equation_label(line: str) -> str:
    lowered = line.lower()
    for label, term in [
        ("Optimal-control objective", "min"),
        ("Constraint relation", "subject to"),
        ("Hamiltonian relation", "hamiltonian"),
        ("KKT condition", "kkt"),
        ("Theorem equation", "theorem"),
    ]:
        if term in lowered:
            return label
    return "Equation candidate"


def _clean_equation_text(line: str) -> str:
    cleaned = re.sub(r"\s+", " ", line).strip()
    cleaned = cleaned.replace("\uf03d", "=").replace("\uf02b", "+").replace("\uf02d", "-")
    cleaned = cleaned.replace("\uf0f2", "∫").replace("\uf064", "d").replace("\uf06a", "J")
    return cleaned


def _build_paper_index(text: str, visual_report: dict[str, Any], parser: str) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    paragraphs: list[dict[str, Any]] = []
    current_section = {
        "section_id": "sec:unknown",
        "title": "Unknown",
        "level": 1,
        "page_start": 1,
        "page_end": 1,
        "paragraph_start": None,
        "paragraph_end": None,
    }
    sections.append(current_section)
    buffer: list[str] = []

    def flush_paragraph() -> None:
        nonlocal buffer
        paragraph = "\n".join(buffer).strip()
        buffer = []
        if not paragraph:
            return
        paragraph_id = f"p:{len(paragraphs) + 1:04d}"
        paragraphs.append(
            {
                "paragraph_id": paragraph_id,
                "section_id": current_section["section_id"],
                "page": 1,
                "text": paragraph[:4000],
                "char_start": None,
                "char_end": None,
            }
        )
        if current_section["paragraph_start"] is None:
            current_section["paragraph_start"] = paragraph_id
        current_section["paragraph_end"] = paragraph_id

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            flush_paragraph()
            title = heading.group(2).strip()
            current_section = {
                "section_id": f"sec:{len(sections):03d}",
                "title": title,
                "level": len(heading.group(1)),
                "page_start": 1,
                "page_end": 1,
                "paragraph_start": None,
                "paragraph_end": None,
            }
            sections.append(current_section)
            continue
        if not line.strip():
            flush_paragraph()
        else:
            buffer.append(line)
    flush_paragraph()

    if not paragraphs:
        paragraph_id = "p:0001"
        paragraphs.append(
            {
                "paragraph_id": paragraph_id,
                "section_id": "sec:unknown",
                "page": 1,
                "text": "No parsed body text was available.",
                "char_start": None,
                "char_end": None,
            }
        )
        sections[0]["paragraph_start"] = paragraph_id
        sections[0]["paragraph_end"] = paragraph_id

    figures_tables: list[dict[str, Any]] = []
    for image_path in visual_report.get("page_images") or []:
        page_match = re.search(r"page-(\d+)", str(image_path))
        page = int(page_match.group(1)) if page_match else 1
        figures_tables.append(
            {
                "label": f"Page {page}",
                "kind": "page_image",
                "page": page,
                "caption": "Full-page rendered image used as approximate visual evidence.",
                "nearby_section_id": sections[0]["section_id"],
                "candidate_image_paths": [str(image_path)],
            }
        )

    page_count = int(visual_report.get("page_count") or 1)
    rendered_pages = int(visual_report.get("visual_pages_rendered") or len(visual_report.get("page_images") or []))
    return {
        "schema_version": "v3-paper-index-2026-06",
        "coverage": {
            "parsed_pages": page_count,
            "rendered_pages": rendered_pages,
            "missing_pages": [page for page in range(rendered_pages + 1, page_count + 1)],
            "parser": parser,
            "known_limitations": [] if parser != "fallback" else ["Automatic text parsing failed; fallback text is incomplete."],
        },
        "sections": sections,
        "paragraphs": paragraphs,
        "figures_tables": figures_tables,
    }


def validate_deep_read_report(root: str | Path, bibkey: str) -> dict[str, Any]:
    paper_dir = TopicPaths.from_root(root).paper_dir(bibkey)
    source_map_path = paper_dir / SOURCE_MAP_NAME
    paper_index_path = paper_dir / PAPER_INDEX_NAME
    note_plan_path = paper_dir / NOTE_PLAN_NAME
    report_path = paper_dir / "deep_read.json"
    for name, path in [(PAPER_INDEX_NAME, paper_index_path), (NOTE_PLAN_NAME, note_plan_path), (SOURCE_MAP_NAME, source_map_path)]:
        if not path.exists():
            return {"ok": False, "errors": [f"missing {name} for {bibkey}"]}
    if not source_map_path.exists():
        return {"ok": False, "errors": [f"missing {SOURCE_MAP_NAME} for {bibkey}"]}
    if not report_path.exists():
        return {"ok": False, "errors": [f"missing deep_read.json for {bibkey}"]}
    try:
        paper_index = json.loads(paper_index_path.read_text(encoding="utf-8"))
        note_plan = json.loads(note_plan_path.read_text(encoding="utf-8"))
        source_map = json.loads(source_map_path.read_text(encoding="utf-8"))
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "errors": [str(exc)]}
    math_index_path = paper_dir / MATH_INDEX_NAME
    formula_vision_path = paper_dir / FORMULA_VISION_NAME
    math_index = None
    formula_vision = None
    if math_index_path.exists():
        try:
            math_index = json.loads(math_index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {"ok": False, "errors": [f"{MATH_INDEX_NAME}: {exc}"]}
    if formula_vision_path.exists():
        try:
            formula_vision = json.loads(formula_vision_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {"ok": False, "errors": [f"{FORMULA_VISION_NAME}: {exc}"]}
    try:
        validate_with_schema(source_map, "source_map.schema.json")
        if math_index is not None:
            validate_with_schema(math_index, "math_index.schema.json")
        if formula_vision is not None:
            validate_with_schema(formula_vision, "formula_vision.schema.json")
        validate_with_schema(data, "deep_read_report.schema.json")
    except Exception as exc:
        return {"ok": False, "errors": [str(exc)]}
    contract_errors = _validate_reading_contract(data, source_map, paper_index, note_plan, math_index)
    contract_errors.extend(_validate_translation_coverage(data))
    quality = _audit_deep_read_quality(data, source_map, paper_index, note_plan)
    contract_errors.extend(quality["errors"])
    if contract_errors:
        return {"ok": False, "errors": contract_errors}
    return {"ok": True, "errors": []}


def audit_deep_read_quality(root: str | Path, bibkey: str) -> dict[str, Any]:
    paper_dir = TopicPaths.from_root(root).paper_dir(bibkey)
    required = {
        PAPER_INDEX_NAME: paper_dir / PAPER_INDEX_NAME,
        NOTE_PLAN_NAME: paper_dir / NOTE_PLAN_NAME,
        SOURCE_MAP_NAME: paper_dir / SOURCE_MAP_NAME,
        "deep_read.json": paper_dir / "deep_read.json",
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        return {
            "ok": False,
            "errors": [f"missing {name} for {bibkey}" for name in missing],
            "warnings": [],
            "quality_score": 0,
            "failed_fields": missing,
        }
    try:
        paper_index = json.loads(required[PAPER_INDEX_NAME].read_text(encoding="utf-8"))
        note_plan = json.loads(required[NOTE_PLAN_NAME].read_text(encoding="utf-8"))
        source_map = json.loads(required[SOURCE_MAP_NAME].read_text(encoding="utf-8"))
        data = json.loads(required["deep_read.json"].read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": [], "quality_score": 0, "failed_fields": ["json"]}
    result = _audit_deep_read_quality(data, source_map, paper_index, note_plan)
    artifact_errors = _audit_generated_reading_artifacts(paper_dir)
    if artifact_errors:
        errors = [str(item) for item in result.get("errors") or []] + artifact_errors
        warnings = [str(item) for item in result.get("warnings") or []]
        return {
            "ok": False,
            "errors": errors,
            "warnings": warnings,
            "quality_score": max(0, int(result.get("quality_score") or 0) - 12 * len(artifact_errors)),
            "failed_fields": _failed_quality_fields(errors),
        }
    return result


def audit_reading_library(root: str | Path, *, repeat_threshold: int = 2, bibkeys: list[str] | None = None) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    repeated: dict[str, dict[str, Any]] = {}
    failed_papers: dict[str, list[str]] = {}
    paper_count = 0
    text_index: dict[str, dict[str, Any]] = {}
    allowed_bibkeys = {str(item) for item in bibkeys or [] if str(item).strip()}
    if allowed_bibkeys:
        report_paths = [paths.paper_dir(bibkey) / "deep_read.json" for bibkey in sorted(allowed_bibkeys)]
        report_paths = [path for path in report_paths if path.exists()]
    else:
        report_paths = sorted(paths.papers.glob("*/deep_read.json"))
    for report_path in report_paths:
        bibkey = report_path.parent.name
        paper_count += 1
        quality = audit_deep_read_quality(paths.root, bibkey)
        if not quality.get("ok"):
            failed_papers[bibkey] = [str(item) for item in quality.get("errors") or []]
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for path, text in _reader_facing_strings(data):
            if _library_audit_path_allowed(path):
                _add_library_text(text_index, bibkey, path, text)
        zh = ((data.get("translations") or {}).get("zh") or {}) if isinstance(data.get("translations"), dict) else {}
        for path, text in _reader_facing_strings(zh, prefix="translations.zh"):
            if _library_audit_path_allowed(path):
                _add_library_text(text_index, bibkey, path, text)

    for normalized, item in sorted(text_index.items(), key=lambda pair: (-len(pair[1]["papers"]), pair[0])):
        papers = sorted(item["papers"])
        if len(papers) >= repeat_threshold:
            repeated[normalized] = {
                "count": len(papers),
                "text": item["text"],
                "papers": papers[:8],
                "paths": sorted(item["paths"])[:8],
            }
            if len(repeated) >= 50:
                break
    errors: list[str] = []
    if failed_papers:
        errors.append(f"{len(failed_papers)} papers failed individual reading quality audit")
    if repeated:
        errors.append(f"{len(repeated)} repeated reader-facing text blocks across >= {repeat_threshold} papers")
    return {
        "ok": not errors,
        "errors": errors,
        "total_papers": paper_count,
        "audit_scope": "selected" if allowed_bibkeys else "library",
        "target_bibkeys": sorted(allowed_bibkeys) if allowed_bibkeys else [],
        "failed_papers": failed_papers,
        "repeated_text": repeated,
    }


def _audit_deep_read_quality(
    data: dict[str, Any],
    source_map: dict[str, Any],
    paper_index: dict[str, Any],
    note_plan: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(_validate_reader_facing_quality(data, source_map))
    warnings.extend(_source_map_granularity_warnings(source_map, paper_index))
    failed_fields = _failed_quality_fields(errors)
    score = max(0, 100 - 12 * len(errors) - 4 * len(warnings))
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "quality_score": score,
        "failed_fields": failed_fields,
    }


def _validate_reading_contract(
    data: dict[str, Any],
    source_map: dict[str, Any],
    paper_index: dict[str, Any],
    note_plan: dict[str, Any],
    math_index: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    block_items = [item for item in source_map.get("blocks") or [] if isinstance(item, dict)]
    block_ids = {str(item.get("id")) for item in block_items}
    block_index = {str(item.get("id")): item for item in block_items}
    section_ids = {str(item.get("section_id")) for item in paper_index.get("sections") or [] if isinstance(item, dict)}
    paragraph_ids = {str(item.get("paragraph_id")) for item in paper_index.get("paragraphs") or [] if isinstance(item, dict)}
    for item in block_items:
        block_id = str(item.get("id") or "")
        source_kind = str(item.get("source_kind") or "")
        if block_id.startswith("E") or source_kind == "external":
            errors.extend(_validate_external_source_block(item))
            if source_kind == "external":
                continue
        section_id = str(item.get("section_id") or "")
        if section_id not in section_ids:
            errors.append(f"source block {block_id} references unknown section_id {section_id}")
        refs = [str(ref) for ref in item.get("paragraph_ids") or []]
        for ref in refs:
            if ref not in paragraph_ids:
                errors.append(f"source block {block_id} references unknown paragraph_id {ref}")
        if source_kind in {"body_text", "caption"} and not refs:
            errors.append(f"source block {block_id} needs paragraph_ids for {source_kind} evidence")
    refs = _collect_source_refs(data)
    for ref in refs:
        block_id = _source_ref_block_id(ref)
        if block_id not in block_ids:
            errors.append(f"source ref {ref} is not present in {SOURCE_MAP_NAME}")
            continue
        if block_id.startswith("E") and str(block_index[block_id].get("source_kind") or "") != "external":
            errors.append(f"source ref {ref} points to non-external source block {block_id}")

    profile = data.get("paper_profile") or {}
    primary = str(note_plan.get("primary_type") or "")
    lenses = [str(item) for item in note_plan.get("active_lenses") or []]
    report_primary = str(profile.get("primary_type") or "")
    report_lenses = [str(item) for item in profile.get("active_lenses") or []]
    if primary not in PAPER_TYPES:
        errors.append(f"note_plan.primary_type must be one of {sorted(PAPER_TYPES)}")
    unknown_lenses = sorted({item for item in lenses + report_lenses if item not in PAPER_TYPES})
    if unknown_lenses:
        errors.append(f"active_lenses contain unsupported types: {', '.join(unknown_lenses)}")
    if primary and primary not in lenses:
        errors.append("note_plan.active_lenses must include note_plan.primary_type")
    if primary != report_primary:
        errors.append("note_plan.primary_type must match deep_read.paper_profile.primary_type")
    missing_lenses = sorted(set(lenses) - set(report_lenses))
    if missing_lenses:
        errors.append(f"deep_read.paper_profile.active_lenses must cover note_plan lenses: {', '.join(missing_lenses)}")
    if "theory" in set(lenses + report_lenses) and math_index is None:
        errors.append(f"missing {MATH_INDEX_NAME} for active theory lens; rerun `battery_lit read <bibkey> --parse-only`")
    if "theory" in set(lenses + report_lenses) and _math_vision_fallback_pending(math_index):
        errors.append(f"{MATH_INDEX_NAME} vision_fallback is pending; run `battery_lit read <bibkey> --vision-formulas` before final writing")
    for lens in lenses:
        section_name = TYPE_SECTIONS.get(lens)
        if not section_name:
            continue
        section = data.get(section_name)
        if not _has_content(section):
            errors.append(f"{section_name} is required for active lens {lens}")
            continue
        required_fields = TYPE_REQUIRED_FIELDS.get(lens, [])
        if lens == "dataset_benchmark" and isinstance(section, dict) and section.get("format") == "structured_v2":
            required_fields = ["format", "key_numbers", "construction_steps", "biases_or_limits"]
        for field in required_fields:
            if not _has_content(section.get(field) if isinstance(section, dict) else None):
                errors.append(f"{section_name}.{field} is required for active lens {lens}")
        if lens == "theory" and isinstance(section, dict):
            key_equations = section.get("key_equations") if isinstance(section.get("key_equations"), list) else []
            theorem_chain = section.get("theorem_or_principle_chain") if isinstance(section.get("theorem_or_principle_chain"), list) else []
            extraction = data.get("extraction_notes") if isinstance(data.get("extraction_notes"), dict) else {}
            low_confidence = extraction.get("low_confidence_equations") if isinstance(extraction.get("low_confidence_equations"), list) else []
            if len(key_equations) < 2:
                if not low_confidence:
                    errors.append("theory_understanding.key_equations needs at least two items for active theory lens")
                elif not _math_vision_fallback_exhausted(math_index):
                    errors.append(
                        "theory_understanding.key_equations cannot be skipped with low_confidence_equations "
                        f"unless {MATH_INDEX_NAME} records exhausted or blocked vision fallback"
                    )
            if not theorem_chain:
                errors.append("theory_understanding.theorem_or_principle_chain is required for active theory lens")
        if lens == "survey" and isinstance(section, dict):
            taxonomy = section.get("taxonomy") if isinstance(section.get("taxonomy"), list) else []
            matrix = section.get("method_family_matrix") if isinstance(section.get("method_family_matrix"), list) else []
            timeline = section.get("timeline_milestones") if isinstance(section.get("timeline_milestones"), list) else []
            extraction = data.get("extraction_notes") if isinstance(data.get("extraction_notes"), dict) else {}
            missing_sections = extraction.get("missing_sections") if isinstance(extraction.get("missing_sections"), list) else []
            missing_timeline = any(any(term in str(item).lower() for term in SURVEY_TIMELINE_MISSING_TERMS) for item in missing_sections)
            if len(taxonomy) < 3:
                errors.append("survey_understanding.taxonomy needs at least three method-family items for active survey lens")
            if len(matrix) < 3:
                errors.append("survey_understanding.method_family_matrix needs at least three rows for active survey lens")
            if not timeline and not missing_timeline:
                errors.append("survey_understanding.timeline_milestones is empty; extraction_notes.missing_sections must state that the paper does not provide timeline/milestones")
    planned_claims = note_plan.get("central_claims") or []
    actual_claims = data.get("central_claims") or []
    if len(planned_claims) < len(actual_claims):
        errors.append("note_plan.central_claims must cover the final central_claims")

    for index, item in enumerate((data.get("evaluation") or {}).get("numeric_results") or []):
        text_blob = " ".join(
            str(item.get(key) or "").lower()
            for key in ["dataset_or_task", "metric", "interpretation", "what_it_does_not_prove"]
        )
        if any(term in text_blob for term in INTERNAL_NUMERIC_TERMS):
            errors.append(f"evaluation.numeric_results[{index}] must describe paper content, not parser or internal workflow metadata")
        if not isinstance(item.get("value"), (int, float)):
            errors.append(f"evaluation.numeric_results[{index}].value must be numeric")
        if str(item.get("unit") or "").strip() == "%" and isinstance(item.get("value"), (int, float)) and not 0 <= item["value"] <= 100:
            errors.append(f"evaluation.numeric_results[{index}].value must be between 0 and 100 for percentages")
        if not item.get("source_refs"):
            errors.append(f"evaluation.numeric_results[{index}] needs source_refs")
        if (item.get("baseline") or item.get("comparison")) and not str(item.get("interpretation") or "").strip():
            errors.append(f"evaluation.numeric_results[{index}] needs interpretation for baseline/comparison")

    for index, item in enumerate(data.get("visual_cards") or []):
        crop_status = str(item.get("crop_status") or "").strip().lower()
        image_path = str(item.get("image_path") or "").strip()
        placeholder = str(item.get("placeholder_reason") or "").strip()
        if not str(item.get("placement_section") or "").strip():
            errors.append(f"visual_cards[{index}] needs placement_section")
        if crop_status not in {"tight_crop", "full_page_approximate", "placeholder", "missing"}:
            errors.append(f"visual_cards[{index}] has unsupported crop_status {crop_status}")
        if crop_status in {"tight_crop", "full_page_approximate"} and not image_path:
            errors.append(f"visual_cards[{index}] needs image_path for crop_status {crop_status}")
        if crop_status in {"placeholder", "missing"} and not placeholder:
            errors.append(f"visual_cards[{index}] needs placeholder_reason for crop_status {crop_status}")
        if crop_status != "tight_crop" and not item.get("reading_note"):
            errors.append(f"visual_cards[{index}] needs reading_note explaining non-tight visual evidence")
        image_page = _page_from_image_path(image_path)
        if image_page is not None and item.get("page") != image_page:
            errors.append(f"visual_cards[{index}] page must match image_path page-{image_page:03d}")
        ref_pages = _visual_ref_pages(item.get("source_refs") or [], block_index)
        if ref_pages and item.get("page") not in ref_pages:
            errors.append(f"visual_cards[{index}] page must match visual/caption source refs")
    extraction = data.get("extraction_notes") or {}
    approximate_visuals = [
        item for item in data.get("visual_cards") or []
        if str(item.get("crop_status") or "").lower() in {"full_page_approximate", "placeholder", "missing"}
    ]
    if approximate_visuals and not extraction.get("visual_crop_limitations"):
        errors.append("extraction_notes.visual_crop_limitations is required for approximate or missing visual cards")
    pseudocode = (data.get("method_understanding") or {}).get("algorithm_pseudocode")
    steps = (data.get("method_understanding") or {}).get("algorithm_steps") or []
    if isinstance(pseudocode, str) and pseudocode.strip() and "\n" not in pseudocode and len(pseudocode) > 120:
        errors.append("algorithm pseudocode must be multiline for readability")
    if isinstance(pseudocode, str) and pseudocode.strip() and not steps:
        errors.append("algorithm_steps are required when algorithm_pseudocode is present")
    for index, step in enumerate(steps):
        action = str(step.get("action") or "") if isinstance(step, dict) else ""
        if len(action) > 220:
            errors.append(f"method_understanding.algorithm_steps[{index}].action is too long for readable pseudocode")
    errors.extend(_validate_availability_source_refs(data.get("availability")))
    return errors


def _math_vision_fallback_exhausted(math_index: dict[str, Any] | None) -> bool:
    if not isinstance(math_index, dict):
        return False
    fallback = math_index.get("vision_fallback") if isinstance(math_index.get("vision_fallback"), dict) else {}
    status = str(fallback.get("status") or "").strip().lower()
    return status in {"exhausted", "blocked", "completed_no_formula"}


def _math_vision_fallback_pending(math_index: dict[str, Any] | None) -> bool:
    if not isinstance(math_index, dict):
        return False
    fallback = math_index.get("vision_fallback") if isinstance(math_index.get("vision_fallback"), dict) else {}
    if not bool(fallback.get("needed")):
        return False
    status = str(fallback.get("status") or "").strip().lower()
    return status not in {"completed", "completed_no_formula", "blocked", "exhausted"}


def _validate_external_source_block(item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    block_id = str(item.get("id") or "")
    source_kind = str(item.get("source_kind") or "")
    if not block_id.startswith("E"):
        errors.append(f"external source block {block_id} must use E### id")
    if source_kind != "external":
        errors.append(f"external source block {block_id} must use source_kind external")
    if item.get("page") != 0:
        errors.append(f"external source block {block_id} must have page 0")
    if str(item.get("section_id") or "") != "external_availability":
        errors.append(f"external source block {block_id} must use section_id external_availability")
    notes = str(item.get("notes") or "").lower()
    has_url = "url" in notes or "http://" in notes or "https://" in notes
    has_access = "access" in notes or "accessed" in notes
    has_query = "query" in notes or "lookup" in notes or "search" in notes
    if not (has_url and has_access and has_query):
        errors.append(f"external source block {block_id} notes must include URL, access date, and query or lookup path")
    return errors


def _validate_availability_source_refs(availability: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(availability, dict):
        return errors
    for key in ["code", "data", "models"]:
        item = availability.get(key) if isinstance(availability.get(key), dict) else {}
        refs = [str(ref) for ref in item.get("source_refs") or [] if str(ref).strip()]
        if _availability_has_reader_content(item) and not refs:
            errors.append(f"availability.{key} needs source_refs for availability conclusion")
        if _availability_requires_external_ref(item) and not any(_source_ref_block_id(ref).startswith("E") for ref in refs):
            errors.append(f"availability.{key} external lookup evidence needs an E### source_ref")
    return errors


def _availability_has_reader_content(item: dict[str, Any]) -> bool:
    return any(str(item.get(key) or "").strip() for key in ["status", "url", "evidence", "notes"])


def _availability_claims_external_lookup(item: dict[str, Any]) -> bool:
    text = " ".join(str(item.get(key) or "") for key in ["evidence", "notes"]).lower()
    return any(term in text for term in EXTERNAL_AVAILABILITY_TERMS)


def _availability_requires_external_ref(item: dict[str, Any]) -> bool:
    status = re.sub(r"[\s-]+", "_", str(item.get("status") or "").strip().lower())
    if str(item.get("url") or "").strip():
        return True
    if status in {"available", "found", "released", "not_available", "not_found", "unavailable"}:
        return True
    return _availability_claims_external_lookup(item)


def _validate_translation_coverage(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    translations = data.get("translations") if isinstance(data.get("translations"), dict) else {}
    zh = translations.get("zh") if isinstance(translations.get("zh"), dict) else {}
    if not zh:
        return ["missing zh translation: translations.zh"]

    _require_zh_text(errors, zh.get("one_sentence_summary"), "translations.zh.one_sentence_summary")
    _require_zh_sourced_list(errors, data.get("quick_read"), zh.get("quick_read"), "translations.zh.quick_read")

    argument = data.get("argument_map") if isinstance(data.get("argument_map"), dict) else {}
    argument_zh = zh.get("argument_map") if isinstance(zh.get("argument_map"), dict) else {}
    for key in ["gap", "core_contribution", "method_logic"]:
        _require_zh_for_sourced_text(errors, argument.get(key), argument_zh.get(key), f"translations.zh.argument_map.{key}")
    for key in ["decisive_evidence", "limitations", "future_work"]:
        _require_zh_sourced_list(errors, argument.get(key), argument_zh.get(key), f"translations.zh.argument_map.{key}")

    _require_zh_dict_list(
        errors,
        data.get("central_claims"),
        zh.get("central_claims"),
        "translations.zh.central_claims",
        ["claim", "evidence_summary", "what_it_proves", "what_it_does_not_prove", "open_question"],
    )

    method = data.get("method_understanding") if isinstance(data.get("method_understanding"), dict) else {}
    method_zh = zh.get("method_understanding") if isinstance(zh.get("method_understanding"), dict) else {}
    _require_zh_sourced_list(errors, method.get("pipeline"), method_zh.get("pipeline"), "translations.zh.method_understanding.pipeline")
    _require_zh_dict_list(
        errors,
        method.get("algorithm_steps"),
        method_zh.get("algorithm_steps"),
        "translations.zh.method_understanding.algorithm_steps",
        ["action", "inputs", "outputs"],
    )
    _require_zh_for_sourced_text(
        errors,
        method.get("engineering_derivation_sketch"),
        method_zh.get("engineering_derivation_sketch"),
        "translations.zh.method_understanding.engineering_derivation_sketch",
    )
    _require_zh_sourced_list(
        errors,
        method.get("implementation_details"),
        method_zh.get("implementation_details"),
        "translations.zh.method_understanding.implementation_details",
    )

    evaluation = data.get("evaluation") if isinstance(data.get("evaluation"), dict) else {}
    evaluation_zh = zh.get("evaluation") if isinstance(zh.get("evaluation"), dict) else {}
    for key in ["datasets", "metrics", "main_results", "ablation_or_comparison_takeaways"]:
        _require_zh_sourced_list(errors, evaluation.get(key), evaluation_zh.get(key), f"translations.zh.evaluation.{key}")
    _require_zh_dict_list(
        errors,
        evaluation.get("numeric_results"),
        evaluation_zh.get("numeric_results"),
        "translations.zh.evaluation.numeric_results",
        ["dataset_or_task", "metric", "interpretation", "what_it_does_not_prove"],
    )

    _require_zh_dict_list(
        errors,
        data.get("visual_cards"),
        zh.get("visual_cards"),
        "translations.zh.visual_cards",
        ["label", "source_caption", "reading_note"],
    )

    type_sections_zh = zh.get("type_sections") if isinstance(zh.get("type_sections"), dict) else {}
    for section_name in TYPE_SECTIONS.values():
        if section_name == "method_understanding":
            continue
        section = data.get(section_name)
        if section_name == "dataset_benchmark_understanding" and isinstance(section, dict) and section.get("format") == "structured_v2":
            continue
        if isinstance(section, dict) and section:
            section_zh = type_sections_zh.get(section_name) if isinstance(type_sections_zh.get(section_name), dict) else {}
            _require_zh_section(errors, section, section_zh, f"translations.zh.type_sections.{section_name}")

    theory = data.get("theory_understanding") if isinstance(data.get("theory_understanding"), dict) else {}
    theory_zh = type_sections_zh.get("theory_understanding") if isinstance(type_sections_zh.get("theory_understanding"), dict) else {}
    _require_zh_dict_list(
        errors,
        theory.get("key_equations"),
        theory_zh.get("key_equations"),
        "translations.zh.type_sections.theory_understanding.key_equations",
        ["label", "explanation"],
    )
    _require_zh_dict_list(
        errors,
        theory.get("theorem_or_principle_chain"),
        theory_zh.get("theorem_or_principle_chain"),
        "translations.zh.type_sections.theory_understanding.theorem_or_principle_chain",
        ["principle", "role", "intuition"],
    )

    survey = data.get("survey_understanding") if isinstance(data.get("survey_understanding"), dict) else {}
    survey_zh = type_sections_zh.get("survey_understanding") if isinstance(type_sections_zh.get("survey_understanding"), dict) else {}
    _require_zh_dict_list(
        errors,
        survey.get("method_family_matrix"),
        survey_zh.get("method_family_matrix"),
        "translations.zh.type_sections.survey_understanding.method_family_matrix",
        ["family", "core_idea", "strengths", "limitations", "best_for"],
    )

    dataset = data.get("dataset_benchmark_understanding")
    dataset_zh = type_sections_zh.get("dataset_benchmark_understanding")
    if isinstance(dataset, dict) and dataset.get("format") == "structured_v2":
        _require_zh_structured_dataset(errors, dataset, dataset_zh)

    _require_zh_availability(errors, data.get("availability"), zh.get("availability"))
    _require_zh_extraction_notes(errors, data.get("extraction_notes"), zh.get("extraction_notes"))
    return errors


def _require_zh_structured_dataset(errors: list[str], source: dict[str, Any], zh_value: Any) -> None:
    path = "translations.zh.type_sections.dataset_benchmark_understanding"
    if not isinstance(zh_value, dict):
        errors.append(f"missing zh translation: {path}")
        return
    row_fields = {
        "key_numbers": ["label", "context"],
        "construction_steps": ["stage", "action", "output", "quality_control"],
    }
    for section, fields in row_fields.items():
        source_rows = source.get(section)
        zh_rows = zh_value.get(section)
        section_path = f"{path}.{section}"
        if not isinstance(source_rows, list):
            continue
        if not isinstance(zh_rows, list) or len(zh_rows) != len(source_rows):
            errors.append(f"invalid zh translation structure: {section_path} must mirror {len(source_rows)} rows")
            continue
        for index, source_row in enumerate(source_rows):
            zh_row = zh_rows[index]
            if not isinstance(source_row, dict) or not isinstance(zh_row, dict):
                errors.append(f"invalid zh translation structure: {section_path}[{index}] must be an object")
                continue
            for field in fields:
                source_field = source_row.get(field)
                field_path = f"{section_path}[{index}].{field}"
                if isinstance(source_field, str) and source_field.strip():
                    translated = zh_row.get(field)
                    _require_zh_text(errors, translated, field_path, source_field)
                    if (
                        isinstance(translated, str)
                        and _english_word_count(source_field) >= 2
                        and _normalize_for_copy_check(source_field) == _normalize_for_copy_check(translated)
                        and not _copies_source_text(source_field, translated)
                    ):
                        errors.append(f"weak zh translation: {field_path} copies short English source text")
    _require_zh_sourced_list(
        errors,
        source.get("biases_or_limits"),
        zh_value.get("biases_or_limits"),
        f"{path}.biases_or_limits",
    )


def _validate_reader_facing_quality(data: dict[str, Any], source_map: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source_blocks = [item for item in source_map.get("blocks") or [] if isinstance(item, dict)]
    source_texts = [str(item.get("source_text") or "") for item in source_blocks]
    for path, text in _reader_facing_strings(data):
        lowered = text.lower()
        if any(term in text for term in PARSER_ARTIFACT_TERMS):
            errors.append(f"reader-facing text contains parser residue: {path}")
        if any(phrase in lowered for phrase in BAD_READER_PHRASES):
            errors.append(f"template-like reading prose: {path}")
        if any(phrase in lowered for phrase in INTERNAL_PROMPT_LEAK_PHRASES):
            errors.append(f"internal prompt text leaked into reader prose: {path}")
        if _is_section_name_only(text):
            errors.append(f"section-name-only reader text: {path}")
        if _too_close_to_source(text, source_texts):
            errors.append(f"reader-facing text copies source block instead of interpreting it: {path}")

    zh = ((data.get("translations") or {}).get("zh") or {}) if isinstance(data.get("translations"), dict) else {}
    for path, text in _reader_facing_strings(zh, prefix="translations.zh"):
        if any(term in text for term in PARSER_ARTIFACT_TERMS):
            errors.append(f"reader-facing zh text contains parser residue: {path}")
        if any(phrase in text for phrase in BAD_ZH_READER_PHRASES):
            errors.append(f"lazy zh translation: {path}")
        if any(phrase in text.lower() for phrase in INTERNAL_PROMPT_LEAK_PHRASES):
            errors.append(f"internal prompt text leaked into zh reader prose: {path}")
        if _is_section_name_only(text):
            errors.append(f"section-name-only reader text: {path}")
        if _looks_like_english_fallback(text):
            errors.append(f"weak zh translation: {path} is mostly English")
    errors.extend(_duplicate_zh_item_errors(zh))
    return errors


def _audit_generated_reading_artifacts(paper_dir: Path) -> list[str]:
    errors: list[str] = []
    for name in ["note.md", "note_zh.md", "reading_result.html"]:
        path = paper_dir / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lowered = text.lower()
        if ZH_MISSING_MARKER in text:
            errors.append(f"missing Chinese translation marker in generated artifact: {name}")
        for phrase in INTERNAL_PROMPT_LEAK_PHRASES:
            if phrase in lowered:
                errors.append(f"internal prompt text leaked into generated artifact: {name}")
                break
    return errors


def _source_map_granularity_warnings(source_map: dict[str, Any], paper_index: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    blocks = [item for item in source_map.get("blocks") or [] if isinstance(item, dict)]
    local_blocks = [item for item in blocks if str(item.get("source_kind") or "") != "external"]
    if len(local_blocks) < 4:
        warnings.append("source_map has fewer than four local evidence blocks; reading may be under-grounded")
    coverage = paper_index.get("coverage") if isinstance(paper_index.get("coverage"), dict) else {}
    parsed_pages = int(coverage.get("parsed_pages") or 0)
    pages = {item.get("page") for item in local_blocks if isinstance(item.get("page"), int)}
    if parsed_pages > 2 and pages and pages == {1}:
        warnings.append("source_map local evidence is all on page 1 despite a multi-page paper; check parser page granularity")
    kinds = {str(item.get("source_kind") or item.get("type") or "") for item in local_blocks}
    if not ({"body_text", "caption", "figure", "table", "equation"} & kinds):
        warnings.append("source_map lacks standard body/caption/visual/equation evidence kinds")
    return warnings


def _failed_quality_fields(errors: list[str]) -> list[str]:
    fields: list[str] = []
    for error in errors:
        if ": " not in error:
            continue
        field = error.rsplit(": ", 1)[-1]
        if field and field not in fields:
            fields.append(field)
    return fields


def _reader_facing_strings(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    skip_keys = {
        "authors",
        "active_lenses",
        "bibkey",
        "confidence",
        "crop_status",
        "doi",
        "equation",
        "higher_is_better",
        "image_path",
        "kind",
        "latex",
        "module_id",
        "openalex_id",
        "parsed_markdown_path",
        "pdf_path",
        "placement_section",
        "placed_near",
        "primary_type",
        "reading_quality",
        "role",
        "schema_version",
        "score",
        "source_map_path",
        "source_refs",
        "status",
        "study_type",
        "symbol",
        "type",
        "unit",
        "url",
        "value",
        "year",
    }
    results: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in skip_keys:
                continue
            path = f"{prefix}.{key}" if prefix else str(key)
            results.extend(_reader_facing_strings(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            results.extend(_reader_facing_strings(item, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        text = value.strip()
        if text and (len(text) >= 24 or _is_section_name_only(text) or _contains_quality_trigger(text)):
            results.append((prefix, text))
    return results


def _add_library_text(index: dict[str, dict[str, Any]], bibkey: str, path: str, text: str) -> None:
    normalized = _normalize_library_reader_text(text)
    if not normalized:
        return
    item = index.setdefault(normalized, {"text": text.strip(), "papers": set(), "paths": set()})
    item["papers"].add(bibkey)
    item["paths"].add(path)


def _library_audit_path_allowed(path: str) -> bool:
    normalized = re.sub(r"\[\d+\]", "[]", path)
    if normalized.startswith("translations.zh."):
        normalized = normalized[len("translations.zh.") :]
    allowed_prefixes = (
        "one_sentence_summary",
        "quick_read[]",
        "argument_map.",
        "central_claims[]",
        "method_understanding.",
        "theory_understanding.",
        "survey_understanding.",
        "dataset_benchmark_understanding.",
        "application_understanding.",
        "system_understanding.",
        "evaluation.main_results[]",
        "evaluation.ablation_or_comparison_takeaways[]",
        "evaluation.numeric_results[]",
        "visual_cards[]",
        "type_sections.",
    )
    return normalized.startswith(allowed_prefixes)


def _normalize_library_reader_text(text: str) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    if len(value) < 42:
        return ""
    lowered = value.lower()
    # Ignore common null availability statements; those can legitimately repeat.
    if lowered in {"not reported", "not specified", "unknown", "not available"}:
        return ""
    value = re.sub(r"\b[A-Z][A-Za-z]+(?:\d{4})?[A-Za-z]*\b", "<NAME>", value)
    value = re.sub(r"\b\d{4}\b", "<YEAR>", value)
    return value.lower()


def _contains_quality_trigger(text: str) -> bool:
    lowered = text.lower()
    if any(phrase in lowered for phrase in BAD_READER_PHRASES):
        return True
    if any(phrase in text for phrase in BAD_ZH_READER_PHRASES):
        return True
    return False


def _is_section_name_only(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.strip()).strip(" .:：#")
    lowered = normalized.lower()
    if not lowered:
        return False
    if lowered in SECTION_NAME_ONLY_TERMS:
        return True
    if re.fullmatch(r"(?:section|sec\.?)\s*\d+(?:\.\d+)*(?:\s*[:：-]\s*[a-z ]{2,40})?", lowered):
        return True
    if re.fullmatch(r"[a-z ]{2,40}\s+section", lowered) and any(term in lowered for term in SECTION_NAME_ONLY_TERMS):
        return True
    return bool(re.fullmatch(r"\d+(?:\.\d+)+", lowered))


def _too_close_to_source(text: str, source_texts: list[str]) -> bool:
    normalized = _norm_match_text(text)
    if len(normalized) < 120:
        return False
    for source in source_texts:
        source_norm = _norm_match_text(source)
        if not source_norm:
            continue
        if normalized[:160] in source_norm or source_norm[:220] in normalized:
            return True
        if len(normalized) >= 180 and _overlap_score(normalized, source_norm) >= 0.72:
            return True
    return False


def _looks_like_english_fallback(text: str) -> bool:
    if len(text) < 40:
        return False
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    english_words = _reader_english_word_count(text)
    return english_words >= 8 and english_words > max(cjk_count, 1) / 2


def _reader_english_word_count(value: str) -> int:
    ignored = {
        "bibtex",
        "deep",
        "html",
        "json",
        "markdown",
        "md",
        "note",
        "pdf",
        "reading",
        "refs",
        "result",
        "schema",
        "source",
        "source_map",
        "source_refs",
        "yaml",
        "yml",
    }
    words = re.findall(r"[A-Za-z][A-Za-z_.-]*", value)
    count = 0
    for word in words:
        lowered = word.strip("._-").lower()
        if "." in word or "_" in word or lowered in ignored:
            continue
        count += 1
    return count


def _duplicate_zh_item_errors(zh: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path, values in _zh_lists_for_duplicate_check(zh):
        normalized = [_normalize_zh_item(item) for item in values]
        normalized = [item for item in normalized if item]
        if len(normalized) >= 3 and len(set(normalized)) <= max(1, len(normalized) // 2):
            errors.append(f"lazy zh translation: {path} repeats generic items")
    return errors


def _zh_lists_for_duplicate_check(value: Any, prefix: str = "translations.zh") -> list[tuple[str, list[Any]]]:
    results: list[tuple[str, list[Any]]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}"
            if isinstance(item, list):
                results.append((path, item))
            results.extend(_zh_lists_for_duplicate_check(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            results.extend(_zh_lists_for_duplicate_check(item, f"{prefix}[{index}]"))
    return results


def _normalize_zh_item(value: Any) -> str:
    text = _zh_value_text(value)
    text = re.sub(r"要点\d+|流程\d+|第\d+个", "", text)
    return re.sub(r"\s+", "", text.strip())


def _require_zh_text(errors: list[str], value: Any, path: str, source: Any = None) -> None:
    if isinstance(value, dict):
        value = value.get("text")
    if not isinstance(value, str) or not value.strip():
        errors.append(f"missing zh translation: {path}")
        return
    source_text = _reader_text(source)
    if _needs_real_zh(source_text, value):
        errors.append(f"weak zh translation: {path} must be Chinese, not an English fallback")
    if _copies_source_text(source_text, value):
        errors.append(f"weak zh translation: {path} copies English source text")


def _reader_text(value: Any, field: str = "text") -> str:
    if isinstance(value, dict):
        for key in [field, "claim", "evidence_summary", "what_it_proves", "what_it_does_not_prove", "open_question"]:
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key].strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _english_word_count(value: str) -> int:
    return len(re.findall(r"[A-Za-z]{2,}", value))


def _normalize_for_copy_check(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _needs_real_zh(source_text: str, zh_text: str) -> bool:
    if not source_text or _contains_cjk(zh_text):
        return False
    return len(source_text) >= 40 or _english_word_count(source_text) >= 4


def _copies_source_text(source_text: str, zh_text: str) -> bool:
    if not source_text:
        return False
    if len(source_text) < 40 and _english_word_count(source_text) < 4:
        return False
    return _normalize_for_copy_check(source_text) == _normalize_for_copy_check(zh_text)


def _source_has_text(value: Any, field: str = "text") -> bool:
    if isinstance(value, dict):
        return isinstance(value.get(field), str) and bool(value[field].strip())
    return isinstance(value, str) and bool(value.strip())


def _require_zh_for_sourced_text(errors: list[str], source: Any, zh_value: Any, path: str) -> None:
    if _source_has_text(source):
        _require_zh_text(errors, zh_value, path, source)


def _require_zh_sourced_list(errors: list[str], source: Any, zh_value: Any, path: str) -> None:
    if not isinstance(source, list) or not source:
        return
    if not isinstance(zh_value, list):
        errors.append(f"missing zh translation: {path}")
        return
    for index, item in enumerate(source):
        if _source_has_text(item):
            zh_item = zh_value[index] if index < len(zh_value) else None
            _require_zh_text(errors, zh_item, f"{path}[{index}]", item)


def _require_zh_dict_list(
    errors: list[str],
    source: Any,
    zh_value: Any,
    path: str,
    fields: list[str],
) -> None:
    if not isinstance(source, list) or not source:
        return
    if not isinstance(zh_value, list):
        errors.append(f"missing zh translation: {path}")
        return
    for index, item in enumerate(source):
        if not isinstance(item, dict):
            continue
        zh_item = zh_value[index] if index < len(zh_value) and isinstance(zh_value[index], dict) else {}
        for field in fields:
            if _source_has_text(item, field):
                _require_zh_text(errors, zh_item.get(field), f"{path}[{index}].{field}", item.get(field))


def _require_zh_section(errors: list[str], source: dict[str, Any], zh_value: dict[str, Any], path: str) -> None:
    for key, item in source.items():
        child_path = f"{path}.{key}"
        zh_item = zh_value.get(key)
        if isinstance(item, list):
            _require_zh_sourced_list(errors, item, zh_item, child_path)
        elif isinstance(item, dict) and "text" in item:
            _require_zh_for_sourced_text(errors, item, zh_item, child_path)
        elif isinstance(item, dict):
            nested_zh = zh_item if isinstance(zh_item, dict) else {}
            _require_zh_section(errors, item, nested_zh, child_path)
        elif isinstance(item, str) and item.strip():
            _require_zh_text(errors, zh_item, child_path, item)


def _require_zh_availability(errors: list[str], source: Any, zh_value: Any) -> None:
    if not isinstance(source, dict):
        return
    zh = zh_value if isinstance(zh_value, dict) else {}
    for key in ["code", "data", "models"]:
        item = source.get(key) if isinstance(source.get(key), dict) else {}
        zh_item = zh.get(key) if isinstance(zh.get(key), dict) else {}
        for field in ["evidence", "notes"]:
            if _source_has_text(item, field):
                _require_zh_text(errors, zh_item.get(field), f"translations.zh.availability.{key}.{field}", item.get(field))


def _require_zh_extraction_notes(errors: list[str], source: Any, zh_value: Any) -> None:
    if not isinstance(source, dict):
        return
    zh = zh_value if isinstance(zh_value, dict) else {}
    for key, values in source.items():
        if not isinstance(values, list) or not values:
            continue
        zh_values = zh.get(key)
        if not isinstance(zh_values, list):
            errors.append(f"missing zh translation: translations.zh.extraction_notes.{key}")
            continue
        for index, value in enumerate(values):
            if isinstance(value, str) and value.strip():
                zh_item = zh_values[index] if index < len(zh_values) else None
                _require_zh_text(errors, zh_item, f"translations.zh.extraction_notes.{key}[{index}]", value)


def _page_from_image_path(value: str) -> int | None:
    match = re.search(r"page-(\d{3,})", value)
    return int(match.group(1)) if match else None


def _visual_ref_pages(refs: Any, block_index: dict[str, dict[str, Any]]) -> set[int]:
    pages: set[int] = set()
    for ref in refs:
        block = block_index.get(_source_ref_block_id(str(ref)))
        if not block:
            continue
        kind = str(block.get("source_kind") or block.get("type") or "").lower()
        if kind in {"caption", "figure", "table", "visual"} and isinstance(block.get("page"), int):
            pages.add(int(block["page"]))
    return pages


def _has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


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


def _source_ref_block_id(ref: str) -> str:
    match = SOURCE_REF_RE.search(str(ref))
    if match:
        return match.group(0)
    return str(ref).split()[0].split("/")[0]


def rebuild_note(root: str | Path, bibkey: str) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    paper_dir = paths.paper_dir(bibkey)
    report_path = paper_dir / "deep_read.json"
    if not report_path.exists():
        return {"ok": False, "error": f"missing deep_read.json for {bibkey}"}
    check = validate_deep_read_report(root, bibkey)
    if not check["ok"]:
        return check
    data = json.loads(report_path.read_text(encoding="utf-8"))
    source_map = json.loads((paper_dir / SOURCE_MAP_NAME).read_text(encoding="utf-8"))
    source_index = _source_index(source_map)
    profile = data["paper_profile"]
    method = data["method_understanding"]
    evaluation = data["evaluation"]

    lines = [
        f"# {data['title']}",
        "",
        f"BibTeX: `{bibkey}`",
        "",
        f"Profile: {profile['primary_type']} | lenses: {', '.join(profile['active_lenses'])}",
        "",
        "## Summary",
        data["one_sentence_summary"],
    ]
    _append_sourced_items(lines, "Quick Read", data["quick_read"], source_index)

    argument = data["argument_map"]
    lines.extend(["", "## Argument Map"])
    _append_sourced_text(lines, "Gap", argument["gap"], source_index)
    _append_sourced_text(lines, "Core contribution", argument["core_contribution"], source_index)
    _append_sourced_text(lines, "Method logic", argument["method_logic"], source_index)
    _append_sourced_items(lines, "Decisive Evidence", argument["decisive_evidence"], source_index)
    _append_sourced_items(lines, "Limitations", argument["limitations"], source_index)
    _append_sourced_items(lines, "Future Work", argument["future_work"], source_index)

    lines.extend(["", "## Central Claims"])
    for item in data["central_claims"]:
        lines.append(f"- Claim: {item['claim']}")
        lines.append(f"  - Evidence: {item['evidence_summary']}")
        lines.append(f"  - {_source_refs_text(item, source_index)}")
        lines.append(f"  - What it proves: {item['what_it_proves']}")
        lines.append(f"  - What it does not prove: {item['what_it_does_not_prove']}")
        lines.append(f"  - Open question: {item['open_question']}")

    lines.extend(["", "## Method Understanding"])
    _append_sourced_items(lines, "Pipeline", method["pipeline"], source_index)
    steps = method.get("algorithm_steps") or []
    if steps:
        lines.extend(["", "## Algorithm Steps"])
        for item in steps:
            lines.append(f"- Step {item['step']}: {item['action']}")
            if item.get("inputs"):
                lines.append(f"  - Inputs: {item['inputs']}")
            if item.get("outputs"):
                lines.append(f"  - Outputs: {item['outputs']}")
            lines.append(f"  - {_source_refs_text(item, source_index)}")
    lines.extend(["", "## Engineering Derivation Sketch", method["engineering_derivation_sketch"]["text"]])
    refs = _source_refs_text(method["engineering_derivation_sketch"], source_index)
    if refs:
        lines.append(f"\n{refs}")
    _append_sourced_items(lines, "Implementation Details", method["implementation_details"], source_index)

    _append_type_section(lines, "Theory Understanding", data.get("theory_understanding"), source_index)
    dataset_section = data.get("dataset_benchmark_understanding")
    if isinstance(dataset_section, dict) and dataset_section.get("format") == "structured_v2":
        _append_structured_dataset_tables(lines, "Dataset / Benchmark Understanding", dataset_section, source_index)
    else:
        _append_type_section(lines, "Dataset / Benchmark Understanding", dataset_section, source_index)
    _append_type_section(lines, "Survey Understanding", data.get("survey_understanding"), source_index)
    _append_type_section(lines, "Application Understanding", data.get("application_understanding"), source_index)
    _append_type_section(lines, "System / Tooling Understanding", data.get("system_understanding"), source_index)

    lines.extend(["", "## Evaluation"])
    _append_sourced_items(lines, "Datasets", evaluation["datasets"], source_index)
    _append_sourced_items(lines, "Metrics", evaluation["metrics"], source_index)
    _append_sourced_items(lines, "Main Results", evaluation["main_results"], source_index)
    _append_sourced_items(lines, "Ablation / Comparison Takeaways", evaluation["ablation_or_comparison_takeaways"], source_index)
    if evaluation.get("numeric_results"):
        lines.extend(["", "### Numeric Results"])
        for item in evaluation["numeric_results"]:
            parts = [
                str(item.get("dataset_or_task") or "task"),
                str(item.get("metric") or "metric"),
                f"{item.get('value')}{item.get('unit') or ''}",
            ]
            if item.get("baseline"):
                parts.append(f"baseline: {item['baseline']}")
            if item.get("comparison"):
                parts.append(f"comparison: {item['comparison']}")
            lines.append(f"- {' | '.join(parts)}")
            lines.append(f"  - Interpretation: {item.get('interpretation', '')}")
            lines.append(f"  - Does not prove: {item.get('what_it_does_not_prove', '')}")
            lines.append(f"  - {_source_refs_text(item, source_index)}")

    lines.extend(["", "## Visual Cards"])
    for item in data["visual_cards"]:
        lines.append(f"- {item['label']} ({item['kind']}, page {item['page']}, {item['crop_status']})")
        if item.get("image_path"):
            lines.append(f"  - Image: {item['image_path']}")
        if item.get("placeholder_reason"):
            lines.append(f"  - Placeholder: {item['placeholder_reason']}")
        lines.append(f"  - Placement section: {item.get('placement_section', '')}")
        lines.append(f"  - Placed near: {item['placed_near']}")
        lines.append(f"  - Caption: {item['source_caption']}")
        lines.append(f"  - Reading note: {item['reading_note']}")
        lines.append(f"  - {_source_refs_text(item, source_index)}")

    lines.extend(["", "## Availability"])
    for label, item in data["availability"].items():
        detail = item.get("url") or item.get("notes") or ""
        lines.append(f"- {label}: {item['status']} - {item['evidence']}" + (f" ({detail})" if detail else ""))

    lines.extend(["", "## Extraction Notes"])
    for key, values in data["extraction_notes"].items():
        lines.append(f"- {key.replace('_', ' ').title()}: " + ("; ".join(values) if values else "none"))
    note_path = paper_dir / "note.md"
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    zh_note_path = paper_dir / "note_zh.md"
    zh_note_path.write_text(_build_zh_note(data, bibkey, source_index), encoding="utf-8")
    return {"ok": True, "note": str(note_path.relative_to(paths.root)), "note_zh": str(zh_note_path.relative_to(paths.root))}


def _append_plain_items(lines: list[str], title: str, values: Any) -> None:
    if not values:
        return
    lines.extend(["", f"### {title}"])
    for value in values:
        lines.append(f"- {value}")


def _build_zh_note(data: dict[str, Any], bibkey: str, source_index: dict[str, dict[str, Any]]) -> str:
    zh = ((data.get("translations") or {}).get("zh") or {}) if isinstance(data.get("translations"), dict) else {}
    argument = data.get("argument_map") if isinstance(data.get("argument_map"), dict) else {}
    argument_zh = zh.get("argument_map") if isinstance(zh.get("argument_map"), dict) else {}
    method = data.get("method_understanding") if isinstance(data.get("method_understanding"), dict) else {}
    method_zh = zh.get("method_understanding") if isinstance(zh.get("method_understanding"), dict) else {}
    evaluation = data.get("evaluation") if isinstance(data.get("evaluation"), dict) else {}
    evaluation_zh = zh.get("evaluation") if isinstance(zh.get("evaluation"), dict) else {}
    lines = [
        f"# {data['title']}",
        "",
        f"BibTeX: `{bibkey}`",
        "",
        "## 总结",
        str(zh.get("one_sentence_summary") or data.get("one_sentence_summary") or ""),
    ]
    quick = zh.get("quick_read") if isinstance(zh.get("quick_read"), list) else []
    if quick:
        lines.extend(["", "## 快速阅读"])
        _append_zh_list(lines, quick, data.get("quick_read"), source_index)

    lines.extend(["", "## 论证地图"])
    _append_zh_sourced_text(lines, "问题缺口", argument_zh.get("gap"), argument.get("gap"), source_index)
    _append_zh_sourced_text(lines, "核心贡献", argument_zh.get("core_contribution"), argument.get("core_contribution"), source_index)
    _append_zh_sourced_text(lines, "方法逻辑", argument_zh.get("method_logic"), argument.get("method_logic"), source_index)
    _append_zh_list(lines, argument_zh.get("decisive_evidence"), argument.get("decisive_evidence"), source_index, "关键证据")
    _append_zh_list(lines, argument_zh.get("limitations"), argument.get("limitations"), source_index, "局限性")
    _append_zh_list(lines, argument_zh.get("future_work"), argument.get("future_work"), source_index, "未来工作")

    claims = zh.get("central_claims") if isinstance(zh.get("central_claims"), list) else []
    if claims:
        lines.extend(["", "## 核心论点"])
        for index, item in enumerate(claims):
            source_item = (data.get("central_claims") or [])[index] if index < len(data.get("central_claims") or []) else {}
            lines.append(f"- 主张：{item.get('claim', '')}")
            if item.get("evidence_summary"):
                lines.append(f"  - 证据：{item['evidence_summary']}")
            if item.get("what_it_proves"):
                lines.append(f"  - 证明了什么：{item['what_it_proves']}")
            if item.get("what_it_does_not_prove"):
                lines.append(f"  - 不能证明什么：{item['what_it_does_not_prove']}")
            if item.get("open_question"):
                lines.append(f"  - 开放问题：{item['open_question']}")
            if source_item:
                lines.append(f"  - {_source_refs_text(source_item, source_index)}")
    pipeline = method_zh.get("pipeline") if isinstance(method_zh.get("pipeline"), list) else []
    if pipeline or method_zh.get("engineering_derivation_sketch") or method_zh.get("implementation_details"):
        lines.extend(["", "## 方法理解"])
        _append_zh_list(lines, pipeline, method.get("pipeline"), source_index, "流程")
    steps = method_zh.get("algorithm_steps") if isinstance(method_zh.get("algorithm_steps"), list) else []
    if steps:
        lines.extend(["", "### 算法步骤"])
        source_steps = (data.get("method_understanding") or {}).get("algorithm_steps") or []
        for index, item in enumerate(steps):
            source_item = source_steps[index] if index < len(source_steps) else {}
            lines.append(f"- Step {index + 1}: {item.get('action', '')}")
            if item.get("inputs"):
                lines.append(f"  - 输入：{item['inputs']}")
            if item.get("outputs"):
                lines.append(f"  - 输出：{item['outputs']}")
            lines.append(f"  - {_source_refs_text(source_item, source_index)}")
    if method_zh.get("engineering_derivation_sketch"):
        lines.extend(["", "### 工程化推导理解", _zh_value_text(method_zh["engineering_derivation_sketch"])])
        if method.get("engineering_derivation_sketch"):
            lines.append(f"\n{_source_refs_text(method['engineering_derivation_sketch'], source_index)}")
    _append_zh_list(lines, method_zh.get("implementation_details"), method.get("implementation_details"), source_index, "实现细节")

    type_sections = zh.get("type_sections") if isinstance(zh.get("type_sections"), dict) else {}
    _append_zh_type_section(lines, "理论理解", data.get("theory_understanding"), type_sections.get("theory_understanding"), source_index)
    dataset_section = data.get("dataset_benchmark_understanding")
    dataset_zh = type_sections.get("dataset_benchmark_understanding")
    if isinstance(dataset_section, dict) and dataset_section.get("format") == "structured_v2":
        _append_zh_structured_dataset_tables(lines, dataset_section, dataset_zh, source_index)
    else:
        _append_zh_type_section(lines, "数据集/基准理解", dataset_section, dataset_zh, source_index)
    _append_zh_type_section(lines, "综述理解", data.get("survey_understanding"), type_sections.get("survey_understanding"), source_index)
    _append_zh_type_section(lines, "应用理解", data.get("application_understanding"), type_sections.get("application_understanding"), source_index)
    _append_zh_type_section(lines, "系统/工具理解", data.get("system_understanding"), type_sections.get("system_understanding"), source_index)

    if evaluation_zh:
        lines.extend(["", "## 实验评估"])
        _append_zh_list(lines, evaluation_zh.get("datasets"), evaluation.get("datasets"), source_index, "数据集")
        _append_zh_list(lines, evaluation_zh.get("metrics"), evaluation.get("metrics"), source_index, "指标")
        _append_zh_list(lines, evaluation_zh.get("main_results"), evaluation.get("main_results"), source_index, "主要结果")
        _append_zh_list(lines, evaluation_zh.get("ablation_or_comparison_takeaways"), evaluation.get("ablation_or_comparison_takeaways"), source_index, "消融/对比结论")
        numeric = evaluation_zh.get("numeric_results") if isinstance(evaluation_zh.get("numeric_results"), list) else []
        source_numeric = evaluation.get("numeric_results") if isinstance(evaluation.get("numeric_results"), list) else []
        if numeric:
            lines.extend(["", "### 关键数值结果"])
            for index, item in enumerate(numeric):
                source_item = source_numeric[index] if index < len(source_numeric) else {}
                parts = [
                    str(item.get("dataset_or_task") or ""),
                    str(item.get("metric") or ""),
                    f"{source_item.get('value')}{source_item.get('unit') or ''}" if isinstance(source_item, dict) else "",
                ]
                lines.append(f"- {' | '.join(part for part in parts if part)}")
                if item.get("interpretation"):
                    lines.append(f"  - 解读：{item['interpretation']}")
                if item.get("what_it_does_not_prove"):
                    lines.append(f"  - 不能证明什么：{item['what_it_does_not_prove']}")
                if source_item:
                    lines.append(f"  - {_source_refs_text(source_item, source_index)}")

    visuals = zh.get("visual_cards") if isinstance(zh.get("visual_cards"), list) else []
    source_visuals = data.get("visual_cards") if isinstance(data.get("visual_cards"), list) else []
    if visuals:
        lines.extend(["", "## 图表卡片"])
        for index, item in enumerate(visuals):
            source_item = source_visuals[index] if index < len(source_visuals) else {}
            page = source_item.get("page") if isinstance(source_item, dict) else ""
            lines.append(f"- {item.get('label', '')}（第 {page} 页）")
            if item.get("source_caption"):
                lines.append(f"  - 图注：{item['source_caption']}")
            if item.get("reading_note"):
                lines.append(f"  - 阅读提示：{item['reading_note']}")
            if source_item:
                lines.append(f"  - {_source_refs_text(source_item, source_index)}")

    availability_zh = zh.get("availability") if isinstance(zh.get("availability"), dict) else {}
    if availability_zh:
        lines.extend(["", "## 可用性"])
        source_availability = data.get("availability") if isinstance(data.get("availability"), dict) else {}
        for key, label in [("code", "代码"), ("data", "数据"), ("models", "模型")]:
            item = availability_zh.get(key) if isinstance(availability_zh.get(key), dict) else {}
            source_item = source_availability.get(key) if isinstance(source_availability.get(key), dict) else {}
            if item or source_item:
                status = source_item.get("status") or "unknown"
                detail = item.get("evidence") or item.get("notes") or ""
                lines.append(f"- {label}: {status} - {detail}")
                if source_item:
                    lines.append(f"  - {_source_refs_text(source_item, source_index)}")

    extraction_zh = zh.get("extraction_notes") if isinstance(zh.get("extraction_notes"), dict) else {}
    if extraction_zh:
        lines.extend(["", "## 提取质量说明"])
        for key, values in extraction_zh.items():
            label = str(key).replace("_", " ")
            lines.append(f"- {label}: " + ("; ".join(str(value) for value in values) if values else "无"))
    return "\n".join(lines) + "\n"


def _zh_value_text(value: Any) -> str:
    if isinstance(value, dict):
        text = value.get("text") or value.get("claim") or value.get("evidence_summary")
        if text:
            return str(text)
        return " | ".join(
            str(item)
            for key, item in value.items()
            if key not in {"source_refs", "confidence"}
            and isinstance(item, (str, int, float))
            and str(item).strip()
        )
    return str(value or "")


def _append_zh_sourced_text(
    lines: list[str],
    label: str,
    zh_value: Any,
    source_value: Any,
    source_index: dict[str, dict[str, Any]],
) -> None:
    text = _zh_value_text(zh_value)
    if not text:
        return
    lines.append(f"- {label}: {text}")
    if source_value:
        lines.append(f"  - {_source_refs_text(source_value, source_index)}")


def _append_zh_list(
    lines: list[str],
    zh_values: Any,
    source_values: Any,
    source_index: dict[str, dict[str, Any]],
    title: str | None = None,
) -> None:
    if not isinstance(zh_values, list) or not zh_values:
        return
    if title:
        lines.extend(["", f"### {title}"])
    source_list = source_values if isinstance(source_values, list) else []
    for index, item in enumerate(zh_values):
        text = _zh_value_text(item)
        if not text:
            continue
        lines.append(f"- {text}")
        source_item = source_list[index] if index < len(source_list) else {}
        if source_item:
            lines.append(f"  - {_source_refs_text(source_item, source_index)}")


def _append_zh_type_section(
    lines: list[str],
    title: str,
    source_section: Any,
    zh_section: Any,
    source_index: dict[str, dict[str, Any]],
) -> None:
    if not isinstance(source_section, dict) or not source_section or not isinstance(zh_section, dict):
        return
    lines.extend(["", f"## {title}"])
    for key, source_value in source_section.items():
        zh_value = zh_section.get(key)
        label = str(key).replace("_", " ")
        if isinstance(zh_value, list):
            _append_zh_list(lines, zh_value, source_value, source_index, label)
        elif isinstance(zh_value, dict):
            text = _zh_value_text(zh_value)
            if text:
                lines.append(f"- {label}: {text}")
                if isinstance(source_value, dict):
                    refs = _source_refs_text(source_value, source_index)
                    if refs:
                        lines.append(f"  - {refs}")
            elif any(key not in {"source_refs", "confidence"} and isinstance(item, list) for key, item in zh_value.items()):
                lines.extend(["", f"### {label}"])
                for child_key, child_value in zh_value.items():
                    if child_key in {"source_refs", "confidence"}:
                        continue
                    _append_zh_list(lines, child_value, source_value.get(child_key) if isinstance(source_value, dict) else None, source_index, str(child_key).replace("_", " "))
        elif isinstance(zh_value, str) and zh_value.strip():
            lines.append(f"- {label}: {zh_value}")


def _append_type_section(
    lines: list[str],
    title: str,
    value: Any,
    source_index: dict[str, dict[str, Any]] | None = None,
) -> None:
    if not isinstance(value, dict) or not value:
        return
    lines.extend(["", f"## {title}"])
    for key, item in value.items():
        label = str(key).replace("_", " ").title()
        if isinstance(item, list):
            _append_sourced_items(lines, label, item, source_index)
        elif isinstance(item, dict) and "text" in item:
            _append_sourced_text(lines, label, item, source_index)
        elif item:
            lines.append(f"- {label}: {item}")


def _markdown_cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", "<br>")


def _append_markdown_table(lines: list[str], headers: list[str], rows: list[list[Any]]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(_markdown_cell(value) for value in row) + " |")


def _dataset_refs(row: dict[str, Any], source_index: dict[str, dict[str, Any]]) -> str:
    value = _source_refs_text(row, source_index)
    return value.removeprefix("Evidence: ")


def _append_structured_dataset_tables(
    lines: list[str],
    title: str,
    section: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
) -> None:
    lines.extend(["", f"## {title}", "", "### Key Numbers"])
    _append_markdown_table(
        lines,
        ["Label", "Value", "Unit", "Context", "Source refs"],
        [[row["label"], row["value"], row.get("unit", ""), row["context"], _dataset_refs(row, source_index)] for row in section["key_numbers"]],
    )
    lines.extend(["", "### Construction Steps"])
    _append_markdown_table(
        lines,
        ["Stage", "Action", "Output", "Quality control", "Source refs"],
        [[row["stage"], row["action"], row["output"], row.get("quality_control", ""), _dataset_refs(row, source_index)] for row in section["construction_steps"]],
    )
    lines.extend(["", "### Biases Or Limits"])
    _append_markdown_table(
        lines,
        ["Bias or limit", "Source refs"],
        [[row["text"], _dataset_refs(row, source_index)] for row in section["biases_or_limits"]],
    )


def _append_zh_structured_dataset_tables(
    lines: list[str],
    source: dict[str, Any],
    zh_value: Any,
    source_index: dict[str, dict[str, Any]],
) -> None:
    if not isinstance(zh_value, dict):
        return
    lines.extend(["", "## 数据集/基准理解", "", "### 关键数字"])
    key_rows = []
    for index, row in enumerate(zh_value.get("key_numbers") or []):
        source_row = source["key_numbers"][index]
        key_rows.append([row["label"], source_row["value"], source_row.get("unit", ""), row["context"], _dataset_refs(source_row, source_index)])
    _append_markdown_table(lines, ["名称", "数值", "单位", "说明", "来源"], key_rows)
    lines.extend(["", "### 构建步骤"])
    step_rows = []
    for index, row in enumerate(zh_value.get("construction_steps") or []):
        source_row = source["construction_steps"][index]
        step_rows.append([row["stage"], row["action"], row["output"], row.get("quality_control", ""), _dataset_refs(source_row, source_index)])
    _append_markdown_table(lines, ["阶段", "操作", "输出", "质量控制", "来源"], step_rows)
    lines.extend(["", "### 偏差与局限"])
    limit_rows = []
    for index, row in enumerate(zh_value.get("biases_or_limits") or []):
        source_row = source["biases_or_limits"][index]
        limit_rows.append([_zh_value_text(row), _dataset_refs(source_row, source_index)])
    _append_markdown_table(lines, ["偏差或局限", "来源"], limit_rows)


def _source_index(source_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id")): item
        for item in source_map.get("blocks") or []
        if isinstance(item, dict) and item.get("id")
    }


def _source_label(ref: str, source_index: dict[str, dict[str, Any]]) -> str:
    block = source_index.get(_source_ref_block_id(ref))
    if not block:
        return ref
    section = str(block.get("section") or "paper").strip()
    page = block.get("page")
    kind = str(block.get("source_kind") or block.get("type") or "source").replace("_", " ")
    if isinstance(page, int):
        return f"{section}, p.{page} ({kind})"
    return f"{section} ({kind})"
