from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "paper-engine-one-page-v1"


def prepare_one_page(pdf: str | Path, work_dir: str | Path) -> dict[str, Any]:
    """Extract bounded, page-addressable evidence for a one-page reading."""
    pdf_path = _pdf_path(pdf)
    output_dir = Path(work_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pages, metadata = _read_pdf_pages(pdf_path)
    parsed = []
    page_index = []
    for number, text in enumerate(pages, start=1):
        parsed.extend((f"\n<!-- page:{number} -->\n", text.strip(), "\n"))
        page_index.append(
            {
                "page": number,
                "characters": len(text),
                "head": _collapse(text)[:240],
            }
        )
    (output_dir / "parsed.md").write_text("\n".join(parsed), encoding="utf-8")
    index = {
        "schema_version": SCHEMA_VERSION,
        "pdf": str(pdf_path),
        "page_count": len(pages),
        "metadata": metadata,
        "pages": page_index,
    }
    (output_dir / "page_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "ok": True,
        "pdf": str(pdf_path),
        "page_count": len(pages),
        "parsed": str(output_dir / "parsed.md"),
        "page_index": str(output_dir / "page_index.json"),
    }


def build_one_page(
    pdf: str | Path,
    content: str | Path,
    output: str | Path,
) -> dict[str, Any]:
    """Validate an evidence-backed brief and render a standalone one-page HTML file."""
    pdf_path = _pdf_path(pdf)
    content_path = Path(content).expanduser().resolve()
    data = json.loads(content_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("one-page content must be a JSON object")
    pages, metadata = _read_pdf_pages(pdf_path)
    _validate_content(data, pages, content_dir=content_path.parent)
    rendered_visuals = [
        {**item, "data_url": _visual_data_url(pdf_path, item, content_dir=content_path.parent)}
        for item in data.get("results", {}).get("visuals", [])
    ]
    document = _render_html(data, rendered_visuals, metadata)
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return {
        "ok": True,
        "output": str(output_path),
        "page_count": len(pages),
        "visual_count": len(rendered_visuals),
        "schema_version": data["schema_version"],
    }


def _pdf_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"PDF not found: {path}")
    return path


def _read_pdf_pages(pdf_path: Path) -> tuple[list[str], dict[str, Any]]:
    fitz = _import_pymupdf()
    with fitz.open(pdf_path) as document:
        return [page.get_text() for page in document], dict(document.metadata or {})


def _import_pymupdf():
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz  # type: ignore[no-redef]
        except ImportError as exc:
            raise RuntimeError(
                "one-page reading requires PyMuPDF; install the project dependencies first"
            ) from exc
    return fitz


def _validate_content(
    data: dict[str, Any], pages: list[str], content_dir: Path | None = None
) -> None:
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    for key in ("paper", "contribution", "model", "results", "reproduction"):
        if not isinstance(data.get(key), dict):
            raise ValueError(f"missing object: {key}")
    if not str(data["paper"].get("title") or "").strip():
        raise ValueError("paper.title is required")
    required_lists = (
        ("contribution", "core_contributions"),
        ("contribution", "core_conclusions"),
        ("model", "governing_equations"),
        ("results", "key_findings"),
        ("results", "visuals"),
        ("reproduction", "workflow"),
    )
    for section, field in required_lists:
        value = data[section].get(field)
        if not isinstance(value, list) or not value:
            raise ValueError(f"{section}.{field} must be a non-empty list")
    evidence = data.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("evidence must be a non-empty list")
    evidence_ids: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("each evidence item must be an object")
        evidence_id = str(item.get("id") or "")
        page = int(item.get("page") or 0)
        quote = str(item.get("quote") or "").strip()
        if not re.fullmatch(r"[SCFM]\d{3}", evidence_id):
            raise ValueError(f"invalid evidence id: {evidence_id}")
        if evidence_id in evidence_ids:
            raise ValueError(f"duplicate evidence id: {evidence_id}")
        if not 1 <= page <= len(pages):
            raise ValueError(f"evidence {evidence_id} has invalid page {page}")
        if quote and _collapse(quote).lower() not in _collapse(pages[page - 1]).lower():
            raise ValueError(f"evidence {evidence_id} quote was not found on page {page}")
        evidence_ids.add(evidence_id)
    refs = _collect_source_refs(data)
    unknown = sorted(refs - evidence_ids)
    if unknown:
        raise ValueError(f"unknown source_refs: {', '.join(unknown)}")
    for visual in data["results"]["visuals"]:
        artifact = str(visual.get("path") or "").strip()
        if artifact:
            artifact_path = Path(artifact).expanduser()
            if not artifact_path.is_absolute() and content_dir is not None:
                artifact_path = content_dir / artifact_path
            artifact_path = artifact_path.resolve()
            if not artifact_path.is_file():
                raise ValueError(f"visual artifact not found: {artifact_path}")
            if artifact_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                raise ValueError(f"unsupported visual artifact: {artifact_path.suffix}")
            continue
        page = int(visual.get("page") or 0)
        crop = visual.get("crop")
        if not 1 <= page <= len(pages):
            raise ValueError(f"visual has invalid page {page}")
        if not isinstance(crop, list) or len(crop) != 4:
            raise ValueError("visual.crop must contain four normalized coordinates")
        x0, y0, x1, y1 = (float(value) for value in crop)
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("visual.crop coordinates must satisfy 0 <= x0 < x1 <= 1")


def _collect_source_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source_refs" and isinstance(child, list):
                refs.update(str(item) for item in child)
            else:
                refs.update(_collect_source_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.update(_collect_source_refs(child))
    return refs


def _visual_data_url(
    pdf_path: Path, visual: dict[str, Any], content_dir: Path | None = None
) -> str:
    artifact = str(visual.get("path") or "").strip()
    if artifact:
        artifact_path = Path(artifact).expanduser()
        if not artifact_path.is_absolute() and content_dir is not None:
            artifact_path = content_dir / artifact_path
        artifact_path = artifact_path.resolve()
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }[artifact_path.suffix.lower()]
        payload = base64.b64encode(artifact_path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{payload}"
    fitz = _import_pymupdf()
    page_number = int(visual["page"])
    x0, y0, x1, y1 = (float(value) for value in visual["crop"])
    with fitz.open(pdf_path) as document:
        page = document[page_number - 1]
        rect = page.rect
        clip = fitz.Rect(
            rect.x0 + rect.width * x0,
            rect.y0 + rect.height * y0,
            rect.x0 + rect.width * x1,
            rect.y0 + rect.height * y1,
        )
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
        payload = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
    return f"data:image/png;base64,{payload}"


def _render_html(data: dict[str, Any], visuals: list[dict[str, Any]], metadata: dict[str, Any]) -> str:
    paper = data["paper"]
    contribution = data["contribution"]
    model = data["model"]
    results = data["results"]
    evidence = {item["id"]: item for item in data["evidence"]}

    def esc(value: Any) -> str:
        return html.escape(str(value or ""))

    def refs(items: Any) -> str:
        labels = []
        for ref in items or []:
            item = evidence.get(ref, {})
            labels.append(f'<span class="ref" title="{esc(item.get("note") or item.get("quote"))}">{esc(ref)} · p.{esc(item.get("page"))}</span>')
        return "".join(labels)

    def bullets(items: list[dict[str, Any]]) -> str:
        return "".join(
            f'<li><span>{esc(item.get("text"))}</span>{refs(item.get("source_refs"))}</li>'
            for item in items
        )

    equations = "".join(
        '<article class="equation">'
        f'<div class="eq-name">{esc(item.get("label"))}{refs(item.get("source_refs"))}</div>'
        f'<div class="formula">{esc(item.get("equation"))}</div>'
        f'<p>{esc(item.get("meaning"))}</p>'
        '</article>'
        for item in model["governing_equations"]
    )
    workflow = "".join(
        '<li class="flow-step">'
        f'<b>{index:02d}</b><div><strong>{esc(item.get("title"))}</strong>'
        f'<p>{esc(item.get("text"))}{refs(item.get("source_refs"))}</p></div>'
        '</li>'
        for index, item in enumerate(data["reproduction"]["workflow"], start=1)
    )
    visual_html = "".join(
        '<figure>'
        f'<img src="{item["data_url"]}" alt="{esc(item.get("label"))}">'
        f'<figcaption><strong>{esc(item.get("label"))}</strong> {esc(item.get("caption"))}{refs(item.get("source_refs"))}</figcaption>'
        '</figure>'
        for item in visuals
    )
    limitations = data.get("limitations") or []
    limitations_html = bullets(limitations) if limitations else ""
    citation = paper.get("citation") or metadata.get("title") or ""
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(paper["title"])}｜PaperEngine 单页解读</title>
<style>
@page {{ size: A4 landscape; margin: 7mm; }}
* {{ box-sizing:border-box }}
:root {{ --ink:#182126; --muted:#5e6a70; --line:#cbd5d8; --a:#0f766e; --b:#b45309; --paper:#f7f3e9; }}
body {{ margin:0; background:#dfe5e6; color:var(--ink); font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif; }}
.sheet {{ width:min(297mm,calc(100vw - 24px)); min-height:210mm; margin:12px auto; padding:7mm 8mm 6mm; background:var(--paper); box-shadow:0 12px 40px #6674; overflow:visible; }}
header {{ display:grid; grid-template-columns:1fr auto; gap:12mm; align-items:end; border-bottom:2px solid var(--ink); padding-bottom:3mm; }}
.kicker {{ color:var(--a); font-weight:800; letter-spacing:.14em; font-size:8.5pt; }}
h1 {{ margin:1mm 0; font-family:Georgia,"Noto Serif CJK SC",serif; font-size:18pt; line-height:1.08; }}
.citation {{ margin:0; color:var(--muted); font-size:7.7pt; }}
.verdict {{ max-width:88mm; padding:3mm 4mm; background:#17383a; color:white; font:700 10pt/1.42 Georgia,"Noto Serif CJK SC",serif; }}
.grid {{ display:grid; grid-template-columns:minmax(0,23fr) minmax(0,35fr) minmax(0,42fr); gap:3.5mm; padding-top:3.5mm; }}
section {{ min-width:0; }}
section+section {{ border-left:1px solid var(--line); padding-left:3.5mm; }}
h2 {{ display:flex; align-items:baseline; gap:1.5mm; margin:0 0 2mm; font:800 11.5pt/1.1 Georgia,"Noto Serif CJK SC",serif; }}
h2 b {{ color:var(--b); font:900 14pt/1 sans-serif; }}
h3 {{ margin:2mm 0 .8mm; color:var(--a); font-size:7.2pt; letter-spacing:.07em; text-transform:uppercase; }}
ul {{ margin:0; padding-left:4mm; }} li {{ margin:0 0 1.25mm; font-size:7.25pt; line-height:1.38; }}
.ref {{ display:inline-block; margin-left:1mm; color:#75634e; border-bottom:1px dotted #9b8970; font:600 6.4pt/1.2 monospace; white-space:nowrap; }}
.framework {{ margin:0 0 1.5mm; padding:1.8mm 2.3mm; background:#e8efeb; font-size:7.2pt; line-height:1.35; }}
.equation {{ margin:0 0 1.3mm; padding:1.2mm 2mm; border-left:2px solid var(--a); background:#fff9; }}
.eq-name {{ font-size:7pt; font-weight:800; color:var(--muted); }}
.formula {{ margin:.5mm 0; font:italic 8.2pt/1.25 Georgia,"Times New Roman",serif; white-space:pre-wrap; overflow-wrap:anywhere; }}
.equation p {{ margin:0; font-size:6.55pt; line-height:1.28; }}
.visuals {{ display:grid; grid-template-columns:1fr; gap:1.2mm; margin-top:1.5mm; }}
figure {{ margin:0; min-width:0; }} img {{ display:block; width:100%; height:54mm; object-fit:contain; background:white; border:1px solid var(--line); }}
figcaption {{ margin-top:1mm; font-size:6.5pt; line-height:1.32; color:#39464b; }}
.boundary {{ margin-top:2.5mm; padding-top:2mm; border-top:1px solid var(--line); }}
.flow {{ list-style:none; padding:0; margin:0; }}
.reproduction {{ grid-column:1/-1; border-left:0!important; border-top:1px solid var(--line); padding:3mm 0 0!important; }}
.reproduction .framework {{ margin-bottom:2mm; }}
.reproduction .flow {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:3mm; }}
.flow-step {{ display:grid; grid-template-columns:6mm 1fr; gap:1.3mm; margin:0; min-width:0; }}
.flow-step>b {{ display:grid; place-items:center; width:5.5mm; height:5.5mm; border-radius:50%; background:var(--a); color:white; font-size:6.2pt; }}
.flow-step strong {{ font-size:7.15pt; }}
.flow-step p {{ margin:.3mm 0 0; font-size:6.55pt; line-height:1.29; }}
footer {{ display:flex; justify-content:space-between; margin-top:2mm; color:var(--muted); font-size:6.2pt; }}
@media print {{ body {{ background:white }} .sheet {{ margin:0; box-shadow:none; height:196mm; }} }}
@media (max-width:1050px) {{ .sheet {{ width:calc(100vw - 16px); min-height:auto; margin:8px }} .grid {{ grid-template-columns:1fr }} section+section {{ border-left:0; border-top:1px solid var(--line); padding:4mm 0 0 }} .reproduction {{ grid-column:auto }} .reproduction .flow {{ grid-template-columns:1fr }} img {{ height:auto; max-height:72vh }} }}
</style></head><body><main class="sheet">
<header><div><div class="kicker">PAPERENGINE · ONE-PAGE DEEP READ</div><h1>{esc(paper["title"])}</h1><p class="citation">{esc(citation)}</p></div><div class="verdict">{esc(contribution.get("one_sentence"))}</div></header>
<div class="grid">
<section><h2><b>01</b> 核心贡献与结论</h2><h3>核心贡献</h3><ul>{bullets(contribution["core_contributions"])}</ul><h3>核心结论</h3><ul>{bullets(contribution["core_conclusions"])}</ul>{f'<div class="boundary"><h3>适用边界</h3><ul>{limitations_html}</ul></div>' if limitations_html else ''}</section>
<section><h2><b>02</b> 模型与本构方程</h2><p class="framework">{esc(model.get("framework"))}{refs(model.get("source_refs"))}</p>{equations}</section>
<section><h2><b>03</b> 最核心结果 / 图表</h2><ul>{bullets(results["key_findings"])}</ul><div class="visuals">{visual_html}</div></section>
<section class="reproduction"><h2><b>04</b> COMSOL 最小复现</h2><p class="framework">{esc(data["reproduction"].get("goal"))}{refs(data["reproduction"].get("source_refs"))}</p><ol class="flow">{workflow}</ol></section>
</div><footer><span>证据标签可回溯到 PDF 页码；悬停可查看原文锚点。</span><span>Generated by PaperEngine · {esc(data.get("generated_on"))}</span></footer>
</main></body></html>'''


def _collapse(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
