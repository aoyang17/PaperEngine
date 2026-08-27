from __future__ import annotations

from pathlib import Path

from paper_engine.prompt_contracts import (
    build_bootstrap_init_prompt,
    build_operation_prompt,
    build_worker_prompt,
    chat_task,
    collect_candidates_task,
    read_paper_task,
    session_action_task,
)


def test_operation_prompt_is_serverlet_first_and_reads_bounded_context(tmp_path):
    prompt = build_operation_prompt(Path("/project/paper-engine"), tmp_path, "Collect papers.")

    assert "serverlet-first product" in prompt
    assert "The browser UI is the user interface" in prompt
    assert "Use these files as the only project/topic context sources when the task needs them" in prompt
    assert "First read these small files" not in prompt
    assert "/project/paper-engine/README.md" in prompt
    assert "/project/paper-engine/AGENTS.md" in prompt
    assert str(tmp_path / "AGENTS.md") in prompt
    assert str(tmp_path / "policy.yml") in prompt
    assert str(tmp_path / "topic.yml") in prompt
    assert str(tmp_path / "preferences.yml") in prompt
    assert "Do not inspect sibling topic folders" in prompt
    assert "Do not use existing topics as templates" in prompt
    assert "Do not modify project source code" in prompt
    assert "Do not run arbitrary nested Codex/Claude/LLM CLI processes" in prompt
    assert "Do not request manual command approval" in prompt
    assert "`sudo`, `chmod`, `chown`, `rm -rf`, `git reset`, or `git checkout`" in prompt
    assert "paper_engine read <bibkey> --vision-formulas" in prompt
    assert "paper_engine read-many ..." in prompt
    assert "Read multiple papers, reread all papers, or update library knowledge cards in bulk -> use `paper_engine read-many`" in prompt
    assert "--refresh-section dataset" in prompt
    assert "do not perform a full reread" in prompt
    assert "Do not loop over papers and write final `papers/<bibkey>/deep_read.json` directly" in prompt
    assert "Do not create helper scripts, deterministic draft generators, parsed/index-only bulk writers" in prompt
    assert "main-session schema fillers" in prompt
    assert "run `/project/paper-engine/bin/paper_engine`" in prompt
    assert "paper_engine candidates remove-by-bibkey <bibkey>" in prompt
    assert "must not delete `library.bib`, `papers/<bibkey>/`, PDFs, notes, or reading HTML" in prompt
    assert "If multiple queue items match the same bibkey, stop" in prompt
    assert "paper_engine library update-metadata <bibkey> --metadata <file>" in prompt
    assert "metadata must come from real search/source results" in prompt
    assert "never from model memory or invention" in prompt
    assert "marks the BibTeX entry as unverified" in prompt
    assert "status: completed | blocked | failed" in prompt
    assert "Task:\nCollect papers." in prompt


def test_worker_prompt_uses_same_operation_contract(tmp_path):
    prompt = build_worker_prompt(Path("/project/paper-engine"), tmp_path, "Run health check.")

    assert "serverlet-first product" in prompt
    assert "Run health check." in prompt


def test_bootstrap_init_prompt_is_clean_room_and_does_not_require_topic_files(tmp_path):
    prompt = build_bootstrap_init_prompt(
        Path("/project/paper-engine"),
        tmp_path / "paper_hub",
        title="Test Time Guidance",
        direction="Flow model test-time guidance",
        seed_papers=["Seed Paper"],
    )

    assert "templates/skills/topic_init/SKILL.md" in prompt
    assert '"/project/paper-engine/bin/paper_engine" init --base-dir' in prompt
    assert "Test Time Guidance" in prompt
    assert "Flow model test-time guidance" in prompt
    assert "Seed Paper" in prompt
    assert "Do not inspect sibling topic folders" in prompt
    assert "Do not run `ls" in prompt
    assert "Do not run `find .agents .codex`" in prompt
    assert "topic.yml" not in prompt
    assert "preferences.yml" not in prompt


def test_collect_task_is_bounded_and_cli_driven():
    task = collect_candidates_task(target_new=12, score_threshold=0.2, query="test-time guidance")

    assert "Collect up to 12 new candidate papers" in task
    assert 'paper_engine collect --target-new 12 --score-threshold 0.2 --query "test-time guidance"' in task
    assert "paper_engine candidates scoring-batch --status new --limit 12 --json" in task
    assert "paper_engine candidates apply-scores --scores reports/candidate_scores.jsonl" in task
    assert "candidates remain unscored instead of treating score 0 as a real relevance score" in task
    assert "Do not directly edit candidate files" in task


def test_chat_task_is_bounded_not_shell_bridge():
    task = chat_task("What should I read next?")

    assert "bounded user request" in task
    assert "Do not perform shell commands unless required" in task
    assert "What should I read next?" in task


def test_read_task_uses_controlled_formula_vision_tool():
    task = read_paper_task("Smith2024Paper")

    assert "templates/skills/paper_deep_read/SKILL.md" in task
    assert "project-root schemas" in task
    assert "paper_engine read Smith2024Paper --vision-formulas" in task
    assert "only controlled Codex image-input exception" in task
    assert "do not start any other nested" in task
    assert "formula_vision.json" in task
    assert "papers/Smith2024Paper/source_map.json" in task
    assert "papers/Smith2024Paper/note_plan.json" in task
    assert "papers/Smith2024Paper/deep_read.json" in task
    assert "papers/Smith2024Paper/math_index.json" in task
    assert "vision_fallback.needed" in task
    assert "do not invent notation" in task
    assert "vision_fallback.status" in task
    assert "paper_engine read Smith2024Paper --validate-report" in task
    assert "paper_engine read Smith2024Paper --rebuild-note" in task
    assert "paper_engine read Smith2024Paper --quality-audit" in task
    assert task.index("paper_engine read Smith2024Paper --validate-report") < task.index("paper_engine read Smith2024Paper --parse-only")
    assert task.rindex("paper_engine read Smith2024Paper --rebuild-note") < task.rindex("paper_engine read Smith2024Paper --quality-audit")
    assert "If validation, rebuild, and quality audit all pass, skip `Smith2024Paper`" in task
    assert "explicitly asked to re-read, reinterpret, refresh, or fix stale reading knowledge" in task
    assert "missing `math_index.json`" in task
    assert "do not run `paper_engine read Smith2024Paper --parse-only`" in task
    assert "paper_engine html build" not in task
    assert "topic-local copied skill is older" not in task
    assert "Do not load, compare, or discuss topic-local copies" in task
    assert "Keep visible progress sparse" in task


def test_read_task_explicitly_requires_deep_read_workflow_and_availability_search():
    task = read_paper_task("Smith2024Paper")

    assert "evidence-harvest -> interpretation-draft -> schema-write -> self-review gate" in task
    assert "code, data, and model availability" in task
    assert "do not rely only on the paper text" in task
    assert "limited external availability search" in task
    assert "E### external source blocks" in task
    assert "`source_kind: \"external\"`" in task
    assert "quality-audit wording" in task
    assert "reread/selected evidence/evidence block" in task
    assert "validation and quality-audit errors are repair instructions, not content to summarize" in task


def test_session_action_prompts_share_boundaries_and_output_contract():
    actions = [
        ("search_30", {"target_new": 30}),
        ("score_queue", {"limit": 30}),
        ("work_status", {}),
        ("refresh", {}),
        ("candidate_download_selected", {"candidate_ids": ["CAND-001"]}),
        ("candidate_mark_relevant", {"candidate_id": "CAND-001"}),
        ("candidate_dismissed", {"candidate_id": "CAND-001"}),
        ("candidate_mark_irrelevant", {"candidate_id": "CAND-001"}),
        ("library_read_selected", {"bibkeys": ["Smith2024Paper"]}),
        ("library_check_bib", {}),
        ("library_refresh_html", {}),
        ("chat", {"message": "What next?"}),
    ]

    for action, payload in actions:
        task = session_action_task(action, payload)
        assert "Do not inspect sibling topic folders" in task
        assert "Use paper_engine CLI commands for state changes" in task
        assert "status/changed/skipped/failed/verification/next_step" in task


def test_session_action_prompts_include_exact_candidate_ids_and_bibkeys():
    download = session_action_task("candidate_download_selected", {"candidate_ids": ["CAND-001", "CAND-002"]})
    read = session_action_task("library_read_selected", {"bibkeys": ["Smith2024Paper", "Doe2025Method"]})

    assert "CAND-001" in download
    assert "CAND-002" in download
    assert "<candidate_id>" not in download
    assert "Smith2024Paper" in read
    assert "Doe2025Method" in read
    assert "paper_engine read-many --bibkey Smith2024Paper --bibkey Doe2025Method --force-reread --json" in read
    assert "one reader session and one independent reviewer session" in read
    assert "project default of 5 paper jobs" in read
    assert "`--max-parallel N` above 5 only when the user explicitly asks" in read
    assert "hard cap is 20 paper jobs" in read
    assert "up to 2N Codex sessions" in read
    assert "at most 3 cycles by default" in read
    assert "`--max-cycles N` up to 7" in read
    assert "`--accept-last-on-max-cycles` unless the user explicitly asks" in read
    assert "selected reduce-audit" in read
    assert "Do not call `read-batch`, `read-batch --draft-workers`, or `read-batch --finalize`" in read
    assert "must not read old `deep_read.json`" in read
    assert "deterministic draft writer" in read
    assert "parsed/index-only schema filler" in read


def test_library_read_action_uses_project_root_skill_without_version_chatter():
    task = session_action_task("library_read_selected", {"bibkeys": ["Smith2024Paper"]})

    assert "templates/skills/paper_deep_read/SKILL.md" in task
    assert "project-root schemas" in task
    assert "topic-local copied skill is older" not in task
    assert "Do not load, compare, or discuss topic-local copies" in task
    assert "sandbox retry" in task


def test_dismissed_action_avoids_positive_or_negative_preference_writeback():
    task = session_action_task("candidate_dismissed", {"candidate_id": "CAND-001"})

    assert "Dismiss candidate CAND-001" in task
    assert "without recording positive feedback" in task
    assert "without recording negative feedback" in task
    assert "paper_engine candidates dismiss CAND-001" in task


def test_unknown_session_action_is_bounded_chat_request():
    task = session_action_task("custom_action", {"note": "inspect status only"})

    assert "custom_action" in task
    assert "inspect status only" in task
    assert "Do not inspect sibling topic folders" in task
    assert "Use paper_engine CLI commands for state changes" in task
