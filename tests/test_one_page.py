from __future__ import annotations

import json

from paper_engine.cli import build_parser
from paper_engine import one_page


def _content():
    sourced = {"text": "Paper-specific finding.", "source_refs": ["S001"]}
    return {
        "schema_version": one_page.SCHEMA_VERSION,
        "generated_on": "2026-08-25",
        "paper": {"title": "A Paper", "citation": "Author (1993)"},
        "contribution": {
            "one_sentence": "A compact verdict.",
            "core_contributions": [sourced],
            "core_conclusions": [sourced],
        },
        "model": {
            "framework": "A coupled model.",
            "source_refs": ["S001"],
            "governing_equations": [
                {"label": "Balance", "equation": "a = b", "meaning": "Meaning.", "source_refs": ["S001"]}
            ],
        },
        "results": {
            "key_findings": [sourced],
            "visuals": [
                {"label": "Figure 1", "page": 1, "crop": [0, 0, 1, 1], "caption": "Result.", "source_refs": ["F001"]}
            ],
        },
        "reproduction": {
            "goal": "Reproduce the trend.",
            "source_refs": ["S001"],
            "workflow": [{"title": "Build", "text": "Set up the model.", "source_refs": ["S001"]}],
        },
        "evidence": [
            {"id": "S001", "page": 1, "quote": "source sentence", "note": "Body text"},
            {"id": "F001", "page": 1, "quote": "figure caption", "note": "Figure"},
        ],
    }


def test_cli_registers_one_page_commands():
    args = build_parser().parse_args(["one-page", "prepare", "paper.pdf", "--work-dir", "work"])
    assert args.command == "one-page"
    assert args.one_page_command == "prepare"


def test_build_one_page_validates_evidence_and_embeds_visual(tmp_path, monkeypatch):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF placeholder")
    content = tmp_path / "content.json"
    content.write_text(json.dumps(_content()), encoding="utf-8")
    monkeypatch.setattr(one_page, "_read_pdf_pages", lambda path: (["source sentence and figure caption"], {"title": "A Paper"}))
    monkeypatch.setattr(
        one_page,
        "_visual_data_url",
        lambda path, visual, content_dir=None: "data:image/png;base64,AA==",
    )

    result = one_page.build_one_page(pdf, content, tmp_path / "brief.html")

    assert result["ok"]
    rendered = (tmp_path / "brief.html").read_text(encoding="utf-8")
    assert "核心贡献与结论" in rendered
    assert "COMSOL 最小复现" in rendered
    assert "data:image/png;base64,AA==" in rendered
    assert "S001 · p.1" in rendered


def test_build_one_page_embeds_local_result_artifact(tmp_path, monkeypatch):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF placeholder")
    artifact = tmp_path / "comparison.png"
    artifact.write_bytes(b"result-image")
    data = _content()
    data["results"]["visuals"] = [
        {
            "label": "Paper vs COMSOL",
            "path": "comparison.png",
            "caption": "Independent result artifact.",
            "source_refs": ["F001"],
        }
    ]
    content = tmp_path / "content.json"
    content.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(one_page, "_read_pdf_pages", lambda path: (["source sentence and figure caption"], {}))

    result = one_page.build_one_page(pdf, content, tmp_path / "brief.html")

    assert result["visual_count"] == 1
    rendered = (tmp_path / "brief.html").read_text(encoding="utf-8")
    assert "data:image/png;base64," in rendered
    assert "Paper vs COMSOL" in rendered
