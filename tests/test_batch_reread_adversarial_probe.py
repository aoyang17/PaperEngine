from __future__ import annotations

from scripts.run_batch_reread_adversarial_probe import run_probe


def test_batch_reread_adversarial_probe_passes():
    result = run_probe()

    assert result["ok"] is True
    assert {item["name"] for item in result["checks"]} == {
        "template_draft_rejected",
        "oversized_batch_rejected",
        "staging_helper_rejected",
        "generator_workflow_leakage_rejected",
        "repeated_library_cards_rejected",
        "missing_parallel_draft_worker_blocks_finalize",
        "dirty_library_chunk_commit_allowed",
        "missing_draft_blocks_finalize",
    }
