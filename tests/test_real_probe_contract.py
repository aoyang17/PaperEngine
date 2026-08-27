from __future__ import annotations

import importlib.util

from conftest import ROOT


def _load_reading_probe_module():
    path = ROOT / "scripts" / "run_reading_quality_probe.py"
    spec = importlib.util.spec_from_file_location("run_reading_quality_probe", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_probe_script_contract():
    script = ROOT / "scripts" / "run_real_2paper_probe.py"
    text = script.read_text(encoding="utf-8")
    assert "test-time guidance for generative flow model" in text
    assert "real_probe_summary.json" in text
    assert "blockers" in text
    assert "manual_skill_required" in text


def test_real_probe_enriches_before_acquire():
    text = (ROOT / "scripts" / "run_real_2paper_probe.py").read_text(encoding="utf-8")
    assert text.index("enrich_candidate(root, cid") < text.index("result = acquire_pdf(root, cid")


def test_real_probe_does_not_spawn_codex_for_deep_reading():
    text = (ROOT / "scripts" / "run_real_2paper_probe.py").read_text(encoding="utf-8")
    assert "codex exec" not in text
    assert "shutil.which" not in text
    assert "subprocess.run" not in text


def test_deep_read_skill_defines_artifact_contract():
    text = (ROOT / "templates" / "skills" / "paper_deep_read" / "SKILL.md").read_text(encoding="utf-8")
    assert "papers/<bibkey>/parsed.md" in text
    assert "papers/<bibkey>/source_map.json" in text
    assert "papers/<bibkey>/note_plan.json" in text
    assert "papers/<bibkey>/deep_read.json" in text
    assert "schemas/deep_read_report.schema.json" in text
    assert "paper_engine read <bibkey> --vision-formulas" in text
    assert "model-backed exceptions are project CLI commands" in text
    assert "paper_engine read-many" in text
    assert "paper_engine read <bibkey> --validate-report" in text
    assert "paper_engine read <bibkey> --quality-audit" in text
    assert "paper_engine read <bibkey> --rebuild-note" in text


def test_reading_quality_probe_uses_temp_topic_and_quality_audit():
    text = (ROOT / "scripts" / "run_reading_quality_probe.py").read_text(encoding="utf-8")
    assert "reading-quality-probe" in text
    assert "--quality-audit" in text
    assert "--validate-report" in text
    assert "--rebuild-note" in text
    assert "\"rebuild\"" in text
    assert text.index("--rebuild-note") < text.index("--quality-audit")
    assert "audit-readings" in text
    assert "paper_engine read-many --bibkey" in text
    assert ".tmp/read_pool/<run_id>/<bibkey>/draft" in text
    assert "Do not write final `papers/<bibkey>/source_map.json`" in text
    assert "--codex-reread" in text
    assert "--report-dir" in text
    assert "shutil.copytree" in text
    assert "source_topic" in text
    assert "probe_topic" in text
    assert "model_reasoning_effort" in text
    assert "--reasoning-effort" not in text
    assert "--add-dir" in text
    assert "per-paper-timeout" in text
    assert "default=1800" in text
    assert "min-papers" in text
    assert "default=15" in text
    assert "duplicate bibkeys are not allowed" in text
    assert "successful_rereads" in text
    assert "paper_scales" in text
    assert "rendered_pages" in text
    assert "paper_index_page_label_count" in text
    assert "page labels may collapse" in text
    assert "changed_artifacts" in text
    assert "reread_ok" in text
    assert "audit-existing" in text
    assert "setup_errors" in text
    assert "probe requires at least" in text
    assert "real reading quality probes require --codex-reread" in text
    assert "--bulk-prompt-probe" in text
    assert "bulk_prompt_probe" in text
    assert "one independent paper job per bibkey" in text
    assert "persistent reader session and an independent reviewer session" in text
    assert "--bulk-max-parallel" in text
    assert "default=5" in text
    assert "Do not process the papers sequentially" in text
    assert "If it reports per-bibkey failures" in text
    assert "The main session must not write `.tmp/read_pool/<run_id>/<bibkey>/draft/{source_map.json,note_plan.json,deep_read.json}`" in text
    assert "deterministic draft writer" in text
    assert "generic bulk draft generator" in text
    assert "shortcut_artifacts" in text
    assert "shortcut_transcript_hits" in text
    assert "read_pool_audit" in text
    assert "_audit_read_pool_run" in text
    assert "_latest_read_pool_run" in text
    assert "bulk_timeout" in text
    assert "codex-bypass-sandbox" in text
    assert "PAPER_ENGINE_ALLOW_UNSANDBOXED_PROBE" in text
    assert "PAPER_ENGINE_CODEX_BYPASS_SANDBOX" in text
    assert "--dangerously-bypass-approvals-and-sandbox" in text
    assert "subprocess.TimeoutExpired" in text
    assert "start_new_session=True" in text
    assert "os.killpg" in text
    assert ".write_check" in text
    assert "Hard time budget" in text
    assert "Do not cat or dump full parsed.md" in text


def test_live_codex_probe_is_opt_in_and_uses_codex_runner():
    text = (ROOT / "scripts" / "run_live_codex_probe.py").read_text(encoding="utf-8")
    assert "PAPER_ENGINE_LIVE_CODEX" in text
    assert "SubprocessCodexRunner" in text
    assert "status --json" in text
    assert "policy check --json" in text


def test_live_web_flow_probe_is_opt_in_and_checks_bootstrap_flow():
    text = (ROOT / "scripts" / "run_live_web_flow_probe.py").read_text(encoding="utf-8")
    assert "PAPER_ENGINE_LIVE_CODEX" in text
    assert "sync_playwright" in text
    assert "data-codex-model" in text
    assert "data-codex-effort" in text
    assert "topic.yml" in text
    assert "文献库" in text
    assert 'default="gpt-5.6-sol"' in text


def test_reading_quality_probe_rejects_unsandboxed_bypass_without_env(monkeypatch, tmp_path):
    module = _load_reading_probe_module()
    monkeypatch.delenv("PAPER_ENGINE_ALLOW_UNSANDBOXED_PROBE", raising=False)

    result = module._codex_reread(
        project_root=ROOT,
        probe_root=tmp_path,
        bibkey="Smith2024Paper",
        model="gpt-5.6-sol",
        effort="medium",
        timeout_s=30,
        bypass_sandbox=True,
    )

    assert result["ok"] is False
    assert "PAPER_ENGINE_ALLOW_UNSANDBOXED_PROBE=1" in result["error"]


def test_reading_quality_probe_scans_assistant_output_not_user_prompt():
    module = _load_reading_probe_module()

    prompt_only = {
        "stdout_tail": "user prompt says: do not create a deterministic draft writer or generic bulk draft generator",
        "assistant_stdout_tail": "I used read-many reader and reviewer jobs and stopped on failure.",
    }
    assistant_violation = {
        "stdout_tail": "irrelevant",
        "assistant_stdout_tail": "I created a deterministic draft writer for schema-valid drafts.",
    }

    assert module._shortcut_transcript_hits(prompt_only) == []
    assert "deterministic draft writer" in module._shortcut_transcript_hits(assistant_violation)


def test_reading_quality_probe_bulk_prompt_uses_configured_parallelism(monkeypatch, tmp_path):
    module = _load_reading_probe_module()
    captured = {}

    def fake_command(*, project_root, probe_root, model, effort, bypass_sandbox, prompt):
        captured["prompt"] = prompt
        return {"ok": False, "error": "captured"}

    monkeypatch.setattr(module, "_codex_command", fake_command)

    result = module._codex_bulk_reread(
        project_root=ROOT,
        probe_root=tmp_path,
        bibkeys=["A2024", "B2024"],
        model="gpt-5.6-sol",
        effort="medium",
        timeout_s=30,
        bypass_sandbox=False,
        bulk_max_parallel=4,
    )

    assert result["ok"] is False
    assert "--max-parallel 4" in captured["prompt"]
    assert "paper_engine read-many" in captured["prompt"]


def test_web_render_script_writes_artifacts():
    text = (ROOT / "scripts" / "check_web_render.py").read_text(encoding="utf-8")
    assert ".tmp/render-checks" in text
    assert "dashboard-desktop.png" in text
    assert "candidates-desktop.png" in text
    assert "library-desktop.png" in text
    assert "paper-detail-desktop.png" in text
    assert "dashboard-mobile.png" in text
    assert "bootstrap-desktop.png" in text
    assert "bootstrap-mobile.png" in text
