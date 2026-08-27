from __future__ import annotations

import json
from pathlib import Path

from paper_engine.sidecars import (
    READ_DRAFT_WORKER_SCHEMA_VERSION,
    READ_HARVEST_SCHEMA_VERSION,
    SidecarTempWorkspace,
    compare_reading_equivalence,
    merge_read_harvest_findings,
    merge_score_shards,
    split_shards,
    validate_read_draft_worker_record,
    validate_read_harvest_finding,
)


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def _valid_harvest(bibkey: str = "Smith2024Paper") -> dict:
    return {
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
                "claim": "The paper-specific method couples a solver update with a validated boundary constraint.",
                "source_path": f"papers/{bibkey}/paper_index.json",
                "paragraph_ids": ["p:0001"],
                "page": 1,
                "confidence": "high",
            }
        ],
        "critical_facts": {
            "method": [{"id": "solver", "text": "solver update with boundary constraint"}],
            "numeric": [{"id": "speed", "text": "2.1x faster"}],
        },
    }


def _valid_draft_worker(bibkey: str = "Smith2024Paper", run_id: str = "unit") -> dict:
    return {
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
                "claim": "The paper-specific draft worker used the indexed method evidence.",
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


def test_sidecar_temp_workspace_cleans_tmp_files():
    workspace = SidecarTempWorkspace.create(prefix="paper-engine-sidecar-")
    marker = workspace.root / "marker.txt"
    marker.write_text("temporary sidecar artifact", encoding="utf-8")

    report = workspace.cleanup()

    assert report.removed is True
    assert report.kept is False
    assert not workspace.root.exists()


def test_sidecar_temp_workspace_refuses_unsafe_cleanup(tmp_path):
    workspace = SidecarTempWorkspace(root=tmp_path)
    (tmp_path / "marker.txt").write_text("not a sidecar temp dir", encoding="utf-8")

    report = workspace.cleanup()

    assert report.removed is False
    assert report.errors
    assert tmp_path.exists()


def test_split_shards_is_deterministic_round_robin():
    assert split_shards([1, 2, 3, 4, 5], 2) == [[1, 3, 5], [2, 4]]


def test_merge_score_shards_writes_valid_records(tmp_path):
    shard_a = tmp_path / "a.jsonl"
    shard_b = tmp_path / "b.jsonl"
    output = tmp_path / "merged" / "scores.jsonl"
    _write_jsonl(
        shard_a,
        [
            {
                "record_id": "r1",
                "candidate_id": "CAND-001",
                "score": 0.45,
                "content": 0.4,
                "preference": 0.05,
                "credibility": 0.0,
                "score_confidence": "medium",
                "reasons": ["direct match"],
            }
        ],
    )
    _write_jsonl(
        shard_b,
        [
            {
                "record_id": "r2",
                "candidate_id": "CAND-001",
                "score": -0.25,
                "content": -0.25,
                "preference": 0.0,
                "credibility": 0.0,
                "score_confidence": "low",
                "reasons": ["different stable record id"],
            }
        ],
    )

    result = merge_score_shards([shard_a, shard_b], output)

    assert result["ok"] is True
    assert result["records"] == 2
    lines = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [line["record_id"] for line in lines] == ["r1", "r2"]


def test_merge_score_shards_rejects_malformed_and_out_of_range(tmp_path):
    shard = tmp_path / "bad.jsonl"
    output = tmp_path / "scores.jsonl"
    shard.write_text('{"candidate_id":"CAND-001","score":1.4}\nnot-json\n', encoding="utf-8")

    result = merge_score_shards([shard], output)

    assert result["ok"] is False
    assert output.exists() is False
    assert any("score must be" in error for error in result["errors"])
    assert any("invalid JSON" in error for error in result["errors"])


def test_merge_score_shards_rejects_duplicate_identity_without_record_id(tmp_path):
    shard_a = tmp_path / "a.jsonl"
    shard_b = tmp_path / "b.jsonl"
    output = tmp_path / "scores.jsonl"
    _write_jsonl(shard_a, [{"candidate_id": "CAND-001", "score": 0.2}])
    _write_jsonl(shard_b, [{"candidate_id": "CAND-001", "score": 0.3}])

    result = merge_score_shards([shard_a, shard_b], output)

    assert result["ok"] is False
    assert output.exists() is False
    assert any("duplicate score identity" in error for error in result["errors"])


def test_validate_read_harvest_accepts_paper_local_evidence(tmp_path):
    result = validate_read_harvest_finding(_valid_harvest(), topic_root=tmp_path, bibkey="Smith2024Paper")

    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_read_harvest_rejects_old_reading_artifact_input(tmp_path):
    record = _valid_harvest()
    record["allowed_inputs"].append("papers/Smith2024Paper/deep_read.json")

    result = validate_read_harvest_finding(record, topic_root=tmp_path, bibkey="Smith2024Paper")

    assert result["ok"] is False
    assert any("old reading artifact" in error for error in result["errors"])


def test_validate_read_harvest_rejects_sibling_topic_or_wrong_paper_path(tmp_path):
    record = _valid_harvest()
    record["allowed_inputs"] = ["papers/Other2024Paper/paper_index.json"]

    result = validate_read_harvest_finding(record, topic_root=tmp_path, bibkey="Smith2024Paper")

    assert result["ok"] is False
    assert any("papers/Smith2024Paper" in error for error in result["errors"])


def test_validate_read_harvest_rejects_claims_without_source_anchor(tmp_path):
    record = _valid_harvest()
    record["evidence_items"][0] = {
        "kind": "method",
        "claim": "Unsupported method claim.",
        "source_path": "papers/Smith2024Paper/paper_index.json",
        "confidence": "medium",
    }

    result = validate_read_harvest_finding(record, topic_root=tmp_path, bibkey="Smith2024Paper")

    assert result["ok"] is False
    assert any("lacks a source anchor" in error for error in result["errors"])


def test_validate_read_harvest_rejects_final_artifact_writes(tmp_path):
    record = _valid_harvest()
    record["writes_final_artifacts"] = True
    record["final_artifacts_written"] = ["papers/Smith2024Paper/deep_read.json"]

    result = validate_read_harvest_finding(record, topic_root=tmp_path, bibkey="Smith2024Paper")

    assert result["ok"] is False
    errors = "\n".join(result["errors"])
    assert "must not write final" in errors
    assert "must be empty" in errors


def test_validate_read_draft_worker_accepts_staged_bundle_provenance(tmp_path):
    result = validate_read_draft_worker_record(_valid_draft_worker(), topic_root=tmp_path, bibkey="Smith2024Paper", run_id="unit")

    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_read_draft_worker_rejects_old_inputs_and_final_writes(tmp_path):
    record = _valid_draft_worker()
    record["allowed_inputs"].append("papers/Smith2024Paper/reading_result.html")
    record["final_artifacts_written"] = ["papers/Smith2024Paper/deep_read.json"]

    result = validate_read_draft_worker_record(record, topic_root=tmp_path, bibkey="Smith2024Paper", run_id="unit")

    errors = "\n".join(result["errors"])
    assert result["ok"] is False
    assert "old reading artifact" in errors
    assert "final_artifacts_written must be empty" in errors


def test_validate_read_draft_worker_requires_all_three_drafts(tmp_path):
    record = _valid_draft_worker()
    record["draft_artifacts_written"] = record["draft_artifacts_written"][:2]

    result = validate_read_draft_worker_record(record, topic_root=tmp_path, bibkey="Smith2024Paper", run_id="unit")

    assert result["ok"] is False
    assert any("deep_read.json" in error for error in result["errors"])


def test_merge_read_harvest_findings_detects_conflicting_critical_facts():
    left = _valid_harvest()
    right = _valid_harvest()
    right["critical_facts"]["method"][0] = {"id": "solver", "text": "a contradictory solver description"}

    result = merge_read_harvest_findings([left, right])

    assert result["ok"] is False
    assert result["conflicts"]


def test_compare_reading_equivalence_flags_missing_parallel_facts():
    sequential = {
        "method_understanding": {"pipeline": [{"text": "Uses multiple shooting with a Newton correction."}]},
        "numeric_results": [{"metric": "runtime", "value": "2.1x faster"}],
        "availability": {"code": [{"status": "available", "url": "https://github.com/example/project"}]},
    }
    parallel = {
        "method_understanding": {"pipeline": [{"text": "Uses a shooting method."}]},
        "numeric_results": [],
        "availability": {"code": []},
    }

    result = compare_reading_equivalence(sequential, parallel)

    assert result["ok"] is False
    assert {item["group"] for item in result["missing"]} >= {"numeric", "availability"}
