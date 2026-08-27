from __future__ import annotations

import json
import shutil
import threading
import time

from conftest import fixture_path
from paper_engine.acquire import acquire_pdf
from paper_engine.bib import promote_candidate
from paper_engine.read import SOURCE_REF_RE, audit_deep_read_quality, audit_reading_library, parse_pdf, rebuild_note, validate_deep_read_report
from paper_engine.read_batch import (
    _build_draft_worker_prompt,
    _repair_errors_for_bibkey,
    finalize_read_batch,
    prepare_read_batch,
    run_read_batch_draft_workers,
    run_read_batch_harvest,
)
from paper_engine.codex_worker import CodexEvent
from paper_engine.search import collect
from paper_engine.sidecars import READ_DRAFT_WORKER_SCHEMA_VERSION, READ_HARVEST_SCHEMA_VERSION
from paper_engine.topic import init_topic


def _promoted_topic(tmp_path):
    init_topic(tmp_path)
    collect(tmp_path, fixture=fixture_path("search_results.json"))
    acquire_pdf(tmp_path, "CAND-001", fixture_path("example.pdf"))
    promote_candidate(tmp_path, "CAND-001")
    return "Example2026A"


def _write_reading_bundle(tmp_path, bibkey, data=None, source_map=None, paper_index=None, note_plan=None):
    paper_dir = tmp_path / "papers" / bibkey
    data = data or json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    source_map = source_map or json.loads(fixture_path("source_map.json").read_text(encoding="utf-8"))
    paper_index = paper_index or json.loads(fixture_path("paper_index.json").read_text(encoding="utf-8"))
    note_plan = note_plan or json.loads(fixture_path("note_plan.json").read_text(encoding="utf-8"))
    data["bibkey"] = bibkey
    data["pdf_path"] = f"papers/{bibkey}/paper.pdf"
    data["parsed_markdown_path"] = f"papers/{bibkey}/parsed.md"
    data["source_map_path"] = f"papers/{bibkey}/source_map.json"
    source_map["paper"]["bibkey"] = bibkey
    source_map["paper"]["pdf_path"] = f"papers/{bibkey}/paper.pdf"
    source_map["paper"]["parsed_markdown_path"] = f"papers/{bibkey}/parsed.md"
    for item in paper_index.get("figures_tables", []):
        if item.get("candidate_image_paths"):
            item["candidate_image_paths"] = [path.replace("Example2026A", bibkey) for path in item["candidate_image_paths"]]
    for item in data.get("visual_cards", []):
        if item.get("image_path"):
            item["image_path"] = item["image_path"].replace("Example2026A", bibkey)
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "paper_index.json").write_text(json.dumps(paper_index, indent=2), encoding="utf-8")
    (paper_dir / "note_plan.json").write_text(json.dumps(note_plan, indent=2), encoding="utf-8")
    (paper_dir / "source_map.json").write_text(json.dumps(source_map, indent=2), encoding="utf-8")
    (paper_dir / "deep_read.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    lenses = set(note_plan.get("active_lenses") or []) | set((data.get("paper_profile") or {}).get("active_lenses") or [])
    if "theory" in lenses and not (paper_dir / "math_index.json").exists():
        _write_math_index(tmp_path, bibkey)


def _write_math_index(tmp_path, bibkey, status="not_needed"):
    paper_dir = tmp_path / "papers" / bibkey
    (paper_dir / "math_index.json").write_text(
        json.dumps(
            {
                "schema_version": "v3-math-index-2026-06",
                "parse_quality": {"quality": "fair", "reasons": [], "metrics": {}},
                "selected_pages": [1],
                "math_page_images": [],
                "text_candidates": [
                    {
                        "id": "M001",
                        "label": "Equation candidate",
                        "page": 1,
                        "section_id": "sec:003",
                        "paragraph_ids": ["p:0003"],
                        "source_kind": "equation",
                        "raw_text": "min J(u)",
                        "cleaned_equation": "min J(u)",
                        "confidence": "medium",
                        "backend": "parsed_text",
                        "notes": "Fixture math candidate.",
                    }
                ],
                "vision_fallback": {
                    "needed": status != "not_needed",
                    "status": status,
                    "reasons": [],
                    "image_paths": [],
                    "instruction": "Use current Codex vision only; do not invent notation.",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_draft_bundle(tmp_path, run_id, bibkey, data=None, source_map=None, note_plan=None):
    draft_dir = tmp_path / ".tmp" / "read_batch" / run_id / "drafts" / bibkey
    draft_dir.mkdir(parents=True, exist_ok=True)
    data = data or json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    source_map = source_map or json.loads(fixture_path("source_map.json").read_text(encoding="utf-8"))
    note_plan = note_plan or json.loads(fixture_path("note_plan.json").read_text(encoding="utf-8"))
    data["bibkey"] = bibkey
    source_map["paper"]["bibkey"] = bibkey
    (draft_dir / "source_map.json").write_text(json.dumps(source_map, indent=2), encoding="utf-8")
    (draft_dir / "note_plan.json").write_text(json.dumps(note_plan, indent=2), encoding="utf-8")
    (draft_dir / "deep_read.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_harvest_finding(tmp_path, run_id, bibkey):
    finding_dir = tmp_path / ".tmp" / "read_batch" / run_id / "findings" / bibkey
    finding_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": READ_HARVEST_SCHEMA_VERSION,
        "role": "paper_evidence_harvest",
        "bibkey": bibkey,
        "producer": {"mode": "test_fixture"},
        "forbidden_inputs_checked": True,
        "allowed_inputs": [f"papers/{bibkey}/metadata.yml", f"papers/{bibkey}/paper_index.json"],
        "forbidden_inputs": [],
        "writes_final_artifacts": False,
        "final_artifacts_written": [],
        "evidence_items": [
            {
                "kind": "method",
                "claim": f"{bibkey} fixture harvest cites paper-specific method evidence.",
                "source_path": f"papers/{bibkey}/paper_index.json",
                "paragraph_ids": ["p:0001"],
                "page": 1,
                "confidence": "high",
            }
        ],
        "critical_facts": {
            "method": [{"id": "method-main", "text": f"{bibkey} has paper-specific method evidence."}],
            "limitations": [{"id": "scope", "text": "Fixture limitation for harvest validation."}],
        },
    }
    (finding_dir / "harvest.json").write_text(json.dumps(record, indent=2), encoding="utf-8")


def _write_draft_worker_record(tmp_path, run_id, bibkey):
    finding_dir = tmp_path / ".tmp" / "read_batch" / run_id / "findings" / bibkey
    finding_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": READ_DRAFT_WORKER_SCHEMA_VERSION,
        "role": "paper_read_draft_worker",
        "run_id": run_id,
        "bibkey": bibkey,
        "producer": {"mode": "test_fixture"},
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
                "claim": f"{bibkey} fixture draft worker cites paper-specific method evidence.",
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
    (finding_dir / "draft_worker.json").write_text(json.dumps(record, indent=2), encoding="utf-8")


class _DraftWorkerWritingRunner:
    def run(self, prompt, cwd, job_dir):
        marker = "Required provenance output: "
        output_line = next(line for line in prompt.splitlines() if line.startswith(marker))
        output_path = cwd / output_line[len(marker):].strip()
        bibkey = next(line for line in prompt.splitlines() if line.startswith("Target bibkey: ")).split(": ", 1)[1]
        run_id = output_path.parts[output_path.parts.index("read_batch") + 1]
        _write_draft_bundle(cwd, run_id, bibkey)
        _write_draft_worker_record(cwd, run_id, bibkey)
        yield CodexEvent(kind="message", payload={"text": "wrote draft worker bundle"})


class _ConcurrentDraftWorkerRunner:
    def __init__(self, shared):
        self.shared = shared

    def run(self, prompt, cwd, job_dir):
        marker = "Required provenance output: "
        output_line = next(line for line in prompt.splitlines() if line.startswith(marker))
        output_path = cwd / output_line[len(marker):].strip()
        bibkey = next(line for line in prompt.splitlines() if line.startswith("Target bibkey: ")).split(": ", 1)[1]
        run_id = output_path.parts[output_path.parts.index("read_batch") + 1]
        with self.shared["condition"]:
            self.shared["active"] += 1
            self.shared["max_active"] = max(self.shared["max_active"], self.shared["active"])
            self.shared["condition"].notify_all()
            deadline = time.monotonic() + 2.0
            while self.shared["max_active"] < self.shared["expected"] and time.monotonic() < deadline:
                self.shared["condition"].wait(timeout=0.05)
        _write_draft_bundle(cwd, run_id, bibkey)
        _write_draft_worker_record(cwd, run_id, bibkey)
        yield CodexEvent(kind="message", payload={"text": f"concurrent draft worker wrote {bibkey}"})
        with self.shared["condition"]:
            self.shared["active"] -= 1
            self.shared["condition"].notify_all()


class _FailIfCalledRunner:
    def run(self, prompt, cwd, job_dir):
        raise AssertionError("runner should not be called for already complete staged drafts")


class _PartialDraftRunner:
    def run(self, prompt, cwd, job_dir):
        marker = "Required provenance output: "
        output_line = next(line for line in prompt.splitlines() if line.startswith(marker))
        output_path = cwd / output_line[len(marker):].strip()
        bibkey = next(line for line in prompt.splitlines() if line.startswith("Target bibkey: ")).split(": ", 1)[1]
        run_id = output_path.parts[output_path.parts.index("read_batch") + 1]
        draft_dir = cwd / ".tmp" / "read_batch" / run_id / "drafts" / bibkey
        draft_dir.mkdir(parents=True, exist_ok=True)
        (draft_dir / "source_map.json").write_text("{}", encoding="utf-8")
        yield CodexEvent(kind="message", payload={"text": "wrote partial source map only"})


class _RecordingDraftWorkerRunner(_DraftWorkerWritingRunner):
    def __init__(self, prompts):
        self.prompts = prompts

    def run(self, prompt, cwd, job_dir):
        self.prompts.append(prompt)
        yield from super().run(prompt, cwd, job_dir)


def _theory_survey_bundle():
    data = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    source_map = json.loads(fixture_path("source_map.json").read_text(encoding="utf-8"))
    note_plan = json.loads(fixture_path("note_plan.json").read_text(encoding="utf-8"))
    data["paper_profile"] = {
        "primary_type": "survey",
        "active_lenses": ["survey", "method", "theory"],
        "confidence": "high",
        "rationale": "Fixture exercises mixed survey and theory reading.",
    }
    note_plan["primary_type"] = "survey"
    note_plan["active_lenses"] = ["survey", "method", "theory"]
    source_map["blocks"].extend(
        [
            {"id": "S007", "page": 1, "section": "Theory", "section_id": "sec:003", "paragraph_ids": ["p:0003"], "type": "equation", "source_kind": "equation", "source_text": "min J(u) subject to xdot=f(t,x,u)", "confidence": "high", "notes": "Cleaned optimal-control problem form."},
            {"id": "S008", "page": 1, "section": "Theory", "section_id": "sec:003", "paragraph_ids": ["p:0003"], "type": "equation", "source_kind": "equation", "source_text": "G(z0)=R(z0,z(T,z0))=0", "confidence": "high", "notes": "Cleaned shooting-function form."},
            {"id": "S009", "page": 1, "section": "Survey", "section_id": "sec:003", "paragraph_ids": ["p:0003"], "type": "method_family", "source_kind": "body_text", "source_text": "The paper compares direct methods, shooting, and HJB.", "confidence": "high", "notes": ""},
        ]
    )
    data["theory_understanding"] = {
        "problem_formulation": {"text": "The paper formulates finite-dimensional ODE optimal control as minimizing a terminal/running cost under state dynamics and constraints.", "source_refs": ["S007"], "confidence": "high"},
        "key_equations": [
            {"label": "ODE optimal-control problem", "equation": "minimize J(u)\nsubject to xdot = f(t, x, u)", "explanation": "The control is chosen to optimize cost while respecting ODE dynamics.", "source_refs": ["S007"], "confidence": "high"},
            {"label": "Shooting function", "equation": "G(z0) = R(z0, z(T, z0)) = 0", "explanation": "The boundary-value problem becomes a root-finding problem over the initial adjoint/state guess.", "source_refs": ["S008"], "confidence": "high"},
        ],
        "theorem_or_principle_chain": [
            {"principle": "Pontryagin maximum principle", "role": "Turns optimality into extremal equations.", "intuition": "Only trajectories satisfying the adjoint and maximization conditions can be optimal candidates.", "source_refs": ["S008"], "confidence": "high"}
        ],
        "assumptions": [{"text": "The cleaned equations assume enough regularity for PMP-style reasoning.", "source_refs": ["S008"], "confidence": "medium"}],
        "key_results": [{"text": "Single shooting solves a boundary-value problem through a root map; multiple shooting adds matching nodes.", "source_refs": ["S008"], "confidence": "high"}],
        "engineering_proof_sketch": {"text": "The engineering path is problem -> optimality conditions -> boundary-value problem -> root solve.", "source_refs": ["S007", "S008"], "confidence": "high"},
        "limitations": [{"text": "Initialization and switching-structure knowledge remain fragile.", "source_refs": ["S008"], "confidence": "high"}],
    }
    data["survey_understanding"] = {
        "scope": {"text": "The survey compares numerical method families for ODE optimal control.", "source_refs": ["S009"], "confidence": "high"},
        "taxonomy": [
            {"text": "Direct methods discretize first and solve an NLP.", "source_refs": ["S009"], "confidence": "high"},
            {"text": "Indirect shooting applies optimality conditions first.", "source_refs": ["S008"], "confidence": "high"},
            {"text": "HJB methods compute value-function information.", "source_refs": ["S009"], "confidence": "high"},
        ],
        "method_family_matrix": [
            {"family": "Direct transcription", "core_idea": "Discretize dynamics and optimize a finite NLP.", "strengths": "Constraint-friendly and easy to implement.", "limitations": "Can be local and mesh-sensitive.", "best_for": "Obtaining robust coarse structure.", "source_refs": ["S009"], "confidence": "high"},
            {"family": "Shooting", "core_idea": "Solve PMP-derived boundary equations.", "strengths": "High accuracy when initialized well.", "limitations": "Sensitive to initial guesses.", "best_for": "Refining known structures.", "source_refs": ["S008"], "confidence": "high"},
            {"family": "HJB", "core_idea": "Approximate a value function.", "strengths": "Global information and feedback structure.", "limitations": "High-dimensional cost.", "best_for": "Global initialization and sanity checks.", "source_refs": ["S009"], "confidence": "high"},
        ],
        "timeline_milestones": [
            {"text": "1950s: PMP and dynamic programming establish the main optimal-control principles.", "source_refs": ["S009"], "confidence": "medium"},
            {"text": "1980s: viscosity solutions make nonsmooth HJB value functions usable.", "source_refs": ["S009"], "confidence": "medium"},
            {"text": "Recent methods: optimistic planning searches control-space partitions.", "source_refs": ["S009"], "confidence": "medium"},
        ],
        "coverage_gaps": [{"text": "The fixture does not attempt a complete historical bibliography.", "source_refs": ["S009"], "confidence": "high"}],
    }
    type_sections = data["translations"]["zh"].setdefault("type_sections", {})
    type_sections["theory_understanding"] = {
        "problem_formulation": "论文把有限维 ODE 最优控制表述为在状态动力学和约束下最小化终端/运行代价。",
        "key_equations": [
            {"label": "ODE 最优控制问题", "explanation": "选择控制以在满足 ODE 动力学的同时优化代价。"},
            {"label": "Shooting function", "explanation": "边值问题被转化为关于初始伴随/状态猜测的根求解问题。"},
        ],
        "theorem_or_principle_chain": [
            {"principle": "Pontryagin maximum principle", "role": "把最优性转化为极值方程。", "intuition": "只有满足伴随和极大化条件的轨线才是最优候选。"}
        ],
        "assumptions": ["清洗后的方程假设正则性足以支持 PMP 式推理。"],
        "key_results": ["Single shooting 通过根映射求解边值问题；multiple shooting 增加匹配节点。"],
        "engineering_proof_sketch": "工程路径是：问题 -> 最优性条件 -> 边值问题 -> 根求解。",
        "limitations": ["初始化和切换结构知识仍然脆弱。"],
    }
    type_sections["survey_understanding"] = {
        "scope": "综述比较 ODE 最优控制的数值方法族。",
        "taxonomy": ["直接法先离散再求解 NLP。", "间接 shooting 先应用最优性条件。", "HJB 方法计算 value-function 信息。"],
        "method_family_matrix": [
            {"family": "直接转录", "core_idea": "离散动力学并优化有限维 NLP。", "strengths": "约束友好且容易实现。", "limitations": "可能局部且依赖网格。", "best_for": "获得鲁棒粗结构。"},
            {"family": "Shooting", "core_idea": "求解 PMP 导出的边界方程。", "strengths": "初始化好时精度高。", "limitations": "对初值敏感。", "best_for": "细化已知结构。"},
            {"family": "HJB", "core_idea": "近似 value function。", "strengths": "提供全局信息和反馈结构。", "limitations": "高维代价高。", "best_for": "全局初始化和校验。"},
        ],
        "timeline_milestones": ["1950s：PMP 和 dynamic programming 建立主要最优控制原理。", "1980s：viscosity solutions 使非光滑 HJB value function 可用。", "较新的方法：optimistic planning 搜索控制空间划分。"],
        "coverage_gaps": ["fixture 不试图给出完整历史文献表。"],
    }
    return data, source_map, note_plan


def test_parse_validate_and_rebuild_note(tmp_path):
    bibkey = _promoted_topic(tmp_path)

    parse_result = parse_pdf(tmp_path, bibkey)
    _write_reading_bundle(tmp_path, bibkey)
    assert parse_result["ok"] is True
    assert parse_result["visual_index"] == f"papers/{bibkey}/visual_index.md"
    assert parse_result["paper_index"] == f"papers/{bibkey}/paper_index.json"
    assert parse_result["math_index"] == f"papers/{bibkey}/math_index.json"
    assert (tmp_path / "papers" / bibkey / "paper_index.json").exists()
    assert (tmp_path / "papers" / bibkey / "math_index.json").exists()
    assert (tmp_path / "papers" / bibkey / "visual_index.md").exists()
    assert parse_result["visual_ok"] is True
    assert parse_result["page_images"]
    assert (tmp_path / parse_result["page_images"][0]).exists()
    assert parse_result["contact_sheet"] == f"papers/{bibkey}/page_images/contact_sheet.jpg"
    assert (tmp_path / parse_result["contact_sheet"]).exists()
    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True
    note = rebuild_note(tmp_path, bibkey)
    assert note["ok"] is True
    text = (tmp_path / "papers" / bibkey / "note.md").read_text()
    assert "## Argument Map" in text
    assert "## Central Claims" in text
    assert "## Visual Cards" in text
    zh_text = (tmp_path / "papers" / bibkey / "note_zh.md").read_text()
    assert "## 论证地图" in zh_text
    assert "## 方法理解" in zh_text
    assert "## 实验评估" in zh_text
    assert "## 图表卡片" in zh_text
    assert "## 可用性" in zh_text
    assert "这是一篇用于测试" in zh_text


def test_parse_pdf_writes_math_index_with_vision_fallback_contract(tmp_path):
    bibkey = _promoted_topic(tmp_path)

    parse_result = parse_pdf(tmp_path, bibkey)
    math_index = json.loads((tmp_path / "papers" / bibkey / "math_index.json").read_text(encoding="utf-8"))

    assert parse_result["math_parse_quality"] in {"good", "fair", "poor"}
    assert math_index["schema_version"] == "v3-math-index-2026-06"
    assert "parse_quality" in math_index
    assert "vision_fallback" in math_index
    assert isinstance(math_index["vision_fallback"]["needed"], bool)
    assert "do not invent notation" in math_index["vision_fallback"]["instruction"].lower()


def test_parse_pdf_repairs_stale_source_map_paragraph_refs(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    first = parse_pdf(tmp_path, bibkey)
    paper_dir = tmp_path / "papers" / bibkey
    paper_index = json.loads((paper_dir / "paper_index.json").read_text(encoding="utf-8"))
    paragraph = paper_index["paragraphs"][0]
    stale_source_map = {
        "schema_version": "v3-source-map-2026-06",
        "paper": {
            "bibkey": bibkey,
            "pdf_path": f"papers/{bibkey}/paper.pdf",
            "parsed_markdown_path": f"papers/{bibkey}/parsed.md",
        },
        "blocks": [
            {
                "id": "S001",
                "page": 99,
                "section": "Old",
                "section_id": "sec:stale",
                "paragraph_ids": ["p:9999"],
                "type": "claim",
                "source_kind": "body_text",
                "source_text": paragraph["text"][:300],
                "confidence": "high",
                "notes": "stale paragraph ref",
            }
        ],
    }
    (paper_dir / "source_map.json").write_text(json.dumps(stale_source_map, indent=2), encoding="utf-8")

    second = parse_pdf(tmp_path, bibkey)
    repaired = json.loads((paper_dir / "source_map.json").read_text(encoding="utf-8"))

    assert first["ok"] is True
    assert second["ok"] is True
    assert repaired["blocks"][0]["paragraph_ids"] == [paragraph["paragraph_id"]]
    assert repaired["blocks"][0]["section_id"] == paragraph["section_id"]


def test_rebuild_note_renders_lens_specific_deep_read_fields(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data.update(
        {
            "paper_profile": {
                "primary_type": "method",
                "active_lenses": ["method", "application"],
                "confidence": "high",
                "rationale": "Fixture exercises mixed-lens rendering.",
            },
            "quick_read": [{"text": "Fast takeaway with evidence.", "source_refs": ["S001"], "confidence": "high"}],
            "central_claims": [
                {
                    "claim": "The fixture supports evidence-grounded reading artifacts.",
                    "evidence_summary": "Validated JSON and rebuilt Markdown note.",
                    "source_refs": ["S004"],
                    "what_it_proves": "The local pipeline renders structured claims.",
                    "what_it_does_not_prove": "It does not prove scientific novelty.",
                    "open_question": "How well does the parser handle complex PDFs?",
                    "confidence": "high",
                }
            ],
            "visual_cards": [
                {
                    "label": "Figure 1",
                    "kind": "method_overview",
                    "page": 1,
                    "image_path": f"papers/{bibkey}/page_images/page-001.png",
                    "source_caption": "Fixture page.",
                    "placement_section": "method_understanding",
                    "placed_near": "S003",
                    "reading_note": "Shows the fixture page used for visual grounding.",
                    "crop_status": "full_page_approximate",
                    "source_refs": ["F001", "C001"],
                }
            ],
            "method_understanding": {
                "pipeline": [{"text": "Parse text and render page images.", "source_refs": ["S003"], "confidence": "high"}],
                "algorithm_pseudocode": "Input PDF\nParse text and render page images\nValidate JSON report\nRebuild note",
                "algorithm_steps": [
                    {"step": 1, "action": "Parse text and render page images.", "inputs": "PDF", "outputs": "parsed text and images", "source_refs": ["S003"]},
                    {"step": 2, "action": "Validate JSON report.", "inputs": "source map", "outputs": "validated report", "source_refs": ["S004"]},
                ],
                "engineering_derivation_sketch": {
                    "text": "The proof obligation is reduced to checking each generated artifact against a schema.",
                    "source_refs": ["S004"],
                    "confidence": "high",
                },
                "implementation_details": [{"text": "Use paper-centric artifact paths.", "source_refs": ["S003"], "confidence": "high"}],
            },
        }
    )
    _write_reading_bundle(tmp_path, bibkey, data=data)

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True
    note = rebuild_note(tmp_path, bibkey)
    assert note["ok"] is True
    text = (tmp_path / "papers" / bibkey / "note.md").read_text()
    assert "Profile: method | lenses: method, application" in text
    assert "## Quick Read" in text
    assert "## Central Claims" in text
    assert "What it does not prove" in text
    assert "## Visual Cards" in text
    assert "## Algorithm Steps" in text
    assert "## Engineering Derivation Sketch" in text
    assert "## Application Understanding" in text
    assert "## Reading Plan" not in text
    assert "### Numeric Results" in text
    assert "## Availability" in text
    assert "## Extraction Notes" in text


def test_rebuild_zh_note_renders_structured_translation_objects_as_text(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data, source_map, note_plan = _theory_survey_bundle()
    zh = data["translations"]["zh"]
    zh["method_understanding"]["engineering_derivation_sketch"] = {
        "text": "中文工程推导文本：先建立问题，再把条件转成可求解的边界或演化系统。",
        "source_refs": ["S004"],
        "confidence": "high",
    }
    zh["type_sections"]["theory_understanding"]["engineering_proof_sketch"] = {
        "text": "中文理论证明文本：从假设出发构造最优性条件，再解释这些条件如何对应数值求解流程。",
        "source_refs": ["S007", "S008"],
        "confidence": "high",
    }
    _write_reading_bundle(tmp_path, bibkey, data=data, source_map=source_map, note_plan=note_plan)

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True
    note = rebuild_note(tmp_path, bibkey)
    assert note["ok"] is True
    zh_text = (tmp_path / "papers" / bibkey / "note_zh.md").read_text(encoding="utf-8")

    assert "中文工程推导文本" in zh_text
    assert "中文理论证明文本" in zh_text
    assert "{'text'" not in zh_text
    assert "### source refs" not in zh_text.lower()
    assert "['S007" not in zh_text
    assert "confidence':" not in zh_text
    assert "- confidence:" not in zh_text.lower()


def test_deep_read_contract_accepts_theory_equations_and_survey_matrix(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data, source_map, note_plan = _theory_survey_bundle()
    _write_reading_bundle(tmp_path, bibkey, data=data, source_map=source_map, note_plan=note_plan)

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True
    note = rebuild_note(tmp_path, bibkey)
    assert note["ok"] is True
    text = (tmp_path / "papers" / bibkey / "note.md").read_text()
    assert "ODE optimal-control problem | minimize J(u)" in text
    assert "Direct transcription | Discretize dynamics" in text


def test_structured_v2_dataset_validates_and_renders_bilingual_tables(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    _write_reading_bundle(tmp_path, bibkey)

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True
    assert rebuild_note(tmp_path, bibkey)["ok"] is True

    note = (tmp_path / "papers" / bibkey / "note.md").read_text(encoding="utf-8")
    zh_note = (tmp_path / "papers" / bibkey / "note_zh.md").read_text(encoding="utf-8")
    assert "### Key Numbers" in note
    assert "| Label | Value | Unit | Context | Source refs |" in note
    assert "### Construction Steps" in note
    assert "### Biases Or Limits" in note
    assert "Evidence-supported central claims" in note
    assert "### 关键数字" in zh_note
    assert "| 名称 | 数值 | 单位 | 说明 | 来源 |" in zh_note
    assert "### 构建步骤" in zh_note
    assert "### 偏差与局限" in zh_note
    assert "有证据支持的核心主张" in zh_note


def test_structured_v2_dataset_rejects_empty_source_refs_on_every_row_type(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    for section in ["key_numbers", "construction_steps", "biases_or_limits"]:
        data = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
        data["dataset_benchmark_understanding"][section][0]["source_refs"] = []
        _write_reading_bundle(tmp_path, bibkey, data=data)
        result = validate_deep_read_report(tmp_path, bibkey)
        assert result["ok"] is False, section


def test_structured_v2_dataset_rejects_non_mirroring_zh_structure(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    zh_dataset = data["translations"]["zh"]["type_sections"]["dataset_benchmark_understanding"]
    zh_dataset["key_numbers"][0].pop("context")
    zh_dataset["construction_steps"] = []
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])
    assert result["ok"] is False
    assert "dataset_benchmark_understanding.key_numbers[0].context" in errors
    assert "dataset_benchmark_understanding.construction_steps must mirror 1 rows" in errors


def test_structured_v2_dataset_zh_rows_do_not_duplicate_language_neutral_fields(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    zh_dataset = data["translations"]["zh"]["type_sections"]["dataset_benchmark_understanding"]
    zh_dataset.pop("format", None)
    for row in zh_dataset["key_numbers"]:
        row.pop("value", None)
        row.pop("unit", None)
        row.pop("source_refs", None)
    for row in zh_dataset["construction_steps"]:
        row.pop("source_refs", None)
    _write_reading_bundle(tmp_path, bibkey, data=data)

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True
    assert rebuild_note(tmp_path, bibkey)["ok"] is True
    zh_note = (tmp_path / "papers" / bibkey / "note_zh.md").read_text(encoding="utf-8")
    assert "| 有证据支持的核心主张 | 1 | claim |" in zh_note


def test_structured_v2_dataset_rejects_short_english_copy_in_zh_row(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    data["dataset_benchmark_understanding"]["construction_steps"][0]["action"] = "Filter records."
    data["translations"]["zh"]["type_sections"]["dataset_benchmark_understanding"]["construction_steps"][0]["action"] = "Filter records."
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "copies short English source text" in "\n".join(result["errors"])


def test_structured_v2_dataset_allows_omitted_zh_for_empty_optional_quality_control(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    data["dataset_benchmark_understanding"]["construction_steps"][0]["quality_control"] = ""
    data["translations"]["zh"]["type_sections"]["dataset_benchmark_understanding"]["construction_steps"][0].pop("quality_control")
    _write_reading_bundle(tmp_path, bibkey, data=data)

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True


def test_legacy_dataset_section_continues_to_validate(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    data["dataset_benchmark_understanding"] = {
        "data_construction": [{"text": "Build the fixture from a local PDF.", "source_refs": ["S003"]}],
        "statistics": [{"text": "The fixture has one supported central claim.", "source_refs": ["S004"]}],
        "availability": {"text": "The fixture is stored with the test artifacts.", "source_refs": ["S003"]},
        "biases_or_limits": [{"text": "The fixture is intentionally minimal.", "source_refs": ["S005"]}],
    }
    data["translations"]["zh"]["type_sections"]["dataset_benchmark_understanding"] = {
        "data_construction": ["从本地 PDF 构建该 fixture。"],
        "statistics": ["该 fixture 包含一条有证据支持的核心主张。"],
        "availability": "该 fixture 与测试产物存放在一起。",
        "biases_or_limits": ["该 fixture 经过刻意简化。"],
    }
    _write_reading_bundle(tmp_path, bibkey, data=data)

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True


def test_deep_read_contract_rejects_theory_without_key_equations(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data, source_map, note_plan = _theory_survey_bundle()
    data["theory_understanding"]["key_equations"] = []
    _write_reading_bundle(tmp_path, bibkey, data=data, source_map=source_map, note_plan=note_plan)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "key_equations" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_active_theory_without_math_index(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data, source_map, note_plan = _theory_survey_bundle()
    _write_reading_bundle(tmp_path, bibkey, data=data, source_map=source_map, note_plan=note_plan)
    (tmp_path / "papers" / bibkey / "math_index.json").unlink()

    result = validate_deep_read_report(tmp_path, bibkey)

    assert result["ok"] is False
    assert "missing math_index.json" in "\n".join(result["errors"])


def test_deep_read_contract_allows_missing_equations_only_after_vision_blocker(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data, source_map, note_plan = _theory_survey_bundle()
    data["theory_understanding"]["key_equations"] = []
    data["extraction_notes"]["low_confidence_equations"] = ["Parser and vision fallback could not recover formulas safely."]
    data["translations"]["zh"]["extraction_notes"]["low_confidence_equations"] = ["解析器和视觉兜底都无法安全恢复公式。"]
    _write_reading_bundle(tmp_path, bibkey, data=data, source_map=source_map, note_plan=note_plan)
    (tmp_path / "papers" / bibkey / "math_index.json").write_text(
        json.dumps(
            {
                "schema_version": "v3-math-index-2026-06",
                "parse_quality": {"quality": "poor", "reasons": ["formula_text_polluted_section_detection"], "metrics": {}},
                "selected_pages": [1],
                "math_page_images": [],
                "text_candidates": [],
                "vision_fallback": {
                    "needed": True,
                    "status": "blocked",
                    "reasons": ["no readable math page images were available"],
                    "image_paths": [],
                    "instruction": "Use current Codex vision only; do not invent notation.",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True


def test_deep_read_contract_requires_pending_formula_vision_to_run(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data, source_map, note_plan = _theory_survey_bundle()
    _write_reading_bundle(tmp_path, bibkey, data=data, source_map=source_map, note_plan=note_plan)
    _write_math_index(tmp_path, bibkey, status="pending")

    result = validate_deep_read_report(tmp_path, bibkey)

    assert result["ok"] is False
    assert "vision_fallback is pending" in "\n".join(result["errors"])


def test_source_map_accepts_math_image_evidence_block(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data, source_map, note_plan = _theory_survey_bundle()
    math_dir = tmp_path / "papers" / bibkey / "math_pages"
    math_dir.mkdir(parents=True, exist_ok=True)
    (math_dir / "page-001.png").write_bytes(b"not a real png but enough for path checks")
    source_map["blocks"].append(
        {
            "id": "M001",
            "page": 1,
            "section": "Theory",
            "section_id": "sec:003",
            "paragraph_ids": [],
            "type": "equation",
            "source_kind": "equation",
            "source_text": "Vision transcription of a visible optimal-control equation.",
            "latex": "\\\\min_u J(u)",
            "image_path": f"papers/{bibkey}/math_pages/page-001.png",
            "backend": "codex_vision",
            "confidence": "medium",
            "notes": "Formula came from the rendered math page image.",
        }
    )
    data["theory_understanding"]["key_equations"][0]["source_refs"] = ["M001"]
    _write_reading_bundle(tmp_path, bibkey, data=data, source_map=source_map, note_plan=note_plan)

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True


def test_deep_read_contract_rejects_survey_without_method_family_matrix(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data, source_map, note_plan = _theory_survey_bundle()
    data["survey_understanding"]["method_family_matrix"] = []
    _write_reading_bundle(tmp_path, bibkey, data=data, source_map=source_map, note_plan=note_plan)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "method_family_matrix" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_missing_theory_equation_zh_fields(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data, source_map, note_plan = _theory_survey_bundle()
    data["translations"]["zh"]["type_sections"]["theory_understanding"]["key_equations"][0].pop("explanation")
    _write_reading_bundle(tmp_path, bibkey, data=data, source_map=source_map, note_plan=note_plan)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "translations.zh.type_sections.theory_understanding.key_equations[0].explanation" in errors


def test_deep_read_contract_rejects_missing_theory_chain_zh_fields(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data, source_map, note_plan = _theory_survey_bundle()
    data["translations"]["zh"]["type_sections"]["theory_understanding"]["theorem_or_principle_chain"][0].pop("intuition")
    _write_reading_bundle(tmp_path, bibkey, data=data, source_map=source_map, note_plan=note_plan)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "translations.zh.type_sections.theory_understanding.theorem_or_principle_chain[0].intuition" in errors


def test_deep_read_contract_rejects_missing_survey_matrix_zh_fields(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data, source_map, note_plan = _theory_survey_bundle()
    data["translations"]["zh"]["type_sections"]["survey_understanding"]["method_family_matrix"][0].pop("core_idea")
    _write_reading_bundle(tmp_path, bibkey, data=data, source_map=source_map, note_plan=note_plan)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "translations.zh.type_sections.survey_understanding.method_family_matrix[0].core_idea" in errors


def test_deep_read_schema_rejects_unknown_extra_field(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["unexpected"] = "no"
    _write_reading_bundle(tmp_path, bibkey, data=data)

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is False


def test_deep_read_schema_accepts_reading_quality_limitations(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["reading_quality"] = {
        "status": "accepted_with_limitations",
        "acceptance_reason": "max_cycles_reached",
        "cycles_used": 7,
        "open_issues": ["Reviewer still requested a more concrete limitation statement."],
        "controller_warnings": ["Accepted only because --accept-last-on-max-cycles was set."],
    }
    _write_reading_bundle(tmp_path, bibkey, data=data)

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True


def test_deep_read_contract_rejects_unexplained_visual_placeholder(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["visual_cards"][0]["crop_status"] = "placeholder"
    data["visual_cards"][0].pop("placeholder_reason", None)
    data["visual_cards"][0].pop("image_path", None)
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "placeholder_reason" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_unknown_source_ref(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["quick_read"][0]["source_refs"] = ["p.1 S999"]
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "S999" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_missing_reader_facing_zh_translation(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["translations"]["zh"]["availability"]["code"].pop("evidence")
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "translations.zh.availability.code.evidence" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_copied_english_zh_translation(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["translations"]["zh"]["quick_read"][0] = data["quick_read"][0]["text"]
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    errors = "\n".join(result["errors"])
    assert "translations.zh.quick_read[0]" in errors
    assert "copies English" in errors or "must be Chinese" in errors


def test_deep_read_contract_rejects_english_workflow_leakage(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["quick_read"][0]["text"] = (
        "This reread uses selected evidence and an evidence block rather than a reader-facing interpretation."
    )
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)

    assert result["ok"] is False
    assert "template-like reading prose: quick_read[0].text" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_parser_residue_in_reader_text(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["argument_map"]["method_logic"]["text"] = "The bound uses L<sup>2</sup> approximation with corrupted � symbols."
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)

    assert result["ok"] is False
    assert "reader-facing text contains parser residue: argument_map.method_logic.text" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_lazy_zh_translation(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["translations"]["zh"]["quick_read"] = [
        "要点1：该论文从流匹配或连续生成建模的具体问题出发，相关结论需要结合英文证据中的 source_refs 理解。",
        "要点2：该论文从流匹配或连续生成建模的具体问题出发，相关结论需要结合英文证据中的 source_refs 理解。",
        "要点3：该论文从流匹配或连续生成建模的具体问题出发，相关结论需要结合英文证据中的 source_refs 理解。",
    ]
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)

    assert result["ok"] is False
    errors = "\n".join(result["errors"])
    assert "lazy zh translation: translations.zh.quick_read[0]" in errors
    assert "repeats generic items" in errors


def test_deep_read_contract_allows_chinese_with_technical_terms(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["translations"]["zh"]["quick_read"][0] = (
        "论文把 flow matching 的误差界限拆成训练误差、速度场 Lipschitz 常数和数据分布正则性三部分来解释。"
    )
    _write_reading_bundle(tmp_path, bibkey, data=data)

    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True


def test_deep_read_contract_rejects_missing_active_type_section_zh(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["translations"]["zh"]["type_sections"].pop("application_understanding")
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "translations.zh.type_sections.application_understanding" in "\n".join(result["errors"])


def test_deep_read_contract_requires_note_plan(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    _write_reading_bundle(tmp_path, bibkey)
    (tmp_path / "papers" / bibkey / "note_plan.json").unlink()

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "missing note_plan.json" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_unknown_source_coordinates(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    source_map = json.loads(fixture_path("source_map.json").read_text())
    source_map["blocks"][0]["section_id"] = "sec:missing"
    source_map["blocks"][1]["paragraph_ids"] = ["p:9999"]
    _write_reading_bundle(tmp_path, bibkey, source_map=source_map)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    errors = "\n".join(result["errors"])
    assert "unknown section_id sec:missing" in errors
    assert "unknown paragraph_id p:9999" in errors


def test_deep_read_contract_rejects_note_plan_type_mismatch(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    note_plan = json.loads(fixture_path("note_plan.json").read_text())
    note_plan["primary_type"] = "survey"
    note_plan["active_lenses"] = ["survey"]
    _write_reading_bundle(tmp_path, bibkey, note_plan=note_plan)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "primary_type must match" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_lens_without_required_section(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    note_plan = json.loads(fixture_path("note_plan.json").read_text())
    data["paper_profile"]["active_lenses"] = ["method", "theory"]
    note_plan["active_lenses"] = ["method", "theory"]
    _write_reading_bundle(tmp_path, bibkey, data=data, note_plan=note_plan)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "theory_understanding is required" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_numeric_percent_out_of_range(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["evaluation"]["numeric_results"][0]["unit"] = "%"
    data["evaluation"]["numeric_results"][0]["value"] = 120
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "between 0 and 100" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_internal_numeric_metadata(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["evaluation"]["numeric_results"][0]["dataset_or_task"] = "Parsed PDF"
    data["evaluation"]["numeric_results"][0]["metric"] = "rendered pages"
    data["evaluation"]["numeric_results"][0]["interpretation"] = "The parser rendered one page."
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "paper content" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_visual_page_mismatch(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["visual_cards"][0]["page"] = 2
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "page must match" in "\n".join(result["errors"])


def test_deep_read_contract_requires_structured_algorithm_steps(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["method_understanding"].pop("algorithm_steps", None)
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    assert result["ok"] is False
    assert "algorithm_steps are required" in "\n".join(result["errors"])


def test_deep_read_contract_accepts_external_availability_source_ref(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["availability"]["code"] = {
        "status": "available",
        "url": "https://github.com/example/fixture-paper",
        "evidence": "External GitHub lookup found a repository URL for the fixture paper.",
        "source_refs": ["External lookup E001"],
        "notes": "External retrieval fixture.",
    }
    data["translations"]["zh"]["availability"]["code"] = {
        "evidence": "外部 GitHub 检索找到了该 fixture 论文的仓库 URL。",
        "notes": "这是外部检索 fixture。",
    }
    _write_reading_bundle(tmp_path, bibkey, data=data)

    assert SOURCE_REF_RE.search("External lookup E001").group(0) == "E001"
    assert validate_deep_read_report(tmp_path, bibkey)["ok"] is True


def test_deep_read_contract_rejects_missing_external_source_ref(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["availability"]["code"] = {
        "status": "available",
        "url": "https://github.com/example/fixture-paper",
        "evidence": "External GitHub lookup found a repository URL for the fixture paper.",
        "source_refs": ["External lookup E999"],
        "notes": "External retrieval fixture.",
    }
    data["translations"]["zh"]["availability"]["code"] = {
        "evidence": "外部 GitHub 检索找到了该 fixture 论文的仓库 URL。",
        "notes": "这是外部检索 fixture。",
    }
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)

    assert result["ok"] is False
    assert "E999" in "\n".join(result["errors"])


def test_deep_read_contract_requires_availability_source_refs_for_conclusions(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["availability"]["code"] = {
        "status": "available",
        "url": "https://github.com/example/fixture-paper",
        "evidence": "The code is available from the project repository.",
        "source_refs": [],
        "notes": None,
    }
    data["translations"]["zh"]["availability"]["code"] = {
        "evidence": "代码可从项目仓库获得。"
    }
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)

    assert result["ok"] is False
    assert "availability.code needs source_refs" in "\n".join(result["errors"])


def test_deep_read_contract_requires_source_refs_for_unknown_availability_evidence(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["availability"]["data"] = {
        "status": "unknown",
        "url": None,
        "evidence": "No data link is present in the fixture PDF.",
        "source_refs": [],
        "notes": None,
    }
    data["translations"]["zh"]["availability"]["data"] = {
        "evidence": "fixture PDF 中没有数据链接。"
    }
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)

    assert result["ok"] is False
    assert "availability.data needs source_refs" in "\n".join(result["errors"])


def test_deep_read_contract_requires_external_ref_for_external_availability_claim(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["availability"]["code"] = {
        "status": "not_found",
        "url": None,
        "evidence": "External GitHub and Semantic Scholar lookup did not find a code release.",
        "source_refs": ["S005"],
        "notes": "Checked GitHub search.",
    }
    data["translations"]["zh"]["availability"]["code"] = {
        "evidence": "外部 GitHub 和 Semantic Scholar 检索没有找到代码发布。",
        "notes": "检查了 GitHub 搜索。",
    }
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)

    assert result["ok"] is False
    assert "availability.code external lookup evidence needs an E### source_ref" in "\n".join(result["errors"])


def test_deep_read_contract_requires_external_ref_for_availability_url(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["availability"]["code"] = {
        "status": "available",
        "url": "https://github.com/example/fixture-paper",
        "evidence": "The code is available from the project repository.",
        "source_refs": ["S005"],
        "notes": "Repository URL recorded without an external evidence block.",
    }
    data["translations"]["zh"]["availability"]["code"] = {
        "evidence": "代码可从项目仓库获得。",
        "notes": "记录了仓库 URL 但没有外部证据块。",
    }
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)

    assert result["ok"] is False
    assert "availability.code external lookup evidence needs an E### source_ref" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_malformed_external_source_block(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    source_map = json.loads(fixture_path("source_map.json").read_text())
    for block in source_map["blocks"]:
        if block["id"] == "E001":
            block["source_kind"] = "body_text"
            block["page"] = 1
            block["notes"] = "Missing URL and access metadata."
    _write_reading_bundle(tmp_path, bibkey, source_map=source_map)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "external source block E001 must use source_kind external" in errors
    assert "external source block E001 must have page 0" in errors
    assert "external source block E001 notes must include URL, access date, and query or lookup path" in errors


def test_deep_read_contract_rejects_additional_template_phrases(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["evaluation"]["main_results"][0]["text"] = (
        "The decisive evidence comes from a specific numerical method and should be understood with the paper-specific route."
    )
    data["translations"]["zh"]["quick_read"][0] = "中文解读应突出论文的任务要求，证据来自英文 source refs。"
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "template-like reading prose: evaluation.main_results[0].text" in errors
    assert "lazy zh translation: translations.zh.quick_read[0]" in errors


def test_deep_read_contract_rejects_optimal_control_workflow_pollution(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["one_sentence_summary"] = (
        "Indirect Solution of Inequality Constrained and Singular Optimal Control Problems Via a Simple "
        "Continuation Method should highlight selected evidence instead of reporting the actual paper result."
    )
    data["translations"]["zh"]["one_sentence_summary"] = "中文解读应突出 shooting + continuation，而不是泛泛说最优控制求解。"
    data["translations"]["zh"]["quick_read"][0] = "证据来自对耦合动力学、打靶迭代和数值延拓章节的描述。"
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "template-like reading prose: one_sentence_summary" in errors
    assert "lazy zh translation: translations.zh.one_sentence_summary" in errors
    assert "lazy zh translation: translations.zh.quick_read[0]" in errors


def test_library_reading_audit_rejects_repeated_reader_cards(tmp_path):
    init_topic(tmp_path)
    repeated = (
        "The method links shooting intervals through boundary matching and uses the resulting nonlinear "
        "equations to guide the solver under the stated control assumptions."
    )
    for bibkey in ["Alpha2024A", "Beta2024B", "Gamma2024C"]:
        data = json.loads(fixture_path("deep_read_report.json").read_text())
        data["quick_read"][0]["text"] = repeated
        _write_reading_bundle(tmp_path, bibkey, data=data)

    result = audit_reading_library(tmp_path)

    assert result["ok"] is False
    assert "repeated reader-facing text blocks" in "\n".join(result["errors"])
    repeated_blocks = list(result["repeated_text"].values())
    assert any(block["count"] == 3 and "shooting intervals" in block["text"] for block in repeated_blocks)


def test_library_reading_audit_rejects_two_repeated_reader_cards(tmp_path):
    init_topic(tmp_path)
    repeated = (
        "The method links shooting intervals through boundary matching and uses the resulting nonlinear "
        "equations to guide the solver under the stated control assumptions."
    )
    for bibkey in ["Alpha2024A", "Beta2024B"]:
        data = json.loads(fixture_path("deep_read_report.json").read_text())
        data["one_sentence_summary"] = repeated
        _write_reading_bundle(tmp_path, bibkey, data=data)

    result = audit_reading_library(tmp_path)

    assert result["ok"] is False
    assert "across >= 2 papers" in "\n".join(result["errors"])


def test_quality_audit_scans_generated_reading_artifacts_for_prompt_leakage(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    _write_reading_bundle(tmp_path, bibkey)
    paper_dir = tmp_path / "papers" / bibkey
    (paper_dir / "reading_result.html").write_text(
        "<html><body>Hard time budget: finish this one paper within 900 seconds.</body></html>",
        encoding="utf-8",
    )

    result = audit_deep_read_quality(tmp_path, bibkey)

    assert result["ok"] is False
    assert "internal prompt text leaked into generated artifact: reading_result.html" in "\n".join(result["errors"])


def test_quality_audit_rejects_reread_workflow_leakage(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["one_sentence_summary"] = (
        "Grounding Generative Policies in Physics is reread as an application contribution with conclusions "
        "tied to selected motivation, method, result, and limitation evidence."
    )
    data["quick_read"][0]["text"] = (
        "The reread identifies a concrete intervention or analysis route around guided diffusion and physics constraints."
    )
    data["translations"]["zh"]["one_sentence_summary"] = "本次重读把论文写成围绕所选证据的应用贡献。"
    data["translations"]["zh"]["quick_read"][0] = "这次重读识别了一个具体技术路线，读者应结合证据块理解。"
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = audit_deep_read_quality(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "one_sentence_summary" in errors
    assert "quick_read[0].text" in errors
    assert "translations.zh.one_sentence_summary" in errors
    assert result["quality_score"] < 100
    assert "one_sentence_summary" in result["failed_fields"]


def test_quality_audit_rejects_bulk_generator_workflow_leakage(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["one_sentence_summary"] = (
        "A deterministic draft writer built schema-valid drafts from parsed/index-only evidence before read-batch staging finalized the result."
    )
    data["quick_read"][0]["text"] = (
        "The staging helper creates a generic bulk draft generator output rather than a paper-specific interpretation."
    )
    data["translations"]["zh"]["one_sentence_summary"] = "该结果来自 deterministic draft writer 和 schema-valid draft 生成流程。"
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = audit_deep_read_quality(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "internal prompt text leaked into reader prose: one_sentence_summary" in errors
    assert "internal prompt text leaked into reader prose: quick_read[0].text" in errors


def test_validate_report_includes_quality_audit_failures(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["argument_map"]["method_logic"]["text"] = (
        "The method evidence block describes tasks, baselines, or benchmarks and the reported setup, metric, or comparison."
    )
    data["translations"]["zh"]["argument_map"]["method_logic"] = "证据块描述任务、基线或指标，属于所选证据。"
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "template-like reading prose: argument_map.method_logic.text" in errors
    assert "lazy zh translation: translations.zh.argument_map.method_logic" in errors


def test_quality_audit_warns_when_real_paper_evidence_all_page_one(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    paper_index = json.loads(fixture_path("paper_index.json").read_text())
    paper_index["coverage"]["parsed_pages"] = 8
    _write_reading_bundle(tmp_path, bibkey, paper_index=paper_index)

    result = audit_deep_read_quality(tmp_path, bibkey)

    assert result["ok"] is True
    assert any("all on page 1" in warning for warning in result["warnings"])
    assert result["quality_score"] < 100


def test_quality_audit_rejects_generated_artifact_missing_chinese_marker(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    _write_reading_bundle(tmp_path, bibkey)
    paper_dir = tmp_path / "papers" / bibkey
    (paper_dir / "reading_result.html").write_text("<p>【中文翻译缺失】</p>", encoding="utf-8")

    result = audit_deep_read_quality(tmp_path, bibkey)

    assert result["ok"] is False
    assert "missing Chinese translation marker in generated artifact: reading_result.html" in "\n".join(result["errors"])


def test_deep_read_contract_rejects_section_name_only_reader_text(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["quick_read"][0]["text"] = "Abstract"
    data["argument_map"]["gap"]["text"] = "3.1"
    data["method_understanding"]["pipeline"][0]["text"] = "Section 4: Method"
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "section-name-only reader text: quick_read[0].text" in errors
    assert "section-name-only reader text: argument_map.gap.text" in errors
    assert "section-name-only reader text: method_understanding.pipeline[0].text" in errors


def test_read_batch_prepare_creates_draft_manifest(tmp_path):
    bibkey = _promoted_topic(tmp_path)

    result = prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id="unit")

    assert result["ok"] is True
    assert result["run_id"] == "unit"
    assert result["targets"] == [bibkey]
    assert (tmp_path / ".tmp" / "read_batch" / "unit" / "manifest.json").exists()
    assert (tmp_path / ".tmp" / "read_batch" / "unit" / "drafts" / bibkey).is_dir()
    manifest = json.loads((tmp_path / ".tmp" / "read_batch" / "unit" / "manifest.json").read_text())
    assert "Do not read existing deep_read.json" in "\n".join(manifest["instructions"])
    assert manifest["draft_worker_mode"] == "single_paper_optional"
    assert manifest["harvest_mode"] == "single_paper_optional"
    assert result["findings_dir"] == ".tmp/read_batch/unit/findings"


def test_read_batch_prepare_requires_parallel_draft_workers_for_multi_paper_batches(tmp_path):
    init_topic(tmp_path)
    bibkeys = ["Alpha2024A", "Beta2024B", "Gamma2024C"]

    result = prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="multi")

    assert result["ok"] is True
    assert result["draft_worker_mode"] == "parallel_required"
    assert result["harvest_mode"] == "parallel_required"
    assert result["max_parallel_subagents"] == 3
    manifest = json.loads((tmp_path / ".tmp" / "read_batch" / "multi" / "manifest.json").read_text())
    assert manifest["fallback_policy"] == "block_not_sequential"
    assert manifest["final_writer"] == "parallel_sidecar_draft_workers"
    assert manifest["max_parallel_cap"] == 5
    assert manifest["max_parallel_subagents"] == 3
    assert "If parallel draft workers are unavailable" in "\n".join(manifest["instructions"])
    assert "do not spend the worker turn on open-ended evidence exploration" in "\n".join(manifest["instructions"])


def test_read_batch_draft_workers_run_sidecars_and_write_complete_drafts(tmp_path):
    init_topic(tmp_path)
    bibkeys = ["Alpha2024A", "Beta2024B"]
    prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="multi")

    result = run_read_batch_draft_workers(
        tmp_path,
        "multi",
        max_parallel=2,
        runner_factory=lambda: _DraftWorkerWritingRunner(),
    )

    assert result["ok"] is True
    assert result["max_parallel"] == 2
    assert set(result["paper_scale"]) == set(bibkeys)
    assert [item["bibkey"] for item in result["results"]] == bibkeys
    for bibkey in bibkeys:
        assert (tmp_path / ".tmp" / "read_batch" / "multi" / "drafts" / bibkey / "deep_read.json").exists()
        assert (tmp_path / ".tmp" / "read_batch" / "multi" / "findings" / bibkey / "draft_worker.json").exists()
    assert all("paper_scale" in item for item in result["results"])
    for bibkey in bibkeys:
        evidence_pack = tmp_path / ".tmp" / "read_batch" / "multi" / "evidence_packs" / bibkey / "evidence_pack.md"
        assert evidence_pack.exists()
        evidence_text = evidence_pack.read_text(encoding="utf-8")
        assert f"# Evidence Pack: {bibkey}" in evidence_text
        assert "This file is a navigation aid" in evidence_text
        assert "## Paper Scale" in evidence_text
        assert "## Selected Paragraphs" in evidence_text


def test_read_batch_draft_workers_start_in_parallel(tmp_path):
    init_topic(tmp_path)
    bibkeys = ["Alpha2024A", "Beta2024B", "Gamma2024C"]
    prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="parallel")
    shared = {
        "condition": threading.Condition(),
        "active": 0,
        "max_active": 0,
        "expected": len(bibkeys),
    }

    result = run_read_batch_draft_workers(
        tmp_path,
        "parallel",
        max_parallel=3,
        runner_factory=lambda: _ConcurrentDraftWorkerRunner(shared),
    )

    assert result["ok"] is True
    assert result["max_parallel"] == 3
    assert shared["max_active"] == 3
    for item in result["results"]:
        assert item["duration_s"] >= 0
        assert (tmp_path / item["event_log"]).exists()


def test_read_batch_draft_workers_default_five_for_full_batch(tmp_path):
    init_topic(tmp_path)
    bibkeys = ["Alpha2024A", "Beta2024B", "Gamma2024C", "Delta2024D", "Epsilon2024E"]
    prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="five")

    default = run_read_batch_draft_workers(
        tmp_path,
        "five",
        runner_factory=lambda: _DraftWorkerWritingRunner(),
    )

    assert default["ok"] is True
    assert default["max_parallel"] == 5

    prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="five_explicit")
    explicit = run_read_batch_draft_workers(
        tmp_path,
        "five_explicit",
        max_parallel=5,
        runner_factory=lambda: _DraftWorkerWritingRunner(),
    )

    assert explicit["ok"] is True
    assert explicit["max_parallel"] == 5


def test_read_batch_draft_workers_report_partial_artifact_state_on_failure(tmp_path):
    init_topic(tmp_path)
    bibkeys = ["Alpha2024A", "Beta2024B"]
    prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="partial")

    result = run_read_batch_draft_workers(
        tmp_path,
        "partial",
        max_parallel=2,
        runner_factory=lambda: _PartialDraftRunner(),
    )

    assert result["ok"] is False
    assert result["errors"]
    assert set(result["artifact_state"]) == set(bibkeys)
    for bibkey in bibkeys:
        item = next(row for row in result["results"] if row["bibkey"] == bibkey)
        assert item["artifact_state"]["source_map.json"]["exists"] is True
        assert item["artifact_state"]["deep_read.json"]["exists"] is False
        assert result["artifact_state"][bibkey]["draft_worker.json"]["exists"] is False


def test_read_batch_draft_worker_prompt_finishes_after_provenance(tmp_path):
    init_topic(tmp_path)
    run_id = "prompt"
    bibkey = "Alpha2024A"
    prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id=run_id)
    evidence_pack = tmp_path / ".tmp" / "read_batch" / run_id / "evidence_packs" / bibkey / "evidence_pack.md"
    evidence_pack.parent.mkdir(parents=True, exist_ok=True)
    evidence_pack.write_text("# Evidence Pack\n", encoding="utf-8")
    prompt = _build_draft_worker_prompt(
        tmp_path,
        run_id,
        bibkey,
        tmp_path / ".tmp" / "read_batch" / run_id / "drafts" / bibkey,
        tmp_path / ".tmp" / "read_batch" / run_id / "findings" / bibkey / "draft_worker.json",
        evidence_pack_path=evidence_pack,
    )

    assert "immediately write" in prompt
    assert "Do not run `paper_engine read ... --validate-report`" in prompt
    assert "Do not keep working after" in prompt
    assert "Do not inspect project implementation source" in prompt
    assert "src/paper_engine/*.py" in prompt
    assert "Keep command output small" in prompt
    assert "Do not print long paragraph ranges" in prompt
    assert "Do not read `source_map.schema.json` or `note_plan.schema.json`" in prompt
    assert "add an `E###` block to source_map.json" in prompt
    assert '"section_id": "external_availability"' in prompt
    assert "`availability.code.source_refs`" in prompt
    assert "`allowed_inputs` must list only approved paper-local evidence paths" in prompt
    assert "Do not put `AGENTS.md`" in prompt
    assert "Do not use `page: 0`" in prompt
    assert '"paper": {' in prompt
    assert '"blocks": [' in prompt
    assert "Do not invent another source-map schema" in prompt
    assert "Do not use top-level `run_id`, `bibkey`, `title`, `source_refs`, `coverage`, or `figures_and_tables_used`" in prompt
    assert "Project root:" in prompt
    assert "Paper scale summary:" in prompt
    assert "Generated evidence pack:" in prompt
    assert f".tmp/read_batch/{run_id}/evidence_packs/{bibkey}/evidence_pack.md" in prompt
    assert "Before running broad searches, read the generated evidence pack" in prompt
    assert "navigation aid built from approved paper-local evidence" in prompt
    assert "Do not list `.tmp/read_batch/.../evidence_pack.md` in `allowed_inputs`" in prompt
    assert "Do not repeat broad keyword sweeps already covered by the evidence pack" in prompt
    assert "at most three targeted follow-up commands" in prompt
    assert "one complete write phase" in prompt
    assert "Do not assume `jq` is installed" in prompt
    assert "Do not leave only `source_map.json` or `note_plan.json` written" in prompt
    assert "rendered_pages" in prompt
    assert "paper_index_page_label_count" in prompt
    assert "page labels may collapse" in prompt
    assert "before writing deep_read.json" in prompt
    assert "/schemas/deep_read_report.schema.json" in prompt
    assert "Do not search for `skills/` or `schemas/` under the topic root" in prompt
    assert "`argument_map`, `quick_read`, `central_claims`, `method_understanding`, `evaluation`" in prompt
    assert "Do not invent another deep-read schema" in prompt
    assert "`reader_facing`, `problem_setting`, `method_map`" in prompt
    assert "`evaluation.numeric_results[]` must contain only the fields allowed by the schema" in prompt
    assert "`translations.zh.quick_read` must be a list of plain Chinese strings" in prompt
    assert "translate every step object's `action`, `inputs`, and `outputs`" in prompt
    assert "translate every result object's `dataset_or_task`, `metric`, `interpretation`, and `what_it_does_not_prove`" in prompt
    assert "Write `{rel_output}` only after a final self-review" not in prompt
    assert "only after a final self-review of the staged `deep_read.json`" in prompt
    assert "Do not mark `self_review.chinese_complete` true" in prompt
    assert "format it as multiline pseudocode with newline characters" in prompt
    assert "Do not copy `source_map.blocks[].source_text` into reader-facing fields" in prompt
    assert "`availability.code.evidence`, `availability.data.evidence`, and `availability.models.evidence` must interpret" in prompt
    assert "Do not paste the `E###` source block text" in prompt
    assert "Every `quick_read[].text` item must name a concrete paper-specific" in prompt
    assert "identify at least six paper anchors" in prompt
    assert "If a sentence would fit another paper in the same topic after replacing the title" in prompt
    assert "Do not write batch-scaffold or workflow sentences" in prompt
    assert "DPS` 基线" in prompt
    assert "`argument_map.decisive_evidence[].text` must synthesize why the cited evidence is decisive" in prompt
    assert "For `survey_understanding.method_family_matrix`, include only method families with enough evidence" in prompt
    assert "Do not add low-confidence filler rows" in prompt
    assert "Every survey matrix `limitations` field" in prompt
    assert "Do not write generic phrases such as \"evidence is insufficient for detailed comparison.\"" in prompt


def test_read_batch_repair_errors_are_filtered_to_target_bibkey():
    payload = {
        "error": "batch validate-report failed",
        "details": {
            "failed_papers": {
                "Alpha2024A": {"ok": False, "errors": ["missing zh translation: translations.zh.quick_read[4]"]},
                "Beta2024B": {
                    "ok": False,
                    "errors": [
                        "weak zh translation: translations.zh.method_understanding.pipeline[0].text is mostly English",
                        "visual_cards[2] page must match visual/caption source refs",
                    ],
                },
            },
            "repeated_text": {
                "same": {
                    "text": "Generic reusable sentence.",
                    "papers": ["Beta2024B", "Gamma2024C"],
                    "paths": ["quick_read[0].text"],
                }
            },
        },
    }

    errors = _repair_errors_for_bibkey([json.dumps(payload)], "Beta2024B")

    assert "missing zh translation" not in "\n".join(errors)
    assert "pipeline[0].text" in "\n".join(errors)
    assert "visual_cards[2]" in "\n".join(errors)
    assert "repeated_text for Beta2024B" in "\n".join(errors)


def test_read_batch_repair_errors_parse_embedded_failed_papers_payload():
    raw = (
        'batch validate-report failed: details.failed_papers='
        '{"Alpha2024A":{"errors":["alpha only"]},'
        '"Beta2024B":{"errors":["weak zh translation: translations.zh.quick_read[1]",'
        '"visual_cards[2] page must match visual/caption source refs"]}}'
    )

    errors = _repair_errors_for_bibkey([raw], "Beta2024B")

    assert errors == [
        "weak zh translation: translations.zh.quick_read[1]",
        "visual_cards[2] page must match visual/caption source refs",
    ]


def test_read_batch_draft_workers_reuse_complete_staged_drafts_without_runner(tmp_path):
    init_topic(tmp_path)
    bibkeys = ["Alpha2024A", "Beta2024B"]
    prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="reuse")
    for bibkey in bibkeys:
        _write_draft_bundle(tmp_path, "reuse", bibkey)
        _write_draft_worker_record(tmp_path, "reuse", bibkey)

    result = run_read_batch_draft_workers(
        tmp_path,
        "reuse",
        max_parallel=2,
        runner_factory=lambda: _FailIfCalledRunner(),
    )

    assert result["ok"] is True
    assert all(item.get("reused_existing_draft") is True for item in result["results"])


def test_read_batch_draft_workers_repair_mode_targets_one_bibkey(tmp_path):
    init_topic(tmp_path)
    bibkeys = ["Alpha2024A", "Beta2024B"]
    prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="repair")
    for bibkey in bibkeys:
        _write_draft_bundle(tmp_path, "repair", bibkey)
        _write_draft_worker_record(tmp_path, "repair", bibkey)
    prompts = []

    result = run_read_batch_draft_workers(
        tmp_path,
        "repair",
        max_parallel=2,
        repair_bibkeys=["Beta2024B"],
        repair_errors=["template-like reading prose: quick_read[3].text"],
        runner_factory=lambda: _RecordingDraftWorkerRunner(prompts),
    )

    assert result["ok"] is True
    assert result["repair_mode"] is True
    assert result["active_targets"] == ["Beta2024B"]
    assert [item["bibkey"] for item in result["results"]] == ["Beta2024B"]
    assert len(prompts) == 1
    assert "Repair mode:" in prompts[0]
    assert "template-like reading prose: quick_read[3].text" in prompts[0]
    assert "errors below are already filtered to `Beta2024B`" in prompts[0]
    assert "Do not broaden the draft" in prompts[0]
    assert "Do not list staged draft files or `.tmp/read_batch/...` paths in `allowed_inputs`" in prompts[0]


def test_read_batch_draft_workers_normalize_target_bibkey_path_typos(tmp_path):
    init_topic(tmp_path)
    bibkeys = ["Alpha2024A", "Beta2024B"]
    prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="reuse")
    for bibkey in bibkeys:
        (tmp_path / "papers" / bibkey).mkdir(parents=True, exist_ok=True)
        _write_draft_bundle(tmp_path, "reuse", bibkey)
        _write_draft_worker_record(tmp_path, "reuse", bibkey)
    (tmp_path / "papers" / "Alpha2024A" / "formula_vision.json").write_text('{"status":"blocked"}\n', encoding="utf-8")
    path = tmp_path / ".tmp" / "read_batch" / "reuse" / "findings" / "Alpha2024A" / "draft_worker.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["allowed_inputs"].append("papers/Alpha2024/formula_vision.json")
    record["evidence_items"][0]["source_path"] = "papers/Alpha2024/formula_vision.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    result = run_read_batch_draft_workers(
        tmp_path,
        "reuse",
        max_parallel=2,
        runner_factory=lambda: _FailIfCalledRunner(),
    )
    fixed = json.loads(path.read_text(encoding="utf-8"))

    assert result["ok"] is True
    alpha = next(item for item in result["results"] if item["bibkey"] == "Alpha2024A")
    assert any("normalized" in warning for warning in alpha["warnings"])
    assert "papers/Alpha2024A/formula_vision.json" in fixed["allowed_inputs"]
    assert fixed["evidence_items"][0]["source_path"] == "papers/Alpha2024A/formula_vision.json"


def test_read_batch_harvest_alias_runs_draft_workers(tmp_path):
    init_topic(tmp_path)
    bibkeys = ["Alpha2024A", "Beta2024B"]
    prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="multi")

    result = run_read_batch_harvest(
        tmp_path,
        "multi",
        max_parallel=2,
        runner_factory=lambda: _DraftWorkerWritingRunner(),
    )

    assert result["ok"] is True
    for bibkey in bibkeys:
        assert (tmp_path / ".tmp" / "read_batch" / "multi" / "drafts" / bibkey / "source_map.json").exists()


def test_read_batch_rejects_unsafe_run_id(tmp_path):
    bibkey = _promoted_topic(tmp_path)

    assert prepare_read_batch(tmp_path, bibkeys=[bibkey], run_id="../escape")["ok"] is False
    assert finalize_read_batch(tmp_path, "../escape")["ok"] is False


def test_read_batch_prepare_rejects_oversized_batches_with_chunks(tmp_path):
    init_topic(tmp_path)
    bibkeys = [f"Paper2026{i}" for i in range(16)]

    result = prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="too_big")

    assert result["ok"] is False
    assert result["max_targets"] == 5
    assert result["target_count"] == 16
    assert [len(chunk) for chunk in result["suggested_chunks"]] == [5, 5, 5, 1]
    assert result["suggested_chunks"][0] == bibkeys[:5]
    assert result["suggested_chunks"][-1] == bibkeys[15:]


def test_read_batch_finalize_rejects_manifest_drafts_dir_escape(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    result = prepare_read_batch(tmp_path, bibkeys=[bibkey], run_id="unit")
    manifest_path = tmp_path / result["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["drafts_dir"] = "/tmp"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = finalize_read_batch(tmp_path, "unit")

    assert result["ok"] is False
    assert "drafts_dir is outside" in result["error"]


def test_read_batch_finalize_rejects_staging_helper_scripts(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    parse_pdf(tmp_path, bibkey)
    _write_reading_bundle(tmp_path, bibkey)
    prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id="unit")
    source_map = json.loads(fixture_path("source_map.json").read_text())
    source_map["blocks"][0]["notes"] = "Fresh draft still fails because a generator script is present."
    _write_draft_bundle(tmp_path, "unit", bibkey, source_map=source_map)
    helper = tmp_path / ".tmp" / "read_batch" / "unit" / "deterministic_draft_generator.py"
    helper.write_text("print('schema-valid draft helper')\n", encoding="utf-8")

    result = finalize_read_batch(tmp_path, "unit")

    assert result["ok"] is False
    assert result["error"] == "read-batch staging contains unsupported helper or scratch files"
    assert "deterministic_draft_generator.py" in "\n".join(result["errors"])


def test_read_batch_finalize_commits_valid_draft_and_runs_batch_audit(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    parse_pdf(tmp_path, bibkey)
    _write_reading_bundle(tmp_path, bibkey)
    prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id="unit")
    source_map = json.loads(fixture_path("source_map.json").read_text())
    source_map["blocks"][0]["notes"] = "Fresh batch draft used to verify non-noop finalize behavior."
    _write_draft_bundle(tmp_path, "unit", bibkey, source_map=source_map)
    evidence_pack = tmp_path / ".tmp" / "read_batch" / "unit" / "evidence_packs" / bibkey / "evidence_pack.md"
    evidence_pack.parent.mkdir(parents=True, exist_ok=True)
    evidence_pack.write_text("# Evidence Pack\n", encoding="utf-8")

    result = finalize_read_batch(tmp_path, "unit")

    assert result["ok"] is True
    assert f"papers/{bibkey}/deep_read.json" in result["changed"]
    assert any("audit-readings" in item and "pass" in item for item in result["verification"])
    assert result["audit_scope"] == "batch"
    assert result["library_audit"]["skipped"] is True
    assert (tmp_path / "papers" / bibkey / "note.md").exists()


def test_read_batch_finalize_syncs_note_plan_claims_before_validation(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    parse_pdf(tmp_path, bibkey)
    _write_reading_bundle(tmp_path, bibkey)
    prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id="unit")
    data = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    second_claim = dict(data["central_claims"][0])
    second_claim["claim"] = "The batch finalizer can repair internal note-plan coverage before validation."
    second_claim["evidence_summary"] = "The claim uses the same fixture source map while exercising cross-file consistency."
    data["central_claims"].append(second_claim)
    zh_claim = dict(data["translations"]["zh"]["central_claims"][0])
    zh_claim["claim"] = "批量 finalizer 可以在验证前修复 note plan 覆盖关系。"
    zh_claim["evidence_summary"] = "该主张使用同一个 fixture source map 来测试跨文件一致性。"
    data["translations"]["zh"]["central_claims"].append(zh_claim)
    note_plan = json.loads(fixture_path("note_plan.json").read_text(encoding="utf-8"))
    assert len(note_plan["central_claims"]) == 1
    _write_draft_bundle(tmp_path, "unit", bibkey, data=data, note_plan=note_plan)

    result = finalize_read_batch(tmp_path, "unit")
    repaired_note_plan = json.loads((tmp_path / "papers" / bibkey / "note_plan.json").read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert result["preflight_repairs"] == [{"bibkey": bibkey, "fields": ["note_plan.central_claims"]}]
    assert len(repaired_note_plan["central_claims"]) == 2
    assert repaired_note_plan["central_claims"][1] == second_claim["claim"]


def test_read_batch_finalize_sanitizes_common_schema_shape_errors(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    parse_pdf(tmp_path, bibkey)
    _write_reading_bundle(tmp_path, bibkey)
    prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id="unit")
    data = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    data["evaluation"]["numeric_results"][0]["confidence"] = "high"
    data["translations"]["zh"]["quick_read"][0] = {
        "text": data["translations"]["zh"]["quick_read"][0],
        "source_refs": ["S002"],
        "confidence": "high",
    }
    _write_draft_bundle(tmp_path, "unit", bibkey, data=data)

    result = finalize_read_batch(tmp_path, "unit")
    repaired = json.loads((tmp_path / "papers" / bibkey / "deep_read.json").read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert result["preflight_repairs"] == [{"bibkey": bibkey, "fields": ["deep_read.schema_shape"]}]
    assert "confidence" not in repaired["evaluation"]["numeric_results"][0]
    assert isinstance(repaired["translations"]["zh"]["quick_read"][0], str)


def test_read_batch_finalize_repairs_unknown_source_map_section_id(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    parse_pdf(tmp_path, bibkey)
    _write_reading_bundle(tmp_path, bibkey)
    prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id="unit")
    source_map = json.loads(fixture_path("source_map.json").read_text(encoding="utf-8"))
    source_map["blocks"][0]["section_id"] = "sec:metadata"
    _write_draft_bundle(tmp_path, "unit", bibkey, source_map=source_map)

    result = finalize_read_batch(tmp_path, "unit")
    repaired = json.loads((tmp_path / "papers" / bibkey / "source_map.json").read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert result["preflight_repairs"] == [{"bibkey": bibkey, "fields": ["source_map.section_id"]}]
    assert repaired["blocks"][0]["section_id"] != "sec:metadata"


def test_read_batch_finalize_repairs_visual_card_page_mismatch_from_image_path(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    parse_pdf(tmp_path, bibkey)
    paper_dir = tmp_path / "papers" / bibkey
    page_001 = paper_dir / "page_images" / "page-001.png"
    page_021 = paper_dir / "page_images" / "page-021.png"
    if page_001.exists():
        shutil.copy2(page_001, page_021)
    _write_reading_bundle(tmp_path, bibkey)
    prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id="unit")
    data = json.loads(fixture_path("deep_read_report.json").read_text(encoding="utf-8"))
    source_map = json.loads(fixture_path("source_map.json").read_text(encoding="utf-8"))
    data["visual_cards"][0]["page"] = 1
    data["visual_cards"][0]["image_path"] = f"papers/{bibkey}/page_images/page-021.png"
    source_map["blocks"][-1]["page"] = 1
    source_map["blocks"][-2]["page"] = 1
    _write_draft_bundle(tmp_path, "unit", bibkey, data=data, source_map=source_map)

    result = finalize_read_batch(tmp_path, "unit")
    repaired = json.loads((tmp_path / "papers" / bibkey / "deep_read.json").read_text(encoding="utf-8"))
    repaired_source = json.loads((tmp_path / "papers" / bibkey / "source_map.json").read_text(encoding="utf-8"))
    source_pages = {block["id"]: block["page"] for block in repaired_source["blocks"] if block["id"] in {"F001", "C001"}}

    assert result["ok"] is True
    assert result["preflight_repairs"] == [{"bibkey": bibkey, "fields": ["visual_cards.page"]}]
    assert repaired["visual_cards"][0]["page"] == 21
    assert source_pages == {"F001": 21, "C001": 21}


def test_read_batch_finalize_commits_current_batch_when_stale_library_has_bad_readings(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    stale_bibkey = "Stale2024Bad"
    parse_pdf(tmp_path, bibkey)
    _write_reading_bundle(tmp_path, bibkey)
    _write_reading_bundle(tmp_path, stale_bibkey)
    stale_data = json.loads((tmp_path / "papers" / stale_bibkey / "deep_read.json").read_text(encoding="utf-8"))
    stale_data["quick_read"][0]["text"] = (
        "This reread uses selected evidence and an evidence block instead of a finished paper-specific interpretation."
    )
    (tmp_path / "papers" / stale_bibkey / "deep_read.json").write_text(json.dumps(stale_data, indent=2), encoding="utf-8")
    prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id="unit")
    source_map = json.loads(fixture_path("source_map.json").read_text())
    source_map["blocks"][0]["notes"] = "Fresh batch draft should commit even while another library paper remains stale."
    _write_draft_bundle(tmp_path, "unit", bibkey, source_map=source_map)

    result = finalize_read_batch(tmp_path, "unit")
    library_result = audit_reading_library(tmp_path)

    assert result["ok"] is True
    assert result["audit_scope"] == "batch"
    assert result["batch_audit"]["target_bibkeys"] == [bibkey]
    assert f"papers/{bibkey}/deep_read.json" in result["changed"]
    assert library_result["ok"] is False
    assert stale_bibkey in library_result["failed_papers"]


def test_read_batch_finalize_rejects_multi_paper_batch_without_draft_worker_records(tmp_path):
    init_topic(tmp_path)
    for bibkey in ["Alpha2024A", "Beta2024B"]:
        paper_dir = tmp_path / "papers" / bibkey
        paper_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture_path("example.pdf"), paper_dir / "paper.pdf")
        parse_pdf(tmp_path, bibkey)
        _write_reading_bundle(tmp_path, bibkey)
    prepare_read_batch(tmp_path, bibkeys=["Alpha2024A", "Beta2024B"], force_reread=True, run_id="unit")
    for bibkey in ["Alpha2024A", "Beta2024B"]:
        source_map = json.loads(fixture_path("source_map.json").read_text())
        source_map["blocks"][0]["notes"] = f"{bibkey} fresh draft with no harvest finding should be rejected."
        _write_draft_bundle(tmp_path, "unit", bibkey, source_map=source_map)

    result = finalize_read_batch(tmp_path, "unit")

    assert result["ok"] is False
    assert result["error"] == "missing or invalid read-batch draft-worker records"
    assert "Alpha2024A: missing findings/Alpha2024A/draft_worker.json" in result["errors"]


def test_read_batch_finalize_rejects_draft_worker_that_uses_old_reading_artifacts(tmp_path):
    init_topic(tmp_path)
    for bibkey in ["Alpha2024A", "Beta2024B"]:
        paper_dir = tmp_path / "papers" / bibkey
        paper_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture_path("example.pdf"), paper_dir / "paper.pdf")
        parse_pdf(tmp_path, bibkey)
        _write_reading_bundle(tmp_path, bibkey)
    prepare_read_batch(tmp_path, bibkeys=["Alpha2024A", "Beta2024B"], force_reread=True, run_id="unit")
    for bibkey in ["Alpha2024A", "Beta2024B"]:
        _write_draft_bundle(tmp_path, "unit", bibkey)
        _write_draft_worker_record(tmp_path, "unit", bibkey)
    bad_path = tmp_path / ".tmp" / "read_batch" / "unit" / "findings" / "Alpha2024A" / "draft_worker.json"
    bad = json.loads(bad_path.read_text(encoding="utf-8"))
    bad["allowed_inputs"].append("papers/Alpha2024A/deep_read.json")
    bad_path.write_text(json.dumps(bad, indent=2), encoding="utf-8")

    result = finalize_read_batch(tmp_path, "unit")

    assert result["ok"] is False
    assert "old reading artifact" in "\n".join(result["errors"])


def test_read_batch_finalize_rejects_template_draft_and_restores_original(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    parse_pdf(tmp_path, bibkey)
    _write_reading_bundle(tmp_path, bibkey)
    original = (tmp_path / "papers" / bibkey / "deep_read.json").read_text(encoding="utf-8")
    prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id="unit")
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["one_sentence_summary"] = (
        "Grounding Generative Policies in Physics is reread as an application contribution with "
        "conclusions tied to selected motivation, method, result, and limitation evidence."
    )
    _write_draft_bundle(tmp_path, "unit", bibkey, data=data)

    result = finalize_read_batch(tmp_path, "unit")

    assert result["ok"] is False
    assert result["restored"] is True
    assert "quality-audit failed" in result["error"] or "validate-report failed" in result["error"]
    assert (tmp_path / "papers" / bibkey / "deep_read.json").read_text(encoding="utf-8") == original


def test_read_batch_finalize_reports_multiple_invalid_batch_drafts(tmp_path):
    init_topic(tmp_path)
    bibkeys = ["Alpha2024A", "Beta2024B"]
    for bibkey in bibkeys:
        paper_dir = tmp_path / "papers" / bibkey
        paper_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture_path("example.pdf"), paper_dir / "paper.pdf")
        parse_pdf(tmp_path, bibkey)
        _write_reading_bundle(tmp_path, bibkey)
    prepare_read_batch(tmp_path, bibkeys=bibkeys, force_reread=True, run_id="unit")
    for bibkey in bibkeys:
        data = json.loads(fixture_path("deep_read_report.json").read_text())
        data["bibkey"] = bibkey
        data["argument_map"]["method_logic"]["text"] = (
            "The validator requirement says this reading bundle should highlight selected evidence, "
            "which leaks the workflow instead of explaining the paper."
        )
        _write_draft_bundle(tmp_path, "unit", bibkey, data=data)
        _write_draft_worker_record(tmp_path, "unit", bibkey)

    result = finalize_read_batch(tmp_path, "unit")

    assert result["ok"] is False
    assert result["restored"] is True
    assert result["error"] == "batch validate-report failed"
    assert sorted(result["details"]["failed_papers"]) == bibkeys
    for bibkey in bibkeys:
        errors = "\n".join(result["details"]["failed_papers"][bibkey]["errors"])
        assert "template-like reading prose" in errors


def test_read_batch_finalize_rejects_force_reread_noop_draft(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    parse_pdf(tmp_path, bibkey)
    _write_reading_bundle(tmp_path, bibkey)
    prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id="unit")
    draft_dir = tmp_path / ".tmp" / "read_batch" / "unit" / "drafts" / bibkey
    for name in ["source_map.json", "note_plan.json", "deep_read.json"]:
        shutil.copy2(tmp_path / "papers" / bibkey / name, draft_dir / name)

    result = finalize_read_batch(tmp_path, "unit")

    assert result["ok"] is False
    assert result["error"] == "force-reread draft is identical to existing artifacts"
    assert result["details"]["no_op_bibkeys"] == [bibkey]


def test_read_batch_finalize_restores_originals_after_unexpected_copy_error(tmp_path, monkeypatch):
    bibkey = _promoted_topic(tmp_path)
    parse_pdf(tmp_path, bibkey)
    _write_reading_bundle(tmp_path, bibkey)
    original = {
        name: (tmp_path / "papers" / bibkey / name).read_text(encoding="utf-8")
        for name in ["source_map.json", "note_plan.json", "deep_read.json"]
    }
    prepare_read_batch(tmp_path, bibkeys=[bibkey], force_reread=True, run_id="unit")
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["quick_read"][0]["text"] = "Use this fixture to verify schema, source refs, Markdown, HTML rendering, and batch rollback behavior."
    _write_draft_bundle(tmp_path, "unit", bibkey, data=data)
    real_copy2 = shutil.copy2
    calls = {"count": 0}

    def flaky_copy2(src, dst, *args, **kwargs):
        if ".tmp/read_batch/unit/drafts" in str(src) and str(dst).endswith("note_plan.json"):
            raise OSError("simulated copy failure")
        calls["count"] += 1
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr("paper_engine.read_batch.shutil.copy2", flaky_copy2)

    result = finalize_read_batch(tmp_path, "unit")

    assert result["ok"] is False
    assert result["restored"] is True
    assert "simulated copy failure" in result["error"]
    for name, text in original.items():
        assert (tmp_path / "papers" / bibkey / name).read_text(encoding="utf-8") == text


def test_read_batch_finalize_rejects_repeated_cards_across_targets(tmp_path):
    init_topic(tmp_path)
    for bibkey in ["Alpha2024A", "Beta2024B"]:
        paper_dir = tmp_path / "papers" / bibkey
        paper_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture_path("example.pdf"), paper_dir / "paper.pdf")
        parse_pdf(tmp_path, bibkey)
        _write_reading_bundle(tmp_path, bibkey)
    prepare_read_batch(tmp_path, bibkeys=["Alpha2024A", "Beta2024B"], force_reread=True, run_id="unit")
    repeated = (
        "The method links shooting intervals through boundary matching and uses the resulting nonlinear "
        "equations to guide the solver under the stated control assumptions."
    )
    for bibkey in ["Alpha2024A", "Beta2024B"]:
        data = json.loads(fixture_path("deep_read_report.json").read_text())
        data["bibkey"] = bibkey
        data["one_sentence_summary"] = repeated
        _write_draft_bundle(tmp_path, "unit", bibkey, data=data)
        _write_draft_worker_record(tmp_path, "unit", bibkey)

    result = finalize_read_batch(tmp_path, "unit")

    assert result["ok"] is False
    assert result["restored"] is True
    assert result["error"] == "batch audit failed"
    assert "repeated reader-facing text blocks" in "\n".join(result["details"]["errors"])


def test_deep_read_contract_rejects_exposed_generic_batch_templates(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["quick_read"][0]["text"] = "This reread relies on selected evidence and an evidence block instead of a reader-facing interpretation."
    data["method_understanding"]["algorithm_steps"][0]["action"] = "The validator requirement says this reading bundle should highlight the selected boundary evidence."
    data["translations"]["zh"]["quick_read"][0] = "这个证据块来自所选证据，读者应结合证据。"
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "template-like reading prose: quick_read[0].text" in errors
    assert "template-like reading prose: method_understanding.algorithm_steps[0].action" in errors
    assert "lazy zh translation: translations.zh.quick_read[0]" in errors


def test_deep_read_contract_rejects_test_time_guidance_batch_templates(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["argument_map"]["method_logic"]["text"] = (
        "This reread uses selected evidence and an evidence block instead of explaining the test-time guidance mechanism."
    )
    data["method_understanding"]["implementation_details"][0]["text"] = (
        "The validator requirement says the reading bundle should highlight the selected boundary evidence."
    )
    data["translations"]["zh"]["one_sentence_summary"] = (
        "中文解读应突出推理时引导，而不是泛泛说生成模型。"
    )
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert result["ok"] is False
    assert "template-like reading prose: argument_map.method_logic.text" in errors
    assert "template-like reading prose: method_understanding.implementation_details[0].text" in errors
    assert "lazy zh translation: translations.zh.one_sentence_summary" in errors


def test_deep_read_quality_allows_concrete_method_block_language(tmp_path):
    bibkey = _promoted_topic(tmp_path)
    data = json.loads(fixture_path("deep_read_report.json").read_text())
    data["central_claims"][0]["evidence_summary"] = (
        "The abstract says ReSample solves general inverse problems with pre-trained LDMs, the contribution "
        "bullets explicitly include both linear and nonlinear cases, and the method block gives the concrete "
        "test-time operation: at selected DDIM reverse times, initialize from zhat_0(z_{t+1}) and solve a "
        "decoded measurement-matching objective, min_z ||y - A(D(z))||^2, to obtain zhat_0(y) before resampling. "
        "This ties the claim to the LDM decoder-composed operator A(D(.)), not to a generic guidance rule."
    )
    data["translations"]["zh"]["central_claims"][0]["evidence_summary"] = (
        "摘要说明 ReSample 面向预训练 LDM 的一般逆问题，贡献条目同时覆盖线性和非线性情形；方法部分给出具体测试时操作："
        "在选定 DDIM 反向时刻，从 zhat_0(z_{t+1}) 初始化并求解解码后的测量匹配目标 min_z ||y - A(D(z))||^2，"
        "得到 zhat_0(y) 后再重采样，因此该证据指向 LDM 解码器复合算子 A(D(.))。"
    )
    _write_reading_bundle(tmp_path, bibkey, data=data)

    result = validate_deep_read_report(tmp_path, bibkey)
    errors = "\n".join(result["errors"])

    assert "template-like reading prose: central_claims[0].evidence_summary" not in errors
