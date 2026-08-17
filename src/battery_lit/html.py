from __future__ import annotations

import base64
import json
import os
import html as html_lib
import mimetypes
import re
from pathlib import Path
from typing import Any

from markupsafe import Markup
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .bib import parse_bibtex
from .candidates import load_candidates
from .paths import TopicPaths, repo_root
from .topic import load_topic


READING_RESULT_NAME = "reading_result.html"
ZH_MISSING = "【中文翻译缺失】"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(repo_root() / "templates" / "html")),
        autoescape=select_autoescape(["html"]),
    )


def _papers(root: str | Path) -> list[dict[str, Any]]:
    paths = TopicPaths.from_root(root)
    papers: list[dict[str, Any]] = []
    for entry in parse_bibtex(paths.library_bib):
        bibkey = entry["bibkey"]
        paper_dir = paths.paper_dir(bibkey)
        detail_page = f"papers/{bibkey}/{READING_RESULT_NAME}"
        meta = {}
        if (paper_dir / "metadata.yml").exists():
            meta = yaml.safe_load((paper_dir / "metadata.yml").read_text(encoding="utf-8")) or {}
        report = _load_json(paper_dir / "deep_read.json")
        papers.append(
            {
                "bibkey": bibkey,
                "title": meta.get("title") or entry.get("title") or bibkey,
                "year": meta.get("year") or entry.get("year") or "",
                "venue": meta.get("venue") or entry.get("journal") or "unknown",
                "authors": meta.get("authors") or entry.get("author") or [],
                "authors_text": _authors_text(meta.get("authors") or entry.get("author") or []),
                "citation_authors": _author_names(meta.get("authors") or entry.get("author") or []),
                "doi": meta.get("doi") or entry.get("doi"),
                "arxiv_id": meta.get("arxiv_id") or entry.get("eprint"),
                "has_pdf": (paper_dir / "paper.pdf").exists(),
                "has_note": (paper_dir / "note.md").exists(),
                "detail_href": f"../{detail_page}",
                "css_href": "../../html/style.css",
                "nav_dashboard_href": "../../html/dashboard.html",
                "nav_candidates_href": "../../html/candidates.html",
                "nav_library_href": "../../html/library.html",
                "pdf_href": _existing_link(paths.root, detail_page, f"papers/{bibkey}/paper.pdf"),
                "note_href": _existing_link(paths.root, detail_page, f"papers/{bibkey}/note.md"),
                "report": _report_view(report, paths.root, detail_page),
                "has_report": bool(report),
                "assets": _asset_views(paths.root, detail_page, paper_dir, report),
                "bibtex": _format_bibtex_entry(entry),
            }
        )
    return papers


def _authors_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    text = str(value or "")
    return text.replace(" and ", ", ")


def _author_names(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.replace("\n", " ").split(" and ") if part.strip()]


def _format_bibtex_entry(entry: dict[str, Any]) -> str:
    bibkey = entry.get("bibkey") or "unknown"
    fields = [(key, value) for key, value in entry.items() if key != "bibkey" and value not in (None, "")]
    rendered = "\n".join(f"  {key} = {{{value}}}," for key, value in fields)
    return f"@article{{{bibkey},\n{rendered}\n}}"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _report_view(report: dict[str, Any] | None, root: Path, current_page: str) -> dict[str, Any]:
    if not report:
        return {}
    view = dict(report)
    source_map_rel = str(report.get("source_map_path") or "").strip()
    source_index = _source_index(_load_json(root / source_map_rel) if source_map_rel else None)
    zh = _zh(report)
    view["reading_quality"] = _reading_quality_view(report.get("reading_quality"))
    view["one_sentence_summary_zh"] = _zh_text(zh.get("one_sentence_summary"), report.get("one_sentence_summary"))
    view["availability_rows"] = _availability_rows(report.get("availability"), zh.get("availability"))
    view["profile_badges"] = _profile_badges(report.get("paper_profile"))
    view["argument_rows"] = _argument_rows(report.get("argument_map"), source_index, zh.get("argument_map"))
    view["quick_read"] = [
        _sourced_item_view(item, source_index, _list_item(zh.get("quick_read"), index))
        for index, item in enumerate(report.get("quick_read") or [])
    ]
    view["central_claims"] = [
        _claim_view(item, source_index, _list_item(zh.get("central_claims"), index))
        for index, item in enumerate(report.get("central_claims") or [])
    ]
    view["method"] = _method_view(report.get("method_understanding"), source_index, zh.get("method_understanding"))
    view["math_core"] = _math_core_view(report.get("theory_understanding"), source_index, root, current_page, _type_zh(zh, "theory_understanding"))
    view["survey_map"] = _survey_map_view(report.get("survey_understanding"), source_index, _type_zh(zh, "survey_understanding"))
    view["dataset_report"] = _dataset_report_view(
        report.get("dataset_benchmark_understanding"),
        source_index,
        _type_zh(zh, "dataset_benchmark_understanding"),
    )
    view["evaluation"] = _evaluation_view(report.get("evaluation"), source_index, zh.get("evaluation"))
    view["visual_cards"] = [
        _visual_card_view(item, root, current_page, source_index, _list_item(zh.get("visual_cards"), index))
        for index, item in enumerate(report.get("visual_cards") or [])
    ]
    view["visual_cards_by_section"] = _visual_cards_by_section(view["visual_cards"])
    view["skim"] = _skim_view(report, view, source_index, zh)
    view["type_sections"] = _type_section_views(report, source_index, zh.get("type_sections"))
    view["extraction_rows"] = _extraction_rows(report.get("extraction_notes"), zh.get("extraction_notes"))
    return view


def _reading_quality_view(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"accepted_with_limitations": False, "issues": [], "warnings": [], "cycles_used": ""}
    status = str(value.get("status") or "")
    return {
        "accepted_with_limitations": status == "accepted_with_limitations",
        "reason": str(value.get("acceptance_reason") or ""),
        "cycles_used": str(value.get("cycles_used") or ""),
        "issues": [str(item) for item in value.get("open_issues") or [] if str(item).strip()],
        "warnings": [str(item) for item in value.get("controller_warnings") or [] if str(item).strip()],
    }


def _zh(report: dict[str, Any]) -> dict[str, Any]:
    translations = report.get("translations") if isinstance(report.get("translations"), dict) else {}
    zh = translations.get("zh") if isinstance(translations.get("zh"), dict) else {}
    return zh


def _profile_badges(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    badges: list[str] = []
    if value.get("primary_type"):
        badges.append(str(value["primary_type"]))
    badges.extend(str(item) for item in value.get("active_lenses") or [] if str(item).strip())
    return list(dict.fromkeys(badges))


def _skim_view(
    report: dict[str, Any],
    view: dict[str, Any],
    source_index: dict[str, dict[str, Any]],
    zh: dict[str, Any],
) -> dict[str, Any]:
    _ = source_index
    skim = report.get("skim") if isinstance(report.get("skim"), dict) else {}
    skim_zh = zh.get("skim") if isinstance(zh.get("skim"), dict) else {}

    why = skim.get("why_it_matters") or _sourced_text(report.get("argument_map", {}).get("core_contribution"))
    remember_items = [item.get("text") for item in report.get("quick_read") or [] if isinstance(item, dict) and item.get("text")]
    remember = skim.get("what_to_remember") or "; ".join(remember_items[:2])
    if not remember and report.get("central_claims"):
        first_claim = report["central_claims"][0]
        if isinstance(first_claim, dict):
            remember = str(first_claim.get("claim") or "")
    deep = skim.get("should_read_deeply") or _should_read_deeply(report)
    highlights = [
        {
            "text": str(item.get("display_label") or item.get("label") or ""),
            "text_zh": str(item.get("display_label_zh") or item.get("display_label") or item.get("label") or ""),
            "meta": str(item.get("source_refs") or ""),
        }
        for item in view.get("visual_cards", [])[:3]
        if item.get("display_label") or item.get("label")
    ]
    if not highlights:
        highlights = [{"text": "No decisive visual highlight extracted.", "text_zh": "未提取到关键图表高亮。", "meta": ""}]

    return {
        "summary": str(skim.get("summary") or report.get("one_sentence_summary") or ""),
        "summary_zh": str(skim_zh.get("summary") or zh.get("one_sentence_summary") or report.get("one_sentence_summary") or ""),
        "why_it_matters": str(why or ""),
        "why_it_matters_zh": str(skim_zh.get("why_it_matters") or why or ""),
        "what_to_remember": str(remember or ""),
        "what_to_remember_zh": str(skim_zh.get("what_to_remember") or remember or ""),
        "should_read_deeply": str(deep or ""),
        "should_read_deeply_zh": str(skim_zh.get("should_read_deeply") or deep or ""),
        "key_visual_highlights": highlights,
    }


def _sourced_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or value.get("claim") or value.get("evidence_summary") or "")
    return str(value or "")


def _should_read_deeply(report: dict[str, Any]) -> str:
    profile = report.get("paper_profile") if isinstance(report.get("paper_profile"), dict) else {}
    types = [str(item) for item in profile.get("active_lenses") or [] if str(item).strip()]
    if types:
        return f"Read deeply if you need the paper's {', '.join(types[:3])} details; otherwise skim the claims, method, and evaluation sections."
    return "Read deeply if this paper looks central to the topic; otherwise use the skim layer and central claims first."


def _availability_rows(value: Any, zh_value: Any = None) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return []
    zh = zh_value if isinstance(zh_value, dict) else {}
    rows: list[dict[str, str]] = []
    for label, label_zh, key in [("Code", "代码", "code"), ("Data", "数据", "data"), ("Models", "模型", "models")]:
        item = value.get(key) if isinstance(value.get(key), dict) else {}
        zh_item = zh.get(key) if isinstance(zh.get(key), dict) else {}
        details = [str(item.get(name) or "").strip() for name in ["evidence", "url", "notes"]]
        details_zh = [
            _zh_text(zh_item.get("evidence"), item.get("evidence")).strip(),
            str(item.get("url") or "").strip(),
            _zh_text(zh_item.get("notes"), item.get("notes")).strip(),
        ]
        status = str(item.get("status") or "unknown")
        rows.append(
            {
                "label": label,
                "label_zh": label_zh,
                "status": status,
                "status_zh": _status_zh(status),
                "detail": " | ".join(part for part in details if part),
                "detail_zh": " | ".join(part for part in details_zh if part),
            }
        )
    return rows


def _status_zh(value: str) -> str:
    return {
        "available": "可用",
        "unknown": "未知",
        "not_found": "未找到",
        "not_applicable": "不适用",
        "restricted": "受限",
    }.get(value, value)


def _sourced_item_view(
    value: Any,
    source_index: dict[str, dict[str, Any]] | None = None,
    zh_value: Any = None,
) -> dict[str, str]:
    if isinstance(value, dict):
        refs = [str(ref) for ref in value.get("source_refs") or []]
        confidence = str(value.get("confidence") or "")
        evidence = _evidence_labels(refs, source_index or {})
        meta = " | ".join(part for part in [f"Evidence: {evidence}" if evidence else "", f"confidence: {confidence}" if confidence else ""] if part)
        return {"text": str(value.get("text") or ""), "text_zh": _zh_text(zh_value, value.get("text")), "meta": meta, "source_refs": ", ".join(refs)}
    return {"text": str(value), "text_zh": _zh_text(zh_value, value), "meta": ""}


def _claim_view(value: Any, source_index: dict[str, dict[str, Any]], zh_value: Any = None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"claim": str(value), "evidence": "", "proves": "", "does_not_prove": "", "open_question": "", "source_refs": ""}
    zh = zh_value if isinstance(zh_value, dict) else {}
    return {
        "claim": str(value.get("claim") or ""),
        "claim_zh": _zh_text(zh.get("claim"), value.get("claim")),
        "evidence": str(value.get("evidence_summary") or ""),
        "evidence_zh": _zh_text(zh.get("evidence_summary"), value.get("evidence_summary")),
        "proves": str(value.get("what_it_proves") or ""),
        "proves_zh": _zh_text(zh.get("what_it_proves"), value.get("what_it_proves")),
        "does_not_prove": str(value.get("what_it_does_not_prove") or ""),
        "does_not_prove_zh": _zh_text(zh.get("what_it_does_not_prove"), value.get("what_it_does_not_prove")),
        "open_question": str(value.get("open_question") or ""),
        "open_question_zh": _zh_text(zh.get("open_question"), value.get("open_question")),
        "source_refs": _evidence_labels([str(ref) for ref in value.get("source_refs") or []], source_index),
    }


def _argument_rows(value: Any, source_index: dict[str, dict[str, Any]], zh_value: Any = None) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return []
    zh = zh_value if isinstance(zh_value, dict) else {}
    rows: list[dict[str, str]] = []
    for label, key in [("Gap", "gap"), ("Core contribution", "core_contribution"), ("Method logic", "method_logic")]:
        if isinstance(value.get(key), dict):
            row = _sourced_item_view(value[key], source_index, zh.get(key))
            row["label"] = label
            row["label_zh"] = _label_zh(label)
            rows.append(row)
    for label, key in [("Decisive evidence", "decisive_evidence"), ("Limitations", "limitations"), ("Future work", "future_work")]:
        zh_items = zh.get(key)
        for index, item in enumerate(value.get(key) or []):
            row = _sourced_item_view(item, source_index, _list_item(zh_items, index))
            row["label"] = label
            row["label_zh"] = _label_zh(label)
            rows.append(row)
    return rows


def _method_view(value: Any, source_index: dict[str, dict[str, Any]], zh_value: Any = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"pipeline": [], "algorithm_steps": [], "pseudocode": "", "derivation": {}, "implementation_details": []}
    zh = zh_value if isinstance(zh_value, dict) else {}
    return {
        "pipeline": [
            _sourced_item_view(item, source_index, _list_item(zh.get("pipeline"), index))
            for index, item in enumerate(value.get("pipeline") or [])
        ],
        "algorithm_steps": _algorithm_steps_view(value.get("algorithm_steps"), source_index, zh.get("algorithm_steps")),
        "pseudocode": _format_pseudocode(value.get("algorithm_pseudocode")),
        "derivation": _sourced_item_view(value.get("engineering_derivation_sketch"), source_index, zh.get("engineering_derivation_sketch")),
        "implementation_details": [
            _sourced_item_view(item, source_index, _list_item(zh.get("implementation_details"), index))
            for index, item in enumerate(value.get("implementation_details") or [])
        ],
    }


def _evaluation_view(value: Any, source_index: dict[str, dict[str, Any]], zh_value: Any = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"datasets": [], "metrics": [], "main_results": [], "ablation_or_comparison_takeaways": [], "numeric_results": []}
    zh = zh_value if isinstance(zh_value, dict) else {}
    view = {
        key: [
            _sourced_item_view(item, source_index, _list_item(zh.get(key), index))
            for index, item in enumerate(value.get(key) or [])
        ]
        for key in ["datasets", "metrics", "main_results", "ablation_or_comparison_takeaways"]
    }
    view["numeric_results"] = [
        _numeric_result_view(item, source_index, _list_item(zh.get("numeric_results"), index))
        for index, item in enumerate(value.get("numeric_results") or [])
    ]
    return view


def _numeric_result_view(value: Any, source_index: dict[str, dict[str, Any]], zh_value: Any = None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"task": str(value), "metric": "", "value": "", "comparison": "", "interpretation": "", "does_not_prove": "", "source_refs": ""}
    zh = zh_value if isinstance(zh_value, dict) else {}
    comparison_parts = [str(value.get("baseline") or "").strip(), str(value.get("comparison") or "").strip()]
    return {
        "task": str(value.get("dataset_or_task") or ""),
        "task_zh": _zh_text(zh.get("dataset_or_task"), value.get("dataset_or_task")),
        "metric": str(value.get("metric") or ""),
        "metric_zh": _zh_text(zh.get("metric"), value.get("metric")),
        "value": f"{value.get('value')}{value.get('unit') or ''}",
        "comparison": " -> ".join(part for part in comparison_parts if part),
        "interpretation": str(value.get("interpretation") or ""),
        "interpretation_zh": _zh_text(zh.get("interpretation"), value.get("interpretation")),
        "does_not_prove": str(value.get("what_it_does_not_prove") or ""),
        "does_not_prove_zh": _zh_text(zh.get("what_it_does_not_prove"), value.get("what_it_does_not_prove")),
        "source_refs": _evidence_labels([str(ref) for ref in value.get("source_refs") or []], source_index),
    }


def _visual_card_view(
    value: Any,
    root: Path,
    current_page: str,
    source_index: dict[str, dict[str, Any]],
    zh_value: Any = None,
) -> dict[str, str | None]:
    if not isinstance(value, dict):
        return {"label": str(value), "crop_status": "unknown", "page": "", "reading_note": "", "image_href": None}
    zh = zh_value if isinstance(zh_value, dict) else {}
    image_path = str(value.get("image_path") or "").strip()
    image_href: str | None = None
    if image_path:
        local = root / image_path
        if local.exists():
            image_href = _link(current_page, image_path)
    crop_status = str(value.get("crop_status") or "unknown")
    page = str(value.get("page") or "")
    label = str(value.get("label") or "visual")
    label_zh = _zh_text(zh.get("label"), label)
    return {
        "label": label,
        "label_zh": label_zh,
        "display_label": f"Page {page} view containing {label}" if crop_status == "full_page_approximate" and page else label,
        "display_label_zh": f"第 {page} 页视图，包含 {label_zh}" if crop_status == "full_page_approximate" and page else label_zh,
        "kind": str(value.get("kind") or ""),
        "crop_status": crop_status,
        "page": page,
        "image_path": image_path,
        "image_href": image_href,
        "placeholder_reason": str(value.get("placeholder_reason") or ""),
        "placeholder_reason_zh": _placeholder_reason_zh(zh.get("placeholder_reason"), value.get("placeholder_reason")),
        "source_caption": str(value.get("source_caption") or ""),
        "source_caption_zh": _zh_text(zh.get("source_caption"), value.get("source_caption")),
        "placement_section": str(value.get("placement_section") or ""),
        "placed_near": str(value.get("placed_near") or ""),
        "reading_note": str(value.get("reading_note") or ""),
        "reading_note_zh": _zh_text(zh.get("reading_note"), value.get("reading_note")),
        "source_refs": _evidence_labels([str(ref) for ref in value.get("source_refs") or []], source_index),
    }


def _placeholder_reason_zh(value: Any, fallback: Any = "") -> str:
    text = _zh_text(value, "")
    if text:
        return text
    reason = str(fallback or "").strip()
    if not reason:
        return ""
    lowered = reason.lower()
    if "page labels collapse" in lowered or "no tight crop" in lowered:
        return "解析页码或裁剪信息不够可靠，因此这里使用整页近似视图作为定位参考。"
    if "no image" in lowered or "missing image" in lowered:
        return "未找到可可靠展示的图像文件。"
    return "未选择精确裁剪；该图表仅作为页面级定位参考。"


def _visual_cards_by_section(cards: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        key = str(card.get("placement_section") or "")
        if key:
            grouped.setdefault(key, []).append(card)
    return grouped


def _type_zh(zh: dict[str, Any], key: str) -> dict[str, Any]:
    sections = zh.get("type_sections") if isinstance(zh.get("type_sections"), dict) else {}
    return sections.get(key) if isinstance(sections.get(key), dict) else {}


def _math_core_view(value: Any, source_index: dict[str, dict[str, Any]], root: Path, current_page: str, zh_value: Any = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"has_content": False, "problem": {}, "equations": [], "chain": [], "derivation": {}, "missing": "No theory section extracted.", "missing_zh": "未提取理论部分。"}
    zh = zh_value if isinstance(zh_value, dict) else {}
    problem = _sourced_item_view(value.get("problem_formulation"), source_index, zh.get("problem_formulation")) if value.get("problem_formulation") else {}
    equations = [
        _equation_view(item, source_index, root, current_page, _list_item(zh.get("key_equations"), index))
        for index, item in enumerate(value.get("key_equations") or [])
    ]
    chain = [
        _theorem_chain_view(item, source_index, _list_item(zh.get("theorem_or_principle_chain"), index))
        for index, item in enumerate(value.get("theorem_or_principle_chain") or [])
    ]
    derivation = _sourced_item_view(value.get("engineering_proof_sketch"), source_index, zh.get("engineering_proof_sketch")) if value.get("engineering_proof_sketch") else {}
    has_content = bool(problem or equations or chain or derivation)
    return {
        "has_content": has_content,
        "problem": problem,
        "equations": equations,
        "chain": chain,
        "derivation": derivation,
        "missing": "" if has_content else "No key equations or theorem chain extracted.",
        "missing_zh": "" if has_content else "未提取关键公式或定理链。",
    }


def _equation_view(value: Any, source_index: dict[str, dict[str, Any]], root: Path, current_page: str, zh_value: Any = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"label": str(value), "label_zh": str(value), "equation": "", "equation_mathml": "", "explanation": "", "explanation_zh": "", "source_refs": "", "source_images": []}
    zh = zh_value if isinstance(zh_value, dict) else {}
    refs = [str(ref) for ref in value.get("source_refs") or []]
    equation = str(value.get("equation") or "")
    latex = str(value.get("latex") or "").strip()
    return {
        "label": str(value.get("label") or ""),
        "label_zh": _zh_text(zh.get("label"), value.get("label")),
        "equation": equation,
        "equation_mathml": _equation_mathml(latex or equation),
        "explanation": str(value.get("explanation") or ""),
        "explanation_zh": _zh_text(zh.get("explanation"), value.get("explanation")),
        "source_refs": _evidence_labels(refs, source_index),
        "source_images": _source_image_links(refs, source_index, root, current_page),
    }


def _equation_mathml(value: str) -> Markup | str:
    expression = _formula_expression(value)
    if not expression:
        return ""
    rows = []
    for part in expression.splitlines():
        part = part.strip()
        if part:
            rows.append(f"<mrow>{''.join(_mathml_tokens(part))}</mrow>")
    if not rows:
        return ""
    return Markup('<math xmlns="http://www.w3.org/1998/Math/MathML" display="block">' + "".join(rows) + "</math>")


def _formula_expression(value: str) -> str:
    text = value.strip().strip("$")
    if not text:
        return ""
    text = text.replace("\\\\", "\\")
    text = re.sub(r"\\begin\{[^}]+\}|\\end\{[^}]+\}", "", text)
    text = re.sub(r"\b(for|where|when|with)\b.*$", "", text, flags=re.IGNORECASE).strip()
    return text[:600]


def _mathml_tokens(expression: str) -> list[str]:
    expression = expression.replace("<=", "≤").replace(">=", "≥").replace("->", "→")
    pieces = re.findall(r"\\[A-Za-z]+(?:_[A-Za-z0-9]+)?(?:\^[A-Za-z0-9]+)?|[A-Za-z]+(?:_[A-Za-z0-9]+)?(?:\^[A-Za-z0-9]+)?|\d+(?:\.\d+)?|[≤≥=+\-*/(),]|[^\s]", expression)
    return [_mathml_piece(piece) for piece in pieces]


def _mathml_piece(piece: str) -> str:
    greek = {
        "alpha": "α",
        "beta": "β",
        "gamma": "γ",
        "lambda": "λ",
        "mu": "μ",
        "tau": "τ",
        "theta": "θ",
        "sigma": "σ",
        "phi": "φ",
    }
    latex_ops = {"le": "≤", "ge": "≥", "rightarrow": "→", "to": "→", "dot": "˙", "min": "min", "max": "max"}
    if piece.startswith("\\"):
        name = piece[1:]
        if "_" in name or "^" in name:
            return _mathml_piece(name)
        if name in greek:
            return f"<mi>{greek[name]}</mi>"
        if name in latex_ops:
            token = latex_ops[name]
            tag = "mo" if token in {"≤", "≥", "→", "˙"} else "mi"
            return f"<{tag}>{html_lib.escape(token)}</{tag}>"
        return f"<mi>{html_lib.escape(name)}</mi>"
    if piece in {"=", "+", "-", "*", "/", "(", ")", ",", "≤", "≥", "→"}:
        return f"<mo>{html_lib.escape(piece)}</mo>"
    if re.fullmatch(r"\d+(?:\.\d+)?", piece):
        return f"<mn>{piece}</mn>"
    base = piece
    sub = sup = None
    if "^" in base:
        base, sup = base.split("^", 1)
    if "_" in base:
        base, sub = base.split("_", 1)
    base_node = f"<mi>{html_lib.escape(_math_identifier(base))}</mi>"
    if sub and sup:
        return f"<msubsup>{base_node}<mi>{html_lib.escape(_math_identifier(sub))}</mi><mi>{html_lib.escape(_math_identifier(sup))}</mi></msubsup>"
    if sub:
        return f"<msub>{base_node}<mi>{html_lib.escape(_math_identifier(sub))}</mi></msub>"
    if sup:
        return f"<msup>{base_node}<mi>{html_lib.escape(_math_identifier(sup))}</mi></msup>"
    return base_node


def _math_identifier(value: str) -> str:
    return {
        "lambda": "λ",
        "mu": "μ",
        "tau": "τ",
        "xdot": "ẋ",
        "x_dot": "ẋ",
        "dtau": "dτ",
    }.get(value, value)


def _source_image_links(refs: list[str], source_index: dict[str, dict[str, Any]], root: Path, current_page: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for ref in refs:
        block = source_index.get(_source_ref_block_id(ref))
        if not block:
            continue
        image_path = str(block.get("image_path") or "").strip()
        if not image_path:
            continue
        if (root / image_path).exists():
            links.append({"label": _source_label(ref, source_index), "href": _link(current_page, image_path)})
    return links


def _theorem_chain_view(value: Any, source_index: dict[str, dict[str, Any]], zh_value: Any = None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"principle": str(value), "principle_zh": str(value), "role": "", "role_zh": "", "intuition": "", "intuition_zh": "", "source_refs": ""}
    zh = zh_value if isinstance(zh_value, dict) else {}
    return {
        "principle": str(value.get("principle") or ""),
        "principle_zh": _zh_text(zh.get("principle"), value.get("principle")),
        "role": str(value.get("role") or ""),
        "role_zh": _zh_text(zh.get("role"), value.get("role")),
        "intuition": str(value.get("intuition") or ""),
        "intuition_zh": _zh_text(zh.get("intuition"), value.get("intuition")),
        "source_refs": _evidence_labels([str(ref) for ref in value.get("source_refs") or []], source_index),
    }


def _survey_map_view(value: Any, source_index: dict[str, dict[str, Any]], zh_value: Any = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"has_content": False, "matrix": [], "timeline": [], "missing": "No survey map extracted.", "missing_zh": "未提取综述地图。"}
    zh = zh_value if isinstance(zh_value, dict) else {}
    matrix = [
        _method_family_view(item, source_index, _list_item(zh.get("method_family_matrix"), index))
        for index, item in enumerate(value.get("method_family_matrix") or [])
    ]
    timeline = [
        _timeline_view(item, source_index, _list_item(zh.get("timeline_milestones"), index))
        for index, item in enumerate(value.get("timeline_milestones") or [])
    ]
    has_content = bool(matrix or timeline)
    return {
        "has_content": has_content,
        "matrix": matrix,
        "timeline": timeline,
        "missing": "" if has_content else "No method-family matrix or timeline extracted.",
        "missing_zh": "" if has_content else "未提取方法族矩阵或时间线。",
    }


def _method_family_view(value: Any, source_index: dict[str, dict[str, Any]], zh_value: Any = None) -> dict[str, str]:
    if not isinstance(value, dict):
        return {"family": str(value), "family_zh": str(value), "core_idea": "", "core_idea_zh": "", "strengths": "", "strengths_zh": "", "limitations": "", "limitations_zh": "", "best_for": "", "best_for_zh": "", "source_refs": ""}
    zh = zh_value if isinstance(zh_value, dict) else {}
    return {
        "family": str(value.get("family") or ""),
        "family_zh": _zh_text(zh.get("family"), value.get("family")),
        "core_idea": str(value.get("core_idea") or ""),
        "core_idea_zh": _zh_text(zh.get("core_idea"), value.get("core_idea")),
        "strengths": str(value.get("strengths") or ""),
        "strengths_zh": _zh_text(zh.get("strengths"), value.get("strengths")),
        "limitations": str(value.get("limitations") or ""),
        "limitations_zh": _zh_text(zh.get("limitations"), value.get("limitations")),
        "best_for": str(value.get("best_for") or ""),
        "best_for_zh": _zh_text(zh.get("best_for"), value.get("best_for")),
        "source_refs": _evidence_labels([str(ref) for ref in value.get("source_refs") or []], source_index),
    }


def _timeline_view(value: Any, source_index: dict[str, dict[str, Any]], zh_value: Any = None) -> dict[str, str]:
    row = _sourced_item_view(value, source_index, zh_value)
    text = row.get("text", "")
    head, sep, tail = text.partition(":")
    if not sep and " - " in text:
        head, sep, tail = text.partition(" - ")
    return {
        "time": head.strip() if sep else "",
        "time_zh": head.strip() if sep else "",
        "text": tail.strip() if sep else text,
        "text_zh": row.get("text_zh", tail.strip() if sep else text),
        "meta": row.get("meta", ""),
    }


def _dataset_report_view(
    value: Any,
    source_index: dict[str, dict[str, Any]],
    zh_value: Any = None,
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("format") != "structured_v2":
        return {"is_structured_v2": False, "key_numbers": [], "construction_steps": [], "biases_or_limits": []}

    zh = zh_value if isinstance(zh_value, dict) else {}
    key_numbers = []
    for index, item in enumerate(value.get("key_numbers") or []):
        if not isinstance(item, dict):
            continue
        item_zh = _list_item(zh.get("key_numbers"), index)
        item_zh = item_zh if isinstance(item_zh, dict) else {}
        key_numbers.append(
            {
                "label": str(item.get("label") or ""),
                "label_zh": _zh_text(item_zh.get("label"), item.get("label")),
                "value": str(item.get("value") or ""),
                "unit": str(item.get("unit") or ""),
                "context": str(item.get("context") or ""),
                "context_zh": _zh_text(item_zh.get("context"), item.get("context")),
                "source_refs": _evidence_labels([str(ref) for ref in item.get("source_refs") or []], source_index),
            }
        )

    construction_steps = []
    for index, item in enumerate(value.get("construction_steps") or []):
        if not isinstance(item, dict):
            continue
        item_zh = _list_item(zh.get("construction_steps"), index)
        item_zh = item_zh if isinstance(item_zh, dict) else {}
        construction_steps.append(
            {
                "number": index + 1,
                "stage": str(item.get("stage") or ""),
                "stage_zh": _zh_text(item_zh.get("stage"), item.get("stage")),
                "action": str(item.get("action") or ""),
                "action_zh": _zh_text(item_zh.get("action"), item.get("action")),
                "output": str(item.get("output") or ""),
                "output_zh": _zh_text(item_zh.get("output"), item.get("output")),
                "quality_control": str(item.get("quality_control") or ""),
                "quality_control_zh": _zh_text(item_zh.get("quality_control"), item.get("quality_control")),
                "source_refs": _evidence_labels([str(ref) for ref in item.get("source_refs") or []], source_index),
            }
        )

    return {
        "is_structured_v2": True,
        "key_numbers": key_numbers,
        "construction_steps": construction_steps,
        "biases_or_limits": [
            _sourced_item_view(item, source_index, _list_item(zh.get("biases_or_limits"), index))
            for index, item in enumerate(value.get("biases_or_limits") or [])
        ],
    }


def _type_section_views(report: dict[str, Any], source_index: dict[str, dict[str, Any]], zh_value: Any = None) -> list[dict[str, Any]]:
    config = [
        ("theory_understanding", "Theory Understanding"),
        ("dataset_benchmark_understanding", "Dataset / Benchmark Understanding"),
        ("survey_understanding", "Survey Understanding"),
        ("application_understanding", "Application Understanding"),
        ("system_understanding", "System / Tooling Understanding"),
    ]
    sections: list[dict[str, Any]] = []
    zh_sections = zh_value if isinstance(zh_value, dict) else {}
    for key, title in config:
        value = report.get(key)
        if not isinstance(value, dict) or not value:
            continue
        if key == "dataset_benchmark_understanding" and value.get("format") == "structured_v2":
            continue
        zh = zh_sections.get(key) if isinstance(zh_sections.get(key), dict) else {}
        groups = []
        for field, item in value.items():
            label = str(field).replace("_", " ").title()
            if isinstance(item, list):
                groups.append(
                    {
                        "label": label,
                        "label_zh": _label_zh(label),
                        "items": [
                            _sourced_item_view(row, source_index, _list_item(zh.get(field), index))
                            for index, row in enumerate(item)
                        ],
                        "text": "",
                    }
                )
            elif isinstance(item, dict):
                row = _sourced_item_view(item, source_index, zh.get(field))
                groups.append({"label": label, "label_zh": _label_zh(label), "items": [], "text": row["text"], "text_zh": row["text_zh"], "meta": row.get("meta", "")})
            else:
                groups.append({"label": label, "label_zh": _label_zh(label), "items": [], "text": str(item), "text_zh": _zh_text(zh.get(field), item), "meta": ""})
        sections.append({"key": key, "title": title, "title_zh": _label_zh(title), "groups": groups})
    return sections


def _extraction_rows(value: Any, zh_value: Any = None) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return []
    zh = zh_value if isinstance(zh_value, dict) else {}
    rows: list[dict[str, str]] = []
    for key, items in value.items():
        zh_items = zh.get(key)
        rows.append(
            {
                "label": str(key).replace("_", " ").title(),
                "label_zh": _label_zh(str(key).replace("_", " ").title()),
                "value": "; ".join(str(item) for item in items) if items else "none",
                "value_zh": "; ".join(str(item) for item in zh_items) if isinstance(zh_items, list) and zh_items else ("无" if not items else ZH_MISSING),
            }
        )
    return rows


def _format_pseudocode(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.split(";") if part.strip()]
    if "\n" in text or "; " not in text or (len(text) <= 100 and len(parts) < 3):
        return text
    return "\n".join(f"{part};" if index < len(parts) - 1 else part for index, part in enumerate(parts))


def _algorithm_steps_view(value: Any, source_index: dict[str, dict[str, Any]], zh_value: Any = None) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        zh = _list_item(zh_value, index)
        zh = zh if isinstance(zh, dict) else {}
        rows.append(
            {
                "step": str(item.get("step") or index + 1),
                "action": str(item.get("action") or ""),
                "action_zh": _zh_text(zh.get("action"), item.get("action")),
                "inputs": str(item.get("inputs") or ""),
                "inputs_zh": _zh_text(zh.get("inputs"), item.get("inputs")),
                "outputs": str(item.get("outputs") or ""),
                "outputs_zh": _zh_text(zh.get("outputs"), item.get("outputs")),
                "source_refs": _evidence_labels([str(ref) for ref in item.get("source_refs") or []], source_index),
            }
        )
    return rows


def _source_index(source_map: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(source_map, dict):
        return {}
    return {
        str(item.get("id")): item
        for item in source_map.get("blocks") or []
        if isinstance(item, dict) and item.get("id")
    }


def _evidence_labels(refs: list[str], source_index: dict[str, dict[str, Any]]) -> str:
    labels = [_source_label(ref, source_index) for ref in refs]
    return "; ".join(dict.fromkeys(label for label in labels if label))


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


def _source_ref_block_id(ref: str) -> str:
    for prefix in ["S", "C", "F", "T", "M"]:
        index = ref.find(prefix)
        if index >= 0 and len(ref) >= index + 4 and ref[index + 1:index + 4].isdigit():
            return ref[index:index + 4]
    return ref.split()[0].split("/")[0]


def _list_item(value: Any, index: int) -> Any:
    return value[index] if isinstance(value, list) and index < len(value) else None


def _zh_text(value: Any, fallback: Any = "") -> str:
    if isinstance(value, dict):
        value = value.get("text")
    if isinstance(value, str) and value.strip():
        return value
    if value is not None and str(value).strip():
        return str(value)
    return ZH_MISSING if fallback else ""


def _label_zh(label: str) -> str:
    labels = {
        "One-sentence summary": "一句话总结",
        "Quick Read": "快速阅读",
        "Argument Map": "论证地图",
        "Gap": "问题缺口",
        "Core contribution": "核心贡献",
        "Method logic": "方法逻辑",
        "Decisive evidence": "关键证据",
        "Limitations": "局限性",
        "Future work": "未来工作",
        "Central Claims": "核心论点",
        "Method Understanding": "方法理解",
        "Pipeline": "流程",
        "Algorithm Steps": "算法步骤",
        "Engineering Derivation Sketch": "工程化推导理解",
        "Implementation Details": "实现细节",
        "Evaluation": "实验评估",
        "Datasets": "数据集",
        "Metrics": "指标",
        "Main Results": "主要结果",
        "Ablation / Comparison Takeaways": "消融/对比结论",
        "Numeric Results": "关键数值结果",
        "Visual Cards": "图表卡片",
        "Availability": "可用性",
        "Extraction Notes": "提取质量说明",
        "Mathematical Core": "数学核心",
        "Problem Formulation": "问题形式",
        "Key Equations": "关键公式",
        "Theorem / Principle Chain": "定理/原理链",
        "Survey Map": "综述地图",
        "Method Family Matrix": "方法族矩阵",
        "Timeline": "时间线",
        "Theory Understanding": "理论理解",
        "Dataset / Benchmark Understanding": "数据集/基准理解",
        "Survey Understanding": "综述理解",
        "Application Understanding": "应用理解",
        "System / Tooling Understanding": "系统/工具理解",
    }
    return labels.get(label, label)


def _asset_views(root: Path, current_page: str, paper_dir: Path, report: dict[str, Any] | None) -> list[dict[str, str | None]]:
    assets: list[dict[str, str | None]] = []
    if not report:
        return assets
    for item in report.get("assets") or []:
        if not isinstance(item, dict):
            continue
        path_or_url = str(item.get("path_or_url") or item.get("url") or item.get("path") or "").strip()
        if not path_or_url:
            continue
        href: str | None
        if path_or_url.startswith(("http://", "https://")):
            href = path_or_url
        else:
            candidate = Path(path_or_url)
            if not candidate.is_absolute():
                local = root / path_or_url
                if not local.exists():
                    local = paper_dir / path_or_url
            else:
                local = candidate
            href = _link(current_page, local.relative_to(root).as_posix()) if local.exists() and _is_relative_to(local, root) else None
        assets.append(
            {
                "type": str(item.get("asset_type") or item.get("type") or "asset"),
                "path_or_url": path_or_url,
                "status": str(item.get("status") or "unknown"),
                "href": href,
                "note": str(item.get("note") or item.get("description") or ""),
            }
        )
    return assets


def _existing_link(root: Path, current_page: str, target: str) -> str | None:
    path = root / target
    if not path.exists():
        return None
    return _link(current_page, target)


def _link(current_page: str, target_root_rel: str) -> str:
    current_parent = Path(current_page).parent
    return Path(os.path.relpath(target_root_rel, current_parent)).as_posix()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def build_html(root: str | Path) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    topic = load_topic(root)
    env = _env()
    paths.html.mkdir(parents=True, exist_ok=True)
    (paths.html / "style.css").write_text((repo_root() / "templates" / "html" / "style.css").read_text(encoding="utf-8"), encoding="utf-8")
    candidates = load_candidates(root)
    papers = _papers(root)
    pdf_count = sum(1 for paper in papers if paper["has_pdf"])

    for paper in papers:
        paper_dir = paths.paper_dir(paper["bibkey"])
        paper_dir.mkdir(parents=True, exist_ok=True)
        (paper_dir / READING_RESULT_NAME).write_text(
            env.get_template("paper.html").render(paper=paper),
            encoding="utf-8",
        )
    (paths.html / "dashboard.html").write_text(
        env.get_template("dashboard.html").render(
            title=topic.get("title") or paths.root.name,
            direction=topic.get("direction") or "",
            scope_guidance=topic.get("scope_guidance") or {},
            candidate_count=len(candidates),
            paper_count=len(papers),
            pdf_count=pdf_count,
        ),
        encoding="utf-8",
    )
    (paths.html / "candidates.html").write_text(env.get_template("candidates.html").render(candidates=candidates), encoding="utf-8")
    (paths.html / "library.html").write_text(env.get_template("library.html").render(papers=papers), encoding="utf-8")
    return {"ok": True, "html": str(paths.html), "pages": 3 + len(papers)}


def export_standalone_html(root: str | Path, bibkey: str, output: str | Path | None = None) -> dict[str, Any]:
    """Export one reading result as a self-contained, shareable HTML file."""
    paths = TopicPaths.from_root(root)
    paper_dir = paths.paper_dir(bibkey)
    source = paper_dir / READING_RESULT_NAME
    if not source.exists():
        raise FileNotFoundError(f"reading result not found for {bibkey}: {source}")
    destination = Path(output).expanduser().resolve() if output else paths.root / "exports" / f"{bibkey}_offline.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = source.read_text(encoding="utf-8")
    stylesheet = (paths.html / "style.css").read_text(encoding="utf-8")
    document = re.sub(
        r'<link rel="stylesheet" href="[^"]*style\.css">',
        f"<style>\n{stylesheet}\n</style>",
        document,
        count=1,
    )

    def inline_reference(match: re.Match[str]) -> str:
        attribute, value = match.group(1), match.group(2)
        if value.startswith(("data:", "http://", "https://", "#")):
            return match.group(0)
        target = (paper_dir / value).resolve()
        if not _is_relative_to(target, paths.root) or not target.is_file():
            if attribute == "href" and value.startswith("../../html/"):
                return f'{attribute}="#"'
            return match.group(0)
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(target.read_bytes()).decode("ascii")
        return f'{attribute}="data:{mime};base64,{encoded}"'

    document = re.sub(r'(src|data-lightbox-src|href)="([^"]+)"', inline_reference, document)
    destination.write_text(document, encoding="utf-8")
    return {
        "ok": True,
        "bibkey": bibkey,
        "output": str(destination),
        "bytes": destination.stat().st_size,
        "self_contained": True,
    }
