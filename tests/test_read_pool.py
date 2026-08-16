from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from battery_lit import cli
from battery_lit.read_pool import (
    DATASET_PATCH_NAME,
    DEFAULT_READ_POOL_PARALLEL,
    MAX_READ_POOL_PARALLEL,
    MAX_READER_REVIEW_CYCLES,
    READ_POOL_ARTIFACTS,
    READ_POOL_READER_RECORD,
    READ_POOL_REVIEW_RECORD,
    READ_POOL_SCHEMA_VERSION,
    _file_sha256,
    _finalize_dataset_section,
    _validate_dataset_patch,
    run_read_pool,
)
from battery_lit.topic import init_topic


class _FakePoolAgent:
    def __init__(self, role: str, bibkey: str, shared: dict[str, object]) -> None:
        self.role = role
        self.bibkey = bibkey
        self.shared = shared
        self.topic_root: Path | None = None
        self.thread_id = f"{role}-{bibkey}"
        self.messages: list[str] = []
        self.closed = False

    def ensure_session(self, topic_root: Path, model: str | None, effort: str | None) -> dict[str, object]:
        self.topic_root = Path(topic_root)
        return {"ok": True, "thread_id": self.thread_id, "model": model, "effort": effort}

    def send_message_until_outputs(
        self,
        message: str,
        required_outputs: list[Path],
        *,
        stable_seconds: float = 5.0,
        timeout_seconds: float | None = None,
        require_output_updates: bool = False,
    ) -> dict[str, object]:
        assert self.topic_root is not None
        self.messages.append(message)
        if self.role == "reader":
            self._track_active_reader()
            self._write_reader_outputs(required_outputs)
        else:
            self._write_review_outputs(required_outputs)
        return {
            "ok": True,
            "status": "idle",
            "outputs_ready": True,
            "thread_id": self.thread_id,
            "require_output_updates": require_output_updates,
        }

    def state(self) -> dict[str, object]:
        return {"thread_id": self.thread_id, "status": "idle"}

    def close(self) -> None:
        self.closed = True

    def _track_active_reader(self) -> None:
        condition = self.shared.get("condition")
        if not isinstance(condition, threading.Condition):
            return
        with condition:
            self.shared["active"] = int(self.shared.get("active") or 0) + 1
            self.shared["max_active"] = max(int(self.shared.get("max_active") or 0), int(self.shared["active"]))
            condition.notify_all()
            deadline = time.monotonic() + 1.0
            expected = int(self.shared.get("barrier_expected") or 1)
            while int(self.shared.get("max_active") or 0) < expected and time.monotonic() < deadline:
                condition.wait(timeout=0.02)
        time.sleep(float(self.shared.get("reader_delay") or 0.0))
        with condition:
            self.shared["active"] = int(self.shared.get("active") or 0) - 1
            condition.notify_all()

    def _write_reader_outputs(self, required_outputs: list[Path]) -> None:
        assert self.topic_root is not None
        for path in required_outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.name in READ_POOL_ARTIFACTS:
                path.write_text("{}\n", encoding="utf-8")
            elif path.name == DATASET_PATCH_NAME:
                path.write_text(json.dumps(self.shared.get("dataset_patch") or {}), encoding="utf-8")
        record_path = next(path for path in required_outputs if path.name == READ_POOL_READER_RECORD)
        artifact_paths = [
            path for path in required_outputs if path.name in READ_POOL_ARTIFACTS or path.name == DATASET_PATCH_NAME
        ]
        record = {
            "schema_version": READ_POOL_SCHEMA_VERSION,
            "role": "paper_read_reader",
            "run_id": _line(self.messages[-1], "Run id: "),
            "bibkey": self.bibkey,
            "cycle": int(_line(self.messages[-1], "Cycle: ")),
            "thread_role": "reader",
            "forbidden_inputs_checked": True,
            "writes_final_artifacts": False,
            "draft_artifacts_written": [str(path.relative_to(self.topic_root)) for path in artifact_paths],
            "allowed_inputs": [f"papers/{self.bibkey}/metadata.yml", f"papers/{self.bibkey}/paper_index.json"],
            "notes": [],
        }
        record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    def _write_review_outputs(self, required_outputs: list[Path]) -> None:
        review_path = next(path for path in required_outputs if path.name == READ_POOL_REVIEW_RECORD)
        cycle = int(_line(self.messages[-1], "Cycle: "))
        review_plan = self.shared.get("review_plan")
        verdict = "pass"
        if isinstance(review_plan, dict):
            verdict = str(review_plan.get((self.bibkey, cycle), "pass"))
        issues = []
        if verdict == "revise":
            issues = [
                {
                    "field_path": "quick_read[0].text",
                    "severity": "major",
                    "problem": "needs paper-specific mechanism",
                    "evidence_ref": "S001",
                    "reader_instruction": f"Revise {self.bibkey} with a concrete method anchor.",
                }
            ]
        record = {
            "schema_version": READ_POOL_SCHEMA_VERSION,
            "role": "paper_read_reviewer",
            "run_id": _line(self.messages[-1], "Run id: "),
            "bibkey": self.bibkey,
            "cycle": cycle,
            "thread_role": "reviewer",
            "verdict": verdict,
            "checks": {
                "paper_specific": verdict == "pass",
                "source_grounded": verdict == "pass",
                "zh_complete": verdict == "pass",
                "visual_consistent": verdict == "pass",
                "no_template_reuse": verdict == "pass",
                "no_prompt_leak": verdict == "pass",
            },
            "issues": issues,
        }
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(json.dumps(record, indent=2), encoding="utf-8")


def _line(text: str, prefix: str) -> str:
    return next(line[len(prefix) :].strip() for line in text.splitlines() if line.startswith(prefix))


def _factory(shared: dict[str, object]):
    def build(role: str, bibkey: str) -> _FakePoolAgent:
        agent = _FakePoolAgent(role, bibkey, shared)
        agents = shared.setdefault("agents", {})
        assert isinstance(agents, dict)
        agents[(role, bibkey)] = agent
        return agent

    return build


def _patch_gates(monkeypatch, finalize=None) -> None:
    monkeypatch.setattr("battery_lit.read_pool._ensure_parse", lambda root, bibkey, force_reread: {"ok": True})
    monkeypatch.setattr(
        "battery_lit.read_pool._finalize_one",
        finalize
        or (lambda root, run_id, bibkey, draft_dir: {"ok": True, "changed": [f"papers/{bibkey}/deep_read.json"], "verification": []}),
    )
    monkeypatch.setattr("battery_lit.read_pool.audit_reading_library", lambda root, bibkeys=None: {"ok": True, "audit_scope": "selected"})
    monkeypatch.setattr("battery_lit.read_pool.build_html", lambda root: {"ok": True})


def test_read_pool_uses_independent_reader_and_reviewer_sessions(tmp_path, monkeypatch):
    init_topic(tmp_path, "Pool Topic", "reader reviewer orchestration")
    _patch_gates(monkeypatch)
    shared: dict[str, object] = {}

    result = run_read_pool(
        tmp_path,
        bibkeys=["Alpha2024A", "Beta2024B"],
        force_reread=True,
        run_id="unit",
        max_parallel=2,
        session_factory=_factory(shared),
    )

    assert result["ok"] is True
    assert result["max_parallel"] == 2
    assert [item["bibkey"] for item in result["results"]] == ["Alpha2024A", "Beta2024B"]
    agents = shared["agents"]
    assert agents[("reader", "Alpha2024A")].thread_id == "reader-Alpha2024A"
    assert agents[("reviewer", "Alpha2024A")].thread_id == "reviewer-Alpha2024A"
    assert agents[("reader", "Alpha2024A")].thread_id != agents[("reviewer", "Alpha2024A")].thread_id
    manifest = json.loads((tmp_path / ".tmp" / "read_pool" / "unit" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["batch_mode"] is False
    assert manifest["reader_reviewer_sessions"] is True
    assert manifest["requested_max_parallel"] == 2
    assert manifest["max_parallel_cap"] == MAX_READ_POOL_PARALLEL
    assert manifest["codex_session_budget"] == 4
    assert manifest["requested_max_cycles"] == 3
    assert manifest["max_cycles"] == 3


def test_read_pool_reuses_same_reader_after_reviewer_feedback(tmp_path, monkeypatch):
    init_topic(tmp_path, "Feedback Topic", "reuse reader context")
    _patch_gates(monkeypatch)
    shared: dict[str, object] = {"review_plan": {("Alpha2024A", 1): "revise", ("Alpha2024A", 2): "pass"}}

    result = run_read_pool(
        tmp_path,
        bibkeys=["Alpha2024A"],
        force_reread=True,
        run_id="feedback",
        max_parallel=1,
        session_factory=_factory(shared),
    )

    reader = shared["agents"][("reader", "Alpha2024A")]
    assert result["ok"] is True
    assert len(reader.messages) == 2
    assert "Revise Alpha2024A with a concrete method anchor" in reader.messages[1]
    assert result["results"][0]["reader_thread_id"] == "reader-Alpha2024A"
    assert len(result["results"][0]["cycles"]) == 2


def test_read_pool_respects_parallel_limit(tmp_path, monkeypatch):
    init_topic(tmp_path, "Parallel Topic", "bounded parallelism")
    _patch_gates(monkeypatch)
    shared: dict[str, object] = {
        "condition": threading.Condition(),
        "active": 0,
        "max_active": 0,
        "barrier_expected": 3,
        "reader_delay": 0.05,
    }

    result = run_read_pool(
        tmp_path,
        bibkeys=[f"Paper{i}2026A" for i in range(5)],
        force_reread=True,
        run_id="parallel",
        max_parallel=3,
        session_factory=_factory(shared),
    )

    assert result["ok"] is True
    assert int(shared["max_active"]) >= 2
    assert int(shared["max_active"]) <= 3
    assert result["max_parallel"] == 3


def test_read_pool_defaults_to_five_parallel_paper_jobs(tmp_path, monkeypatch):
    init_topic(tmp_path, "Default Parallel Topic", "default bounded parallelism")
    _patch_gates(monkeypatch)
    shared: dict[str, object] = {
        "condition": threading.Condition(),
        "active": 0,
        "max_active": 0,
        "barrier_expected": DEFAULT_READ_POOL_PARALLEL,
        "reader_delay": 0.05,
    }

    result = run_read_pool(
        tmp_path,
        bibkeys=[f"Paper{i}2026A" for i in range(6)],
        force_reread=True,
        run_id="default_parallel",
        session_factory=_factory(shared),
    )

    assert result["ok"] is True
    assert result["requested_max_parallel"] is None
    assert result["max_parallel"] == DEFAULT_READ_POOL_PARALLEL == 5
    assert result["max_parallel_cap"] == MAX_READ_POOL_PARALLEL
    assert result["codex_session_budget"] == 10
    assert int(shared["max_active"]) <= DEFAULT_READ_POOL_PARALLEL


def test_read_pool_allows_explicit_parallelism_above_default(tmp_path, monkeypatch):
    init_topic(tmp_path, "High Parallel Topic", "explicit high throughput")
    _patch_gates(monkeypatch)
    shared: dict[str, object] = {
        "condition": threading.Condition(),
        "active": 0,
        "max_active": 0,
        "barrier_expected": 8,
        "reader_delay": 0.05,
    }

    result = run_read_pool(
        tmp_path,
        bibkeys=[f"Paper{i}2026A" for i in range(9)],
        force_reread=True,
        run_id="parallel8",
        max_parallel=8,
        session_factory=_factory(shared),
    )

    assert result["ok"] is True
    assert result["requested_max_parallel"] == 8
    assert result["max_parallel"] == 8
    assert result["codex_session_budget"] == 16
    assert int(shared["max_active"]) >= 6
    assert int(shared["max_active"]) <= 8


def test_read_pool_clamps_parallelism_to_hard_cap(tmp_path, monkeypatch):
    init_topic(tmp_path, "Parallel Cap Topic", "hard cap")
    _patch_gates(monkeypatch)
    shared: dict[str, object] = {}

    result = run_read_pool(
        tmp_path,
        bibkeys=[f"Paper{i}2026A" for i in range(25)],
        force_reread=True,
        run_id="parallel_cap",
        max_parallel=99,
        session_factory=_factory(shared),
    )

    assert result["ok"] is True
    assert result["requested_max_parallel"] == 99
    assert result["max_parallel"] == MAX_READ_POOL_PARALLEL == 20
    assert result["max_parallel_cap"] == 20
    assert result["codex_session_budget"] == 40


def test_read_pool_returns_cli_gate_feedback_to_same_reader(tmp_path, monkeypatch):
    init_topic(tmp_path, "Finalize Feedback Topic", "cli feedback loop")
    calls = {"finalize": 0}

    def finalize(root, run_id, bibkey, draft_dir):
        calls["finalize"] += 1
        if calls["finalize"] == 1:
            return {"ok": False, "errors": ["quick_read[0] is too generic"], "restored": True}
        return {"ok": True, "changed": [f"papers/{bibkey}/deep_read.json"], "verification": ["validate: pass"]}

    _patch_gates(monkeypatch, finalize=finalize)
    shared: dict[str, object] = {}

    result = run_read_pool(
        tmp_path,
        bibkeys=["Alpha2024A"],
        force_reread=True,
        run_id="cli_feedback",
        max_parallel=1,
        session_factory=_factory(shared),
    )

    reader = shared["agents"][("reader", "Alpha2024A")]
    assert result["ok"] is True
    assert calls["finalize"] == 2
    assert len(reader.messages) == 2
    assert "quick_read[0] is too generic" in reader.messages[1]


def test_read_pool_honors_requested_cycles_above_default(tmp_path, monkeypatch):
    init_topic(tmp_path, "Cycle Topic", "allow more reader reviewer cycles")
    _patch_gates(monkeypatch)
    shared: dict[str, object] = {
        "review_plan": {("Alpha2024A", 1): "revise", ("Alpha2024A", 2): "revise", ("Alpha2024A", 3): "revise", ("Alpha2024A", 4): "revise", ("Alpha2024A", 5): "pass"}
    }

    result = run_read_pool(
        tmp_path,
        bibkeys=["Alpha2024A"],
        force_reread=True,
        run_id="cycles5",
        max_parallel=1,
        max_cycles=5,
        session_factory=_factory(shared),
    )

    assert result["ok"] is True
    assert result["requested_max_cycles"] == 5
    assert result["max_cycles"] == 5
    assert len(result["results"][0]["cycles"]) == 5
    manifest = json.loads((tmp_path / ".tmp" / "read_pool" / "cycles5" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["requested_max_cycles"] == 5
    assert manifest["max_cycles"] == 5


def test_read_pool_clamps_cycles_to_hard_cap(tmp_path, monkeypatch):
    init_topic(tmp_path, "Hard Cap Topic", "clamp reader reviewer cycles")
    _patch_gates(monkeypatch)
    shared: dict[str, object] = {"review_plan": {("Alpha2024A", cycle): "revise" for cycle in range(1, 20)}}

    result = run_read_pool(
        tmp_path,
        bibkeys=["Alpha2024A"],
        force_reread=True,
        run_id="clamped",
        max_parallel=1,
        max_cycles=99,
        session_factory=_factory(shared),
    )

    assert result["ok"] is False
    assert result["requested_max_cycles"] == 99
    assert result["max_cycles"] == MAX_READER_REVIEW_CYCLES == 7
    assert len(result["results"][0]["cycles"]) == 7
    assert "max reader-review cycles reached (7)" in result["results"][0]["error"]


def test_read_pool_does_not_accept_max_cycle_last_draft_by_default(tmp_path, monkeypatch):
    init_topic(tmp_path, "Strict Cycle Topic", "do not accept limited drafts by default")
    calls = {"finalize": 0}

    def finalize(root, run_id, bibkey, draft_dir):
        calls["finalize"] += 1
        return {"ok": True, "changed": [f"papers/{bibkey}/deep_read.json"], "verification": []}

    _patch_gates(monkeypatch, finalize=finalize)
    shared: dict[str, object] = {"review_plan": {("Alpha2024A", 1): "revise"}}

    result = run_read_pool(
        tmp_path,
        bibkeys=["Alpha2024A"],
        force_reread=True,
        run_id="strict",
        max_parallel=1,
        max_cycles=1,
        session_factory=_factory(shared),
    )

    assert result["ok"] is False
    assert calls["finalize"] == 0
    assert "max reader-review cycles reached (1)" in result["results"][0]["error"]


def test_read_pool_can_accept_last_draft_with_limitations_when_explicit(tmp_path, monkeypatch):
    init_topic(tmp_path, "Limited Accept Topic", "explicitly accept limited last draft")
    seen_quality = {}

    def finalize(root, run_id, bibkey, draft_dir):
        data = json.loads((draft_dir / "deep_read.json").read_text(encoding="utf-8"))
        seen_quality.update(data.get("reading_quality") or {})
        return {"ok": True, "changed": [f"papers/{bibkey}/deep_read.json"], "verification": ["validate: pass"]}

    _patch_gates(monkeypatch, finalize=finalize)
    shared: dict[str, object] = {"review_plan": {("Alpha2024A", 1): "revise"}}

    result = run_read_pool(
        tmp_path,
        bibkeys=["Alpha2024A"],
        force_reread=True,
        run_id="limited",
        max_parallel=1,
        max_cycles=1,
        accept_last_on_max_cycles=True,
        session_factory=_factory(shared),
    )

    assert result["ok"] is True
    assert result["accept_last_on_max_cycles"] is True
    assert result["results"][0]["accepted_with_limitations"] is True
    assert seen_quality["status"] == "accepted_with_limitations"
    assert seen_quality["acceptance_reason"] == "max_cycles_reached"
    assert seen_quality["cycles_used"] == 1
    assert seen_quality["open_issues"]


def test_cli_read_many_invokes_read_pool(tmp_path, monkeypatch, capsys):
    init_topic(tmp_path, "CLI Pool Topic", "read many cli")
    called = {}

    def fake_run(root, **kwargs):
        kwargs["root"] = root
        called.update(kwargs)
        progress = kwargs.get("progress")
        if progress:
            progress("read-many: test heartbeat")
        return {"ok": True, "run_id": kwargs["run_id"], "results": []}

    monkeypatch.setattr("battery_lit.read_pool.run_read_pool", fake_run)

    result = cli.main(
        [
            "read-many",
            "--root",
            str(tmp_path),
            "--bibkey",
            "Alpha2024A",
            "--bibkey",
            "Beta2024B",
            "--force-reread",
            "--run-id",
            "cli_pool",
            "--max-parallel",
            "3",
            "--max-cycles",
            "2",
            "--accept-last-on-max-cycles",
            "--model",
            "gpt-5.5",
            "--effort",
            "medium",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert called["root"] == str(tmp_path)
    assert called["bibkeys"] == ["Alpha2024A", "Beta2024B"]
    assert called["force_reread"] is True
    assert called["run_id"] == "cli_pool"
    assert called["max_parallel"] == 3
    assert called["max_cycles"] == 2
    assert called["accept_last_on_max_cycles"] is True
    assert called["model"] == "gpt-5.5"
    assert called["effort"] == "medium"
    assert "read-many: test heartbeat" in captured.err


def test_dataset_refresh_reuses_read_pool_and_skips_parser(tmp_path, monkeypatch):
    init_topic(tmp_path, "Dataset Refresh", "refresh only dataset evidence")
    calls = {"parse_force": None, "finalize": 0}
    context = {
        "ok": True,
        "bibkey": "Alpha2024A",
        "base_report_sha256": "report-hash",
        "base_source_map_sha256": "source-hash",
        "source_id_starts": {"S": "S010", "C": "C010", "F": "F010", "T": "T010", "M": "M010", "E": "E010"},
        "style_context": {"title": "Dataset Paper"},
    }

    def existing_parse(root, bibkey):
        calls["parse_force"] = False
        return {"ok": True}

    def finalize(root, run_id, bibkey, draft_dir, seen_context):
        calls["finalize"] += 1
        assert seen_context == context
        return {"ok": True, "changed": [f"papers/{bibkey}/deep_read.json"], "verification": []}

    monkeypatch.setattr("battery_lit.read_pool._existing_dataset_parse", existing_parse)
    monkeypatch.setattr("battery_lit.read_pool._prepare_dataset_context", lambda root, bibkey, job_dir: context)
    monkeypatch.setattr("battery_lit.read_pool._finalize_dataset_section", finalize)
    monkeypatch.setattr("battery_lit.read_pool.audit_reading_library", lambda root, bibkeys=None: {"ok": True})
    monkeypatch.setattr("battery_lit.read_pool.build_html", lambda root: {"ok": True})
    shared = {"dataset_patch": {"schema_version": READ_POOL_SCHEMA_VERSION}}

    result = run_read_pool(
        tmp_path,
        bibkeys=["Alpha2024A"],
        refresh_section="dataset",
        run_id="dataset_only",
        max_parallel=1,
        session_factory=_factory(shared),
    )

    assert result["ok"] is True
    assert result["refresh_section"] == "dataset"
    assert calls == {"parse_force": False, "finalize": 1}
    reader = shared["agents"][("reader", "Alpha2024A")]
    reviewer = shared["agents"][("reviewer", "Alpha2024A")]
    assert "do not run PDF parsing" in reader.messages[0]
    assert "Do not read the old dataset_benchmark_understanding" in reader.messages[0]
    assert '"visual_cards"' not in reader.messages[0]
    assert '"availability_data"' not in reader.messages[0]
    assert "Leave availability and visual cards outside this module unchanged" in reader.messages[0]
    assert '"forbidden_inputs_checked": true' in reader.messages[0]
    assert "dataset-module patch" in reviewer.messages[0]
    assert 'Use only "pass", "revise", or "block" for verdict' in reviewer.messages[0]


def test_dataset_refresh_reviewer_rejection_keeps_finalizer_closed(tmp_path, monkeypatch):
    init_topic(tmp_path, "Dataset Review", "reject weak dataset patch")
    monkeypatch.setattr("battery_lit.read_pool._existing_dataset_parse", lambda root, bibkey: {"ok": True})
    monkeypatch.setattr(
        "battery_lit.read_pool._prepare_dataset_context",
        lambda root, bibkey, job_dir: {
            "ok": True,
            "bibkey": bibkey,
            "base_report_sha256": "report-hash",
            "base_source_map_sha256": "source-hash",
            "source_id_starts": {},
            "style_context": {},
        },
    )
    finalized = {"called": False}
    monkeypatch.setattr(
        "battery_lit.read_pool._finalize_dataset_section",
        lambda *args, **kwargs: finalized.update(called=True) or {"ok": True},
    )
    shared = {
        "dataset_patch": {"schema_version": READ_POOL_SCHEMA_VERSION},
        "review_plan": {("Alpha2024A", 1): "revise"},
    }

    result = run_read_pool(
        tmp_path,
        bibkeys=["Alpha2024A"],
        refresh_section="dataset",
        run_id="dataset_rejected",
        max_parallel=1,
        max_cycles=1,
        session_factory=_factory(shared),
    )

    assert result["ok"] is False
    assert finalized["called"] is False


def test_dataset_finalizer_changes_only_dataset_owned_content(tmp_path, monkeypatch):
    root = tmp_path
    bibkey = "Dataset2026A"
    paper_dir = root / "papers" / bibkey
    draft_dir = root / ".tmp" / "read_pool" / "section_merge" / bibkey / "draft"
    paper_dir.mkdir(parents=True)
    draft_dir.mkdir(parents=True)
    report = {
        "one_sentence_summary": "Stable summary.",
        "dataset_benchmark_understanding": {"format": "structured_v2", "key_numbers": [], "construction_steps": [], "biases_or_limits": []},
        "evaluation": {"main_results": [{"text": "Keep me", "source_refs": ["S002"]}]},
        "visual_cards": [
            {"label": "old dataset", "placement_section": "dataset_benchmark_understanding", "source_refs": ["S001"]},
            {"label": "result", "placement_section": "evaluation", "source_refs": ["S002"]},
        ],
        "availability": {"data": {"status": "old", "evidence": "old", "source_refs": ["S001"]}},
        "translations": {
            "zh": {
                "type_sections": {"dataset_benchmark_understanding": {"old": True}},
                "visual_cards": [{"label": "旧数据"}, {"label": "结果"}],
                "availability": {"data": {"evidence": "旧"}},
            }
        },
    }
    source_map = {
        "blocks": [
            {"id": "S001", "source_text": "old dataset evidence"},
            {"id": "S002", "source_text": "preserved result evidence"},
        ]
    }
    (paper_dir / "deep_read.json").write_text(json.dumps(report), encoding="utf-8")
    (paper_dir / "source_map.json").write_text(json.dumps(source_map), encoding="utf-8")
    (paper_dir / "note_plan.json").write_text("{}\n", encoding="utf-8")
    context = {
        "bibkey": bibkey,
        "base_report_sha256": _file_sha256(paper_dir / "deep_read.json"),
        "base_source_map_sha256": _file_sha256(paper_dir / "source_map.json"),
    }
    patch = {
        "schema_version": READ_POOL_SCHEMA_VERSION,
        "bibkey": bibkey,
        "base_report_sha256": context["base_report_sha256"],
        "base_source_map_sha256": context["base_source_map_sha256"],
        "dataset_benchmark_understanding": {
            "format": "structured_v2",
            "key_numbers": [{"label": "Cases", "value": "10", "context": "New", "source_refs": ["S003"]}],
            "construction_steps": [{"stage": "Build", "action": "Generate", "output": "Cases", "source_refs": ["S003"]}],
            "biases_or_limits": [{"text": "Scoped corpus", "source_refs": ["S003"]}],
        },
        "translation_zh": {
            "dataset_benchmark_understanding": {
                "key_numbers": [{"label": "算例", "context": "新"}],
                "construction_steps": [{"stage": "构建", "action": "生成", "output": "算例"}],
                "biases_or_limits": ["语料范围有限"],
            }
        },
        "source_blocks": [{"id": "S003", "source_text": "new dataset evidence"}],
    }
    (draft_dir / DATASET_PATCH_NAME).write_text(json.dumps(patch), encoding="utf-8")
    monkeypatch.setattr("battery_lit.read_pool.validate_deep_read_report", lambda root, bibkey: {"ok": True})
    monkeypatch.setattr("battery_lit.read_pool.rebuild_note", lambda root, bibkey: {"ok": True})
    monkeypatch.setattr("battery_lit.read_pool.audit_deep_read_quality", lambda root, bibkey: {"ok": True})

    result = _finalize_dataset_section(root, "section_merge", bibkey, draft_dir, context)

    merged = json.loads((paper_dir / "deep_read.json").read_text(encoding="utf-8"))
    merged_map = json.loads((paper_dir / "source_map.json").read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert merged["one_sentence_summary"] == "Stable summary."
    assert merged["evaluation"] == report["evaluation"]
    assert merged["dataset_benchmark_understanding"]["key_numbers"][0]["value"] == "10"
    assert merged["visual_cards"] == report["visual_cards"]
    assert merged["translations"]["zh"]["visual_cards"] == report["translations"]["zh"]["visual_cards"]
    assert merged["availability"] == report["availability"]
    assert merged["translations"]["zh"]["availability"] == report["translations"]["zh"]["availability"]
    assert {item["id"] for item in merged_map["blocks"]} == {"S001", "S002", "S003"}


def test_dataset_patch_rejects_invented_source_block_keys():
    context = {"bibkey": "Dataset2026A", "base_report_sha256": "r", "base_source_map_sha256": "s"}
    patch = {
        "schema_version": READ_POOL_SCHEMA_VERSION,
        "bibkey": "Dataset2026A",
        "base_report_sha256": "r",
        "base_source_map_sha256": "s",
        "dataset_benchmark_understanding": {
            "format": "structured_v2",
            "key_numbers": [{"label": "Cases", "value": "10", "source_refs": ["S003"]}],
            "construction_steps": [],
            "biases_or_limits": [],
        },
        "translation_zh": {"dataset_benchmark_understanding": {}},
        "source_blocks": [{"block_id": "S003", "text": "wrong shape"}],
    }

    errors = _validate_dataset_patch(patch, context)

    assert "source_blocks[0] is missing id" in errors
    assert "dataset section has source refs missing from patch blocks: S003" in errors


def test_cli_read_many_accepts_dataset_refresh(tmp_path, monkeypatch, capsys):
    init_topic(tmp_path, "CLI Dataset", "dataset section refresh")
    called = {}

    def fake_run(root, **kwargs):
        called.update(kwargs)
        return {"ok": True, "run_id": "dataset_cli", "results": []}

    monkeypatch.setattr("battery_lit.read_pool.run_read_pool", fake_run)
    result = cli.main(
        [
            "read-many",
            "--root",
            str(tmp_path),
            "--bibkey",
            "Alpha2024A",
            "--refresh-section",
            "dataset",
            "--json",
        ]
    )

    assert result == 0
    assert called["refresh_section"] == "dataset"
    assert called["force_reread"] is False
    assert json.loads(capsys.readouterr().out)["ok"] is True
