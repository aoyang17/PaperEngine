from __future__ import annotations

import json

from conftest import fixture_path
from battery_lit.acquire import acquire_pdf
from battery_lit.bib import promote_candidate
from battery_lit.html import build_html, export_standalone_html
from battery_lit.read import rebuild_note
from battery_lit.search import collect
from battery_lit.topic import init_topic


def _write_reading_bundle(tmp_path, bibkey, report=None, source_map=None, paper_index=None, note_plan=None):
    paper_dir = tmp_path / "papers" / bibkey
    report = report or json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    source_map = source_map or json.loads(fixture_path("source_map.json").read_text(encoding="utf-8"))
    paper_index = paper_index or json.loads(fixture_path("paper_index.json").read_text(encoding="utf-8"))
    note_plan = note_plan or json.loads(fixture_path("note_plan.json").read_text(encoding="utf-8"))
    report["bibkey"] = bibkey
    report["pdf_path"] = f"papers/{bibkey}/paper.pdf"
    report["parsed_markdown_path"] = f"papers/{bibkey}/parsed.md"
    report["source_map_path"] = f"papers/{bibkey}/source_map.json"
    source_map["paper"]["bibkey"] = bibkey
    source_map["paper"]["pdf_path"] = f"papers/{bibkey}/paper.pdf"
    source_map["paper"]["parsed_markdown_path"] = f"papers/{bibkey}/parsed.md"
    for item in paper_index.get("figures_tables", []):
        if item.get("candidate_image_paths"):
            item["candidate_image_paths"] = [path.replace("Example2026A", bibkey) for path in item["candidate_image_paths"]]
    for item in report.get("visual_cards", []):
        if item.get("image_path"):
            item["image_path"] = item["image_path"].replace("Example2026A", bibkey)
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "paper_index.json").write_text(json.dumps(paper_index, indent=2), encoding="utf-8")
    (paper_dir / "note_plan.json").write_text(json.dumps(note_plan, indent=2), encoding="utf-8")
    (paper_dir / "source_map.json").write_text(json.dumps(source_map, indent=2), encoding="utf-8")
    (paper_dir / "deep_read.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def test_empty_topic_builds_core_pages(tmp_path):
    init_topic(tmp_path, title="Empty Topic")
    result = build_html(tmp_path)
    assert result["ok"] is True
    for name in ["dashboard.html", "candidates.html", "library.html", "style.css"]:
        assert (tmp_path / "html" / name).exists()


def test_export_standalone_html_inlines_styles_images_and_pdf(tmp_path):
    paper_dir = tmp_path / "papers" / "Example2026A"
    html_dir = tmp_path / "html"
    paper_dir.joinpath("page_images").mkdir(parents=True)
    html_dir.mkdir()
    html_dir.joinpath("style.css").write_text("body { color: navy; }", encoding="utf-8")
    paper_dir.joinpath("page_images", "figure.png").write_bytes(b"fake-png")
    paper_dir.joinpath("paper.pdf").write_bytes(b"fake-pdf")
    paper_dir.joinpath("reading_result.html").write_text(
        '<link rel="stylesheet" href="../../html/style.css">'
        '<a href="../../html/library.html">Library</a>'
        '<a href="paper.pdf">PDF</a>'
        '<img src="page_images/figure.png" data-lightbox-src="page_images/figure.png">',
        encoding="utf-8",
    )

    result = export_standalone_html(tmp_path, "Example2026A")
    text = (tmp_path / "exports" / "Example2026A_offline.html").read_text(encoding="utf-8")

    assert result["self_contained"] is True
    assert "<style>" in text
    assert "data:image/png;base64," in text
    assert "data:application/pdf;base64," in text
    assert 'href="#"' in text
    assert "../../html/style.css" not in text


def test_populated_topic_builds_library_and_paper_page(tmp_path):
    init_topic(tmp_path, title="Populated")
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")
    report = json.loads(fixture_path("deep_read_report.json").read_text())
    report["paper_profile"] = {
        "primary_type": "method",
        "active_lenses": ["method", "application"],
        "confidence": "high",
        "rationale": "Fixture exercises HTML rendering.",
    }
    report["quick_read"] = [{"text": "Read this first.", "source_refs": ["S001"], "confidence": "high"}]
    report["central_claims"] = [
        {
            "claim": "The HTML renderer can show evidence-grounded claims.",
            "evidence_summary": "The fixture report includes central_claims.",
            "source_refs": ["S004"],
            "what_it_proves": "Renderer support exists.",
            "what_it_does_not_prove": "It does not prove the PDF was deeply understood.",
            "open_question": "How dense should the final note be?",
            "confidence": "high",
        }
    ]
    report["visual_cards"] = [
        {
            "label": "Figure 1",
            "kind": "method_overview",
            "page": 1,
            "image_path": "papers/Example2026A/page_images/page-001.png",
            "source_caption": "Fixture page.",
            "placement_section": "method_understanding",
            "placed_near": "S003",
            "reading_note": "Grounds the visual selection panel.",
            "crop_status": "full_page_approximate",
            "source_refs": ["F001", "C001"],
        }
    ]
    report["method_understanding"]["implementation_details"] = [
        {"text": "Uses a structured local pipeline.", "source_refs": ["S003"], "confidence": "high"}
    ]
    report["evaluation"]["main_results"] = [
        {"text": "Runs a fixture workflow end to end.", "source_refs": ["S004"], "confidence": "high"}
    ]
    report["availability"]["code"]["url"] = "https://example.com/project"
    report["translations"]["zh"]["quick_read"] = ["先阅读这一条结论。"]
    report["translations"]["zh"]["central_claims"] = [
        {
            "claim": "HTML 渲染器可以展示有证据支撑的主张。",
            "evidence_summary": "fixture 报告包含 central_claims。",
            "what_it_proves": "渲染器支持已经存在。",
            "what_it_does_not_prove": "它不能证明 PDF 已经被深入理解。",
            "open_question": "最终 note 应该多密集？",
        }
    ]
    report["translations"]["zh"]["visual_cards"] = [
        {"label": "图 1", "source_caption": "fixture 页面。", "reading_note": "支撑视觉选择面板。"}
    ]
    report["translations"]["zh"]["method_understanding"]["implementation_details"] = ["使用结构化本地流程。"]
    report["translations"]["zh"]["evaluation"]["main_results"] = ["完整运行一个 fixture 工作流。"]
    _write_reading_bundle(tmp_path, "Example2026A", report=report)
    rebuild_note(tmp_path, "Example2026A")

    build_html(tmp_path)
    library_html = (tmp_path / "html" / "library.html").read_text()
    assert "Example2026A" in library_html
    assert 'href="../papers/Example2026A/reading_result.html">Note</a>' in library_html
    assert 'href="../papers/Example2026A/note.md">Note</a>' not in library_html
    paper_html = tmp_path / "papers" / "Example2026A" / "reading_result.html"
    assert paper_html.exists()
    text = paper_html.read_text()
    assert "One-sentence summary" in text
    assert "一句话总结" in text
    assert "Quick Read" in text
    assert "Read this first." in text
    assert "Argument Map" in text
    assert "source: S001" not in text
    assert "Evidence: Abstract, p.1" in text
    assert "Central Claims" in text
    assert "The HTML renderer can show evidence-grounded claims." in text
    assert "Boundary" in text
    assert "It does not prove the PDF was deeply understood." in text
    assert "Visual Cards" in text
    assert "Figure 1" in text
    assert "Method Understanding" in text
    assert "Algorithm Steps" in text
    assert "Engineering Derivation Sketch" in text
    assert "Evaluation" in text
    assert "Reading Plan" not in text
    assert "Numeric Results" in text
    assert "Application Understanding" in text
    assert "Availability" in text
    assert "可用性" in text
    assert "Code" in text
    assert "代码" in text
    assert "外部 GitHub 检索找到了该 fixture 论文的合成仓库 URL。" in text
    assert "Extraction Quality Notes" in text
    assert "Uses a structured local pipeline." in text
    assert "https://example.com/project" in text
    assert "paper.pdf" in text
    assert "note.md" in text
    assert "../../html/style.css" in text
    assert "<article>" not in text


def test_paper_page_marks_missing_chinese_translation_instead_of_falling_back(tmp_path):
    init_topic(tmp_path, title="Missing Chinese")
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")
    report = json.loads(fixture_path("deep_read_report.json").read_text())
    report["translations"]["zh"]["central_claims"][0].pop("claim")
    _write_reading_bundle(tmp_path, "Example2026A", report=report)

    build_html(tmp_path)
    text = (tmp_path / "papers" / "Example2026A" / "reading_result.html").read_text()
    assert "【中文翻译缺失】" in text


def test_paper_page_renders_structured_dataset_report_without_generic_duplicate(tmp_path):
    init_topic(tmp_path, title="Structured Dataset")
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")
    report = json.loads(fixture_path("deep_read_report.json").read_text())
    report["paper_profile"] = {
        "primary_type": "dataset_benchmark",
        "active_lenses": ["dataset_benchmark"],
        "confidence": "high",
        "rationale": "Fixture exercises structured dataset HTML rendering.",
    }
    report["dataset_benchmark_understanding"] = {
        "format": "structured_v2",
        "key_numbers": [
            {
                "label": "Simulation cases",
                "value": "8,000",
                "unit": "cases",
                "context": "The release covers multiple vehicle geometries.",
                "source_refs": ["S001"],
            },
            {
                "label": "Storage",
                "value": "39",
                "unit": "TB",
                "context": "Total packaged dataset size.",
                "source_refs": ["S004"],
            },
        ],
        "construction_steps": [
            {
                "stage": "Geometry sampling",
                "action": "Sample valid vehicle parameters.",
                "output": "Parameterized vehicle variants",
                "quality_control": "Reject invalid geometry combinations.",
                "source_refs": ["S003"],
            },
            {
                "stage": "Electrochemical characterization",
                "action": "Cycle each accepted electrode formulation.",
                "output": "Capacity, efficiency, and impedance measurements",
                "quality_control": "Retain measurements that pass cell-level quality checks.",
                "source_refs": ["S004"],
            },
        ],
        "biases_or_limits": [
            {"text": "Coverage is bounded by the sampled design space.", "source_refs": ["S004"], "confidence": "high"}
        ],
    }
    report["translations"]["zh"].setdefault("type_sections", {})["dataset_benchmark_understanding"] = {
        "key_numbers": [
            {"label": "仿真案例", "context": "该发布覆盖多种车辆几何。"},
            {"label": "存储量", "context": "打包数据集的总大小。"},
        ],
        "construction_steps": [
            {
                "stage": "几何采样",
                "action": "采样有效的车辆参数。",
                "output": "参数化车辆变体",
                "quality_control": "剔除无效的几何组合。",
            },
            {
                "stage": "电化学表征",
                "action": "对每个通过筛选的电极配方进行循环测试。",
                "output": "容量、效率与阻抗测量",
                "quality_control": "仅保留通过电芯级质量检查的测量。",
            },
        ],
        "biases_or_limits": ["覆盖范围受采样设计空间限制。"],
    }
    _write_reading_bundle(tmp_path, "Example2026A", report=report)

    build_html(tmp_path)
    text = (tmp_path / "papers" / "Example2026A" / "reading_result.html").read_text()

    assert text.count("Dataset / Benchmark Understanding") == 1
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in text
    assert text.count("数据集/基准理解") == 1
    assert "Dataset at a Glance" in text
    assert "数据集速览" in text
    assert "Simulation cases" in text
    assert "仿真案例" in text
    assert "8,000" in text
    assert "Construction Pipeline" in text
    assert "构建流程" in text
    assert "Geometry sampling" in text
    assert "几何采样" in text
    assert "Coverage is bounded by the sampled design space." in text
    assert "覆盖范围受采样设计空间限制。" in text
    assert "Abstract, p.1" in text
    assert text.count('class="table-scroll"') >= 2
    assert "Data Construction" not in text
    assert "Key Numbers" not in text


def test_paper_page_keeps_legacy_dataset_generic_section(tmp_path):
    init_topic(tmp_path, title="Legacy Dataset")
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")
    report = json.loads(fixture_path("deep_read_report.json").read_text())
    report["dataset_benchmark_understanding"] = {
        "data_construction": [
            {"text": "Legacy records are collected and filtered.", "source_refs": ["S003"], "confidence": "high"}
        ],
        "statistics": [
            {"text": "The legacy corpus has 500 records.", "source_refs": ["S004"], "confidence": "high"}
        ],
        "availability": [
            {"text": "The legacy dataset is available.", "source_refs": ["S004"], "confidence": "high"}
        ],
        "biases_or_limits": [
            {"text": "The legacy corpus has narrow coverage.", "source_refs": ["S004"], "confidence": "high"}
        ],
    }
    report["translations"]["zh"].setdefault("type_sections", {})["dataset_benchmark_understanding"] = {
        "data_construction": ["旧版记录经过收集和筛选。"],
        "statistics": ["旧版语料包含 500 条记录。"],
        "availability": ["旧版数据集可用。"],
        "biases_or_limits": ["旧版语料覆盖范围较窄。"],
    }
    _write_reading_bundle(tmp_path, "Example2026A", report=report)

    build_html(tmp_path)
    text = (tmp_path / "papers" / "Example2026A" / "reading_result.html").read_text()

    assert "Dataset / Benchmark Understanding" in text
    assert "Data Construction" in text
    assert "Legacy records are collected and filtered." in text
    assert "旧版记录经过收集和筛选。" in text
    assert "Statistics" in text
    assert "The legacy corpus has 500 records." in text
    assert "Dataset at a Glance" not in text
    assert "Construction Pipeline" not in text


def test_paper_page_translates_visual_placeholder_reason_with_safe_fallback(tmp_path):
    init_topic(tmp_path, title="Visual Placeholder")
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")
    report = json.loads(fixture_path("deep_read_report.json").read_text())
    report["visual_cards"][0]["placeholder_reason"] = "paper_index page labels collapse to page 1; no tight crop selected in this draft."
    report["visual_cards"][0]["crop_status"] = "placeholder"
    report["visual_cards"][0].pop("image_path", None)
    report["translations"]["zh"]["visual_cards"][0].pop("placeholder_reason", None)
    _write_reading_bundle(tmp_path, "Example2026A", report=report)

    build_html(tmp_path)
    text = (tmp_path / "papers" / "Example2026A" / "reading_result.html").read_text()

    assert "解析页码或裁剪信息不够可靠" in text
    assert "【中文翻译缺失】" not in text


def test_paper_page_handles_missing_deep_read_report(tmp_path):
    init_topic(tmp_path, title="Missing Report")
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")

    build_html(tmp_path)
    text = (tmp_path / "papers" / "Example2026A" / "reading_result.html").read_text()
    assert "No structured reading report yet" in text
    assert "BibTeX" in text


def test_materials_report_renders_six_sections_and_hides_algorithm_layout(tmp_path):
    init_topic(tmp_path, title="Materials")
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")
    report = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    sourced = {"text": "Paper-specific physical interpretation with traceable evidence.", "source_refs": ["S001"]}
    report["research_overview"] = {
        "study_identity": {"study_type": "computational", "domain": "Coupled materials simulation", "evidence_mode": "Finite-element evidence", "source_refs": ["S001"]},
        "module_alignment": [{"module_id": "m1", "module_title": "Module one", "score": 0.9, "role": "primary", "rationale": "Directly addresses the configured physical problem.", "source_refs": ["S001"]}],
        "one_sentence_conclusion": sourced, "why_worth_reading": sourced, "research_problem": sourced,
        "prior_gap": sourced, "core_contribution": sourced, "scope_boundary": sourced,
    }
    report["research_system"] = {"research_object": sourced, "geometry_and_scale": [sourced], "phases_and_composition": [sourced], "process_and_loading": [sourced], "state_variables": [sourced], "target_outputs": [sourced]}
    report["model_and_mechanisms"] = {"framework": sourced, "assumptions": [sourced], "free_energy": [sourced], "governing_equations": [], "constitutive_relations": [], "coupling_logic": [sourced]}
    report["computational_reproducibility"] = {"parameters": [], "initial_conditions": [sourced], "boundary_conditions": [sourced], "numerical_implementation": [sourced], "reproducibility_check": [sourced]}
    report["results_validation_mechanisms"] = {"key_results": [sourced], "validation_and_comparison": [sourced], "mechanistic_interpretation": [sourced], "sensitivity_and_uncovered": [sourced], "experimental_correspondence": [sourced]}
    report["research_value_resources"] = {"module_value": [sourced], "reusable_elements": [sourced], "limitations_and_next_steps": [sourced], "reproducibility_verdict": sourced}
    report["translations"]["zh"].update({
        "research_overview": {"study_identity": {"study_type_label": "计算建模研究", "domain": "材料耦合仿真", "evidence_mode": "有限元证据"}, "module_alignment": [{"module_title": "模块一", "role_label": "主模块", "rationale": "直接研究所配置的物理问题。"}], **{key: "具有原文证据的论文专属物理解读。" for key in ["one_sentence_conclusion", "why_worth_reading", "research_problem", "prior_gap", "core_contribution", "scope_boundary"]}},
        "research_system": {}, "model_and_mechanisms": {}, "computational_reproducibility": {},
        "results_validation_mechanisms": {}, "research_value_resources": {},
    })
    _write_reading_bundle(tmp_path, "Example2026A", report=report)
    rebuild_note(tmp_path, "Example2026A")
    build_html(tmp_path)
    text = (tmp_path / "papers" / "Example2026A" / "reading_result.html").read_text(encoding="utf-8")
    for heading in ["Paper Overview", "Research System and Problem Definition", "Model and Physical Mechanisms", "Computational Setup and Reproducibility", "Results, Validation, and Mechanisms", "Research Value and Resources"]:
        assert heading in text
    assert "Algorithm Steps" not in text
    assert "Dataset / Benchmark Understanding" not in text


def test_paper_page_formats_pseudocode_and_local_assets(tmp_path):
    init_topic(tmp_path, title="Pseudocode")
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")
    paper_dir = tmp_path / "papers" / "Example2026A"
    (paper_dir / "figure.png").write_bytes(b"fake")
    report = json.loads(fixture_path("deep_read_report.json").read_text())
    report["method_understanding"]["algorithm_pseudocode"] = (
        "Initialize states; Compute guidance gradient; Update sample with corrected drift; Return sample"
    )
    report["method_understanding"]["algorithm_steps"] = [
        {"step": 1, "action": "Initialize states.", "inputs": "PDF", "outputs": "state", "source_refs": ["S003"]},
        {"step": 2, "action": "Compute guidance gradient.", "inputs": "state", "outputs": "gradient", "source_refs": ["S003"]},
        {"step": 3, "action": "Update sample with corrected drift.", "inputs": "gradient", "outputs": "sample", "source_refs": ["S004"]},
    ]
    report["visual_cards"][0]["image_path"] = "papers/Example2026A/figure.png"
    report["visual_cards"][0]["crop_status"] = "tight_crop"
    _write_reading_bundle(tmp_path, "Example2026A", report=report)

    build_html(tmp_path)
    text = (tmp_path / "papers" / "Example2026A" / "reading_result.html").read_text()
    assert "Initialize states." in text
    assert "Compute guidance gradient." in text
    assert "figure.png" in text
    assert 'data-lightbox-src="figure.png"' in text


def test_paper_page_renders_accepted_with_limitations_banner(tmp_path):
    init_topic(tmp_path, title="Limited Reading")
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")
    report = json.loads(fixture_path("deep_read_report.json").read_text())
    report["reading_quality"] = {
        "status": "accepted_with_limitations",
        "acceptance_reason": "max_cycles_reached",
        "cycles_used": 7,
        "open_issues": ["Reviewer still requested a more concrete limitation statement."],
        "controller_warnings": ["Accepted only because --accept-last-on-max-cycles was set."],
    }
    _write_reading_bundle(tmp_path, "Example2026A", report=report)

    build_html(tmp_path)
    text = (tmp_path / "papers" / "Example2026A" / "reading_result.html").read_text()
    assert "Accepted with limitations" in text
    assert "带局限接受" in text
    assert "Reviewer still requested a more concrete limitation statement." in text
    assert "after 7 cycles" in text


def test_paper_page_renders_mathematical_core_and_survey_map(tmp_path):
    init_topic(tmp_path, title="Math Survey")
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")
    report = json.loads(fixture_path("deep_read_report.json").read_text())
    source_map = json.loads(fixture_path("source_map.json").read_text())
    source_map["blocks"].extend(
        [
            {"id": "S007", "page": 1, "section": "Theory", "section_id": "sec:003", "paragraph_ids": ["p:0003"], "type": "equation", "source_kind": "equation", "source_text": "min J(u) subject to xdot=f(t,x,u)", "confidence": "high", "notes": ""},
            {"id": "S008", "page": 1, "section": "Survey", "section_id": "sec:003", "paragraph_ids": ["p:0003"], "type": "method_family", "source_kind": "body_text", "source_text": "Direct, shooting, and HJB methods are compared.", "confidence": "high", "notes": ""},
            {"id": "M001", "page": 1, "section": "Theory", "section_id": "sec:003", "paragraph_ids": [], "type": "equation", "source_kind": "equation", "source_text": "Vision transcription of objective equation.", "latex": "\\\\min_u J(u)", "image_path": "papers/Example2026A/math_pages/page-001.png", "backend": "codex_vision", "confidence": "medium", "notes": ""},
        ]
    )
    math_dir = tmp_path / "papers" / "Example2026A" / "math_pages"
    math_dir.mkdir(parents=True, exist_ok=True)
    (math_dir / "page-001.png").write_bytes(b"fake")
    report["paper_profile"] = {
        "primary_type": "survey",
        "active_lenses": ["survey", "method", "theory"],
        "confidence": "high",
        "rationale": "Fixture exercises math and survey HTML rendering.",
    }
    report["theory_understanding"] = {
        "problem_formulation": {"text": "Minimize cost under ODE dynamics and constraints.", "source_refs": ["S007"], "confidence": "high"},
        "key_equations": [
            {"label": "ODE optimal-control problem", "equation": "minimize J(u)\nsubject to xdot = f(t, x, u)", "latex": "\\\\min_u J(u)", "explanation": "The control is optimized while respecting dynamics.", "source_refs": ["M001"], "confidence": "high"},
            {"label": "Shooting function", "equation": "G(z0) = R(z0, z(T, z0)) = 0", "explanation": "The BVP becomes a root solve.", "source_refs": ["S007"], "confidence": "high"},
        ],
        "theorem_or_principle_chain": [
            {"principle": "Pontryagin maximum principle", "role": "Creates extremal equations.", "intuition": "Optimal candidates must satisfy adjoint conditions.", "source_refs": ["S007"], "confidence": "high"}
        ],
        "assumptions": [{"text": "Regularity is assumed.", "source_refs": ["S007"], "confidence": "medium"}],
        "key_results": [{"text": "Multiple shooting adds matching nodes.", "source_refs": ["S007"], "confidence": "high"}],
        "engineering_proof_sketch": {"text": "Problem to PMP to BVP to root solve.", "source_refs": ["S007"], "confidence": "high"},
        "limitations": [{"text": "Initialization remains fragile.", "source_refs": ["S007"], "confidence": "high"}],
    }
    report["survey_understanding"] = {
        "scope": {"text": "Compares method families for optimal control.", "source_refs": ["S008"], "confidence": "high"},
        "taxonomy": [
            {"text": "Direct methods.", "source_refs": ["S008"], "confidence": "high"},
            {"text": "Shooting methods.", "source_refs": ["S008"], "confidence": "high"},
            {"text": "HJB methods.", "source_refs": ["S008"], "confidence": "high"},
        ],
        "method_family_matrix": [
            {"family": "Direct transcription", "core_idea": "Discretize then optimize.", "strengths": "Constraint-friendly.", "limitations": "Local and mesh-sensitive.", "best_for": "Coarse structure.", "source_refs": ["S008"], "confidence": "high"},
            {"family": "Shooting", "core_idea": "Solve PMP boundary equations.", "strengths": "Accurate.", "limitations": "Initialization-sensitive.", "best_for": "Known structure.", "source_refs": ["S008"], "confidence": "high"},
            {"family": "HJB", "core_idea": "Compute value functions.", "strengths": "Global information.", "limitations": "Dimensional cost.", "best_for": "Global checks.", "source_refs": ["S008"], "confidence": "high"},
        ],
        "timeline_milestones": [
            {"text": "1950s: PMP and dynamic programming.", "source_refs": ["S008"], "confidence": "medium"},
            {"text": "1980s: viscosity solutions.", "source_refs": ["S008"], "confidence": "medium"},
        ],
        "coverage_gaps": [{"text": "Not a complete historical bibliography.", "source_refs": ["S008"], "confidence": "high"}],
    }
    type_sections = report["translations"]["zh"].setdefault("type_sections", {})
    type_sections["theory_understanding"] = {
        "problem_formulation": "在 ODE 动力学和约束下最小化代价。",
        "key_equations": [
            {"label": "ODE 最优控制问题", "explanation": "在满足动力学的同时优化控制。"},
            {"label": "Shooting function", "explanation": "BVP 被转化为根求解。"},
        ],
        "theorem_or_principle_chain": [
            {"principle": "Pontryagin maximum principle", "role": "生成极值方程。", "intuition": "最优候选必须满足伴随条件。"}
        ],
        "engineering_proof_sketch": "问题到 PMP 到 BVP 到根求解。",
    }
    type_sections["survey_understanding"] = {
        "method_family_matrix": [
            {"family": "直接转录", "core_idea": "先离散再优化。", "strengths": "约束友好。", "limitations": "局部且依赖网格。", "best_for": "粗结构。"},
            {"family": "Shooting", "core_idea": "求解 PMP 边界方程。", "strengths": "精确。", "limitations": "依赖初始化。", "best_for": "已知结构。"},
            {"family": "HJB", "core_idea": "计算 value function。", "strengths": "全局信息。", "limitations": "维度代价高。", "best_for": "全局校验。"},
        ],
        "timeline_milestones": ["1950s：PMP 和 dynamic programming。", "1980s：viscosity solutions。"],
    }
    _write_reading_bundle(tmp_path, "Example2026A", report=report, source_map=source_map)

    build_html(tmp_path)
    text = (tmp_path / "papers" / "Example2026A" / "reading_result.html").read_text()
    assert "Mathematical Core" in text
    assert "数学核心" in text
    assert "Key Equations" in text
    assert "<math" in text
    assert "<msub>" in text
    assert "minimize J(u)\nsubject to xdot = f(t, x, u)" in text
    assert "math_pages/page-001.png" in text
    assert "Theorem / Principle Chain" in text
    assert "Pontryagin maximum principle" in text
    assert "Survey Map" in text
    assert "Method Family Matrix" in text
    assert "Direct transcription" in text
    assert "Timeline" in text
    assert "1950s" in text
