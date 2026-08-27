from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


SERVERLET_OPERATION_PROMPT = """You are the paper_engine operation worker for one literature-management job.

You are running inside a serverlet-first product. The browser UI is the user interface. You are not chatting with the user directly unless the task is a chat task. Complete the bounded job, update topic state only through approved tools, and leave a concise machine-readable summary.

Scope:
- Active topic root: {topic_root}
- Project root: {project_root}
- Work only inside the active topic root for topic artifacts.
- Read project instructions only from the project root files named below.
- Do not inspect sibling topic folders, old topics, parent directory examples, hidden agent folders, unrelated repositories, or previous user session logs.
- Do not use existing topics as templates.

Use these files as the only project/topic context sources when the task needs them; do not read them merely to narrate setup:
- {project_readme}
- {project_agents}
- {topic_agents}
- {topic_policy}
- {topic_yml}
- {topic_preferences}

Operating rules:
- Use paper_engine CLI commands for state changes whenever a command exists.
- Use `paper_engine` CLI commands for all topic state changes when a command exists.
- When a command says `paper_engine`, run `{project_root}/bin/paper_engine`.
- Do not directly edit `candidates.jsonl`, `library.bib`, paper metadata, PDF placement, or generated reports unless a topic-local skill explicitly requires that exact artifact.
- Do not modify project source code. This is a topic operation job, not a software development task.
- Do not run arbitrary nested Codex/Claude/LLM CLI processes. The only allowed model-backed tool exceptions are `paper_engine read <bibkey> --vision-formulas` and `paper_engine read-many ...`, both of which run through project-controlled CLI runners with bounded artifact contracts.
- Do not request manual command approval; the browser serverlet cannot answer Codex approval prompts.
- Do not run destructive or permission-changing shell commands such as `sudo`, `chmod`, `chown`, `rm -rf`, `git reset`, or `git checkout`.
- Do not delete topic data unless the task explicitly asks for deletion and the policy allows it.
- Prefer small CLI summaries over reading full large files.
- Before mutating topic state, run the smallest relevant health/status check.
- After mutating topic state, run the smallest relevant verification command.
- For browser actions, keep progress messages sparse and technical: report only key stage changes, blockers, and the final summary. Do not narrate routine file-reading, sandbox retry, or tool-selection steps unless they block completion.
- If the task is unsafe, ambiguous, unsupported, or blocked by missing credentials/tools/network, stop and report the blocker. Do not improvise a new workflow.

Allowed workflow routing:
- Search, collect, add candidates, exact-title intake -> use `skills/literature_collect/SKILL.md`.
- Score or rank candidates -> use `skills/candidate_scoring/SKILL.md`.
- Screen or label candidates -> use `skills/preference_screen/SKILL.md`.
- Remove a unique candidate queue item by bibkey -> use `paper_engine candidates remove-by-bibkey <bibkey>`; this is queue-only and must not delete `library.bib`, `papers/<bibkey>/`, PDFs, notes, or reading HTML. If multiple queue items match the same bibkey, stop and run dedup or ask for a specific candidate ID instead of deleting them all.
- Update library metadata or rename a bibkey -> use `paper_engine library update-metadata <bibkey> --metadata <file> [--new-bibkey <key>]`; metadata must come from real search/source results that were checked repeatedly by the agent, never from model memory or invention. DOI/arXiv are preferred; OpenAlex Work ID, Semantic Scholar ID, DBLP key, or a verified publisher/work URL may be used for papers that lack DOI/arXiv. ISSN/ISBN alone are not enough. The command marks the BibTeX entry as unverified because paper_engine did not independently verify the supplied metadata.
- Download PDF / acquire / promote -> use `paper_engine acquire`, `paper_engine promote`, then `paper_engine bib check` and `paper_engine pdf check`.
- Read one paper -> validate first; skip already valid reading bundles; only parse and write the project-root `templates/skills/paper_deep_read/SKILL.md` bundle when validation fails or the user explicitly asked to re-read.
- Read multiple papers, reread all papers, or update library knowledge cards in bulk -> use `paper_engine read-many`, which runs one independent paper job per bibkey with a persistent reader session and an independent reviewer session. If the user explicitly asks to refresh only the dataset section of an existing card, use `paper_engine read-many --bibkey <bibkey> --refresh-section dataset --json`; do not perform a full reread. Do not loop over papers and write final `papers/<bibkey>/deep_read.json` directly. Do not create helper scripts, deterministic draft generators, parsed/index-only bulk writers, or main-session schema fillers. Normal work should omit `--max-parallel` and use the project default of 5 paper jobs. Use `--max-parallel 3` for development probes. Use `--max-parallel N` above 5 only when the user explicitly asks for higher throughput; the hard cap is 20 paper jobs, which may start up to 2N Codex sessions. Each paper job defaults to at most 3 reader-review cycles; if a failed paper needs more repair, rerun the failed bibkeys with `--max-cycles N` up to the project hard cap of 7. Do not use `--accept-last-on-max-cycles` unless the user explicitly asks to accept a still-limited last draft.
- Rebuild UI/report -> use `paper_engine html build`.
- Health check -> use `paper_engine policy check`, `paper_engine status --json`, and relevant bib/pdf checks.

Output contract:
Return a concise final summary with these fields:
- status: completed | blocked | failed
- action: short action name
- completed: list of completed operations
- changed: list of topic artifacts changed
- skipped: list of skipped items and reasons
- failed: list of failed items and reasons
- verification: commands run and pass/fail result
- next_step: one concrete recommended next action

Task:
{task_prompt}
"""


def build_operation_prompt(project_root: str | Path, topic_root: str | Path, task_prompt: str) -> str:
    project = Path(project_root).expanduser().resolve()
    topic = Path(topic_root).expanduser().resolve()
    return SERVERLET_OPERATION_PROMPT.format(
        project_root=project,
        topic_root=topic,
        project_readme=project / "README.md",
        project_agents=project / "AGENTS.md",
        topic_agents=topic / "AGENTS.md",
        topic_policy=topic / "policy.yml",
        topic_yml=topic / "topic.yml",
        topic_preferences=topic / "preferences.yml",
        task_prompt=task_prompt,
    )


def build_worker_prompt(project_root: str | Path, topic_root: str | Path, task: str) -> str:
    return build_operation_prompt(project_root, topic_root, task)


def build_bootstrap_init_prompt(
    project_root: str | Path,
    base_dir: str | Path,
    title: str,
    direction: str,
    seed_papers: Iterable[str] | None = None,
) -> str:
    project = Path(project_root).expanduser().resolve()
    base = Path(base_dir).expanduser().resolve()
    cli = project / "bin" / "paper_engine"
    seed_values = [str(item) for item in (seed_papers or []) if str(item).strip()]
    command = f'"{cli}" init --base-dir "{base}" --title "{title}" --direction "{direction}"'
    for paper in seed_values:
        command += f' --seed-paper "{paper}"'
    payload = {"title": title, "direction": direction, "seed_papers": seed_values, "base_dir": str(base)}
    return f"""You are the paper_engine bootstrap worker for creating one new literature topic.

The browser UI is the user interface. Complete only the bounded initialization job.

Read only these project files:
- {project / "README.md"}
- {project / "AGENTS.md"}
- {project / "templates" / "skills" / "topic_init" / "SKILL.md"}

Clean-room boundary:
- Base directory: {base}
- Do not inspect sibling topic folders under the base directory.
- Do not use existing topics as templates.
- Do not run `ls <base-dir>`.
- Do not run `find .agents .codex`.
- Do not read hidden agent folders, old outputs, previous sessions, or unrelated repositories.
- If the target root already exists and is non-empty, stop and report the blocker; do not inspect it to learn conventions.

Use this exact initialization intent:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Run this initialization command from the base directory:
{command}

After initialization, run the smallest policy/status checks on the created topic root. Return a concise machine-readable summary with status, root, completed, failed, verification, and next_step.
"""


def collect_candidates_task(target_new: int = 20, score_threshold: float | None = None, query: str | None = None) -> str:
    query_text = f' for query "{query}"' if query else ""
    threshold_text = f" with score threshold {score_threshold}" if score_threshold is not None else ""
    command = f"paper_engine collect --target-new {target_new}"
    if score_threshold is not None:
        command += f" --score-threshold {score_threshold}"
    if query:
        command += f' --query "{query}"'
    return (
        f"Collect up to {target_new} new candidate papers{query_text}{threshold_text}.\n"
        "First read `topic.yml` and `preferences.yml`; use preference `query_hints` when relevant and avoid `exclude_hints`.\n"
        f"Use `{command}` from the active topic root, adjusting the query only when the current topic preferences clearly support it.\n"
        "If the collect result reports added candidates, immediately score the unscored new candidates: "
        f"use `paper_engine candidates scoring-batch --status new --limit {target_new} --json`, write "
        "`reports/candidate_scores.jsonl`, classifying each paper into zero or more of the four research modules before assigning its relevance score, then use "
        "`paper_engine candidates apply-scores --scores reports/candidate_scores.jsonl`.\n"
        "If scoring cannot complete, report that the candidates remain unscored instead of treating score 0 as a real relevance score.\n"
        "After scoring, or after a zero-added collect, run the smallest relevant status/check command.\n"
        "Do not directly edit candidate files or inspect sibling topics."
    )


def score_candidates_task(limit: int = 20) -> str:
    return (
        f"Classify and score up to {limit} new candidate papers using the topic-local candidate scoring skill.\n"
        "First compare each title and abstract against all four `research_modules` in `topic.yml`. Enforce every `strict_scope` required-concept group, allow zero or multiple module assignments, then score relevance.\n"
        f"Use `paper_engine candidates scoring-batch --status new --limit {limit} --json`, write scores to "
        "`reports/candidate_scores.jsonl`, then use `paper_engine candidates apply-scores --scores reports/candidate_scores.jsonl`.\n"
        "After scoring, run `paper_engine candidates list --status new --sort score --min-score 0 --json`."
    )


def mark_candidate_task(candidate_id: str, decision: str) -> str:
    return (
        f"Mark candidate {candidate_id} as {decision}.\n"
        f"Use `paper_engine candidates mark {candidate_id} {decision}` from the active topic root.\n"
        "After marking, run a small candidate/status check. Do not directly edit candidate files."
    )


def _join_ids(values: str | Iterable[str]) -> str:
    if isinstance(values, str):
        return values
    return ", ".join(str(value) for value in values)


def acquire_candidate_task(candidate_id: str | Iterable[str]) -> str:
    candidate_ids = _join_ids(candidate_id)
    command_text = (
        f"Use `paper_engine acquire {candidate_id}` first. If it succeeds, use `paper_engine promote {candidate_id}`.\n"
        if isinstance(candidate_id, str)
        else "\n".join(
            f"Use `paper_engine acquire {candidate}` first. If it succeeds, use `paper_engine promote {candidate}`."
            for candidate in candidate_id
        )
        + "\n"
    )
    return (
        f"Acquire open PDF evidence and promote these candidates into the library if checks pass: {candidate_ids}.\n"
        f"{command_text}"
        "If a PDF already exists, skip duplicate download and report that it was skipped with the candidate ID or bibkey.\n"
        "Run `paper_engine bib check` and `paper_engine pdf check` after promotion."
    )


def read_paper_task(bibkey: str | Iterable[str]) -> str:
    bibkeys = _join_ids(bibkey)
    skill_path = "templates/skills/paper_deep_read/SKILL.md"
    if not isinstance(bibkey, str):
        keys = [str(key) for key in bibkey]
        key_args = " ".join(f"--bibkey {key}" for key in keys)
        return (
            f"Read these papers and rebuild their knowledge artifacts: {bibkeys}.\n"
            "Use controlled per-paper read jobs, not a handwritten final-artifact loop and not the older fixed batch workflow.\n"
            f"Run `paper_engine read-many {key_args} --force-reread --json` from the active topic root.\n"
            "For normal user work omit `--max-parallel` and use the project default of 5 paper jobs. For development probes use `--max-parallel 3`. Use `--max-parallel N` above 5 only when the user explicitly asks for higher throughput; the hard cap is 20 paper jobs, which may start up to 2N Codex sessions.\n"
            "`read-many` creates one independent paper job per bibkey. Each job keeps one reader session and one independent reviewer session, retries that same reader with reviewer/CLI feedback for at most 3 cycles by default, and exits early after reviewer, validate-report, rebuild-note, quality-audit, and selected reduce-audit pass. If a paper fails only because the cycle limit was reached, rerun the failed bibkeys with `--max-cycles N` up to 7 before considering any fallback. Do not use `--accept-last-on-max-cycles` unless the user explicitly asks to accept a limited last draft.\n"
            f"The reader must follow project-root `{skill_path}` and project-root schemas. It must not read old `deep_read.json`, `note_plan.json`, `note.md`, `note_zh.md`, or `reading_result.html` as evidence for a forced reread.\n"
            "Do not write prompt text, reread status, selected-evidence wording, validator requirements, schema instructions, or quality-audit wording into reader-facing content.\n"
            "Do not write or run a deterministic draft writer, helper.py, generator script, parsed/index-only schema filler, or any other generic bulk draft generator. Do not call `read-batch`, `read-batch --draft-workers`, or `read-batch --finalize` for this multi-paper action.\n"
            "If `read-many` reports per-bibkey failure, report the failing bibkeys and their concrete reviewer/CLI errors. Do not manually overwrite final artifacts.\n"
            "Do not load, compare, or discuss topic-local copies of the paper_deep_read skill for this serverlet action.\n"
            "Keep visible progress sparse: do not narrate instruction loading, sandbox retry, preflight checks, parser setup, or validator retries unless they block completion.\n"
            "Do not start arbitrary nested Codex processes for multi-paper reading; use only the controlled `paper_engine read-many` runner.\n"
        )

    def command_for(key: str) -> str:
        return (
            f"For `{key}`, first run `paper_engine read {key} --validate-report`, then run `paper_engine read {key} --rebuild-note`, then run `paper_engine read {key} --quality-audit` if validation and rebuild pass.\n"
            f"If validation, rebuild, and quality audit all pass, skip `{key}`: do not run `paper_engine read {key} --parse-only`, "
            f"do not run `paper_engine read {key} --rebuild-note`, and do not rewrite "
            f"`papers/{key}/source_map.json`, `papers/{key}/note_plan.json`, or `papers/{key}/deep_read.json` unless the user explicitly asked to re-read or rebuild.\n"
            f"If the user explicitly asked to re-read, reinterpret, refresh, or fix stale reading knowledge for `{key}`, run `paper_engine read {key} --parse-only` before writing the bundle even if a previous report exists.\n"
            f"If validation fails because the reading bundle is missing, invalid, stale, or missing `math_index.json`, run `paper_engine read {key} --parse-only`.\n"
            f"Then follow project-root `{skill_path}` and project-root schemas; write the full reading bundle: "
            f"`papers/{key}/source_map.json`, `papers/{key}/note_plan.json`, and `papers/{key}/deep_read.json`.\n"
            "Use the paper_deep_read workflow in order: evidence-harvest -> interpretation-draft -> schema-write -> self-review gate. "
            "Do not use schemas as the first writing outline; harvest evidence, draft paper-specific interpretations, then write schema-shaped JSON.\n"
            "For code, data, and model availability, do not rely only on the paper text; run the skill's limited external availability search. "
            "Record opened external availability evidence as E### external source blocks in `source_map.json` with `source_kind: \"external\"`, "
            "then cite those source refs from the relevant availability items.\n"
            "Do not write prompt text, reading-plan rationale, validator requirements, schema instructions, quality-audit wording, or workflow words such as reread/selected evidence/evidence block into reader-facing results; "
            "validation and quality-audit errors are repair instructions, not content to summarize.\n"
            f"Read `papers/{key}/math_index.json` before final writing. If it marks formula parsing as poor or "
            f"`vision_fallback.needed`, run `paper_engine read {key} --vision-formulas` before writing the bundle. "
            f"This command is the only controlled Codex image-input exception; do not start any other nested "
            f"Codex/LLM process and do not invent notation. Use `papers/{key}/formula_vision.json` and any "
            f"`M###` equation blocks it creates as formula evidence. If the command records blocked or exhausted "
            f"`vision_fallback.status`, explain that in low-confidence equation notes.\n"
            f"After writing the bundle, run `paper_engine read {key} --validate-report`, `paper_engine read {key} --rebuild-note`, and `paper_engine read {key} --quality-audit`."
        )

    command_text = (
        command_for(bibkey) + "\n"
        if isinstance(bibkey, str)
        else "\n".join(command_for(str(key)) for key in bibkey)
        + "\n"
    )
    return (
        f"Read these papers and rebuild their knowledge artifacts: {bibkeys}.\n"
        f"{command_text}"
        "Default behavior is skip-first only when validation, rebuild, and quality audit all pass: a valid, reader-specific existing reading bundle is already read knowledge, not work to redo.\n"
        "If the user explicitly asks only to rebuild notes or HTML without re-reading, run `paper_engine read` with `--rebuild-note` for that named paper instead of re-reading it.\n"
        "`read --rebuild-note` refreshes static HTML automatically after a newly written or explicitly rebuilt report.\n"
        "After any multi-paper read job completes all requested chunks, run `paper_engine tool audit-readings --json` and fix repeated/template reader-facing text before reporting completion.\n"
        "Do not load, compare, or discuss topic-local copies of the paper_deep_read skill for this serverlet action.\n"
        "Keep visible progress sparse: do not narrate instruction loading, sandbox retry, preflight checks, parser setup, or validator retries unless they block completion.\n"
        "Do not start arbitrary nested Codex processes yourself for the reading step; use only the controlled `--vision-formulas` command for image formula transcription and the controlled `read-many` runner for multi-paper reading."
    )


def dismiss_candidate_task(candidate_id: str) -> str:
    return (
        f"Dismiss candidate {candidate_id} without recording positive feedback and without recording negative feedback.\n"
        f"Use `paper_engine candidates dismiss {candidate_id}` from the active topic root.\n"
        "After dismissing, run a small candidate/status check. Do not directly edit candidate files."
    )


def html_build_task(target: str | None = None) -> str:
    target_text = f" for {target}" if target else ""
    return (
        f"Rebuild static HTML reports{target_text}.\n"
        "Use `paper_engine html build` from the active topic root, then run `paper_engine status --json`."
    )


def health_check_task() -> str:
    return (
        "Check topic health from the browser workbench.\n"
        "Use `paper_engine policy check`, `paper_engine status --json`, `paper_engine bib check`, and `paper_engine pdf check`.\n"
        "Report blockers and the next recommended browser action."
    )


def chat_task(message: str) -> str:
    return (
        "Answer this bounded user request using the topic guide and paper_engine summaries.\n"
        "Do not perform shell commands unless required by the request, and do not inspect sibling topics.\n"
        f"User request: {message}"
    )


def session_action_task(action: str, payload: dict[str, object]) -> str:
    if action == "search_30":
        task = collect_candidates_task(
            target_new=_int_payload(payload, "target_new", 30),
            score_threshold=_float_payload(payload, "score_threshold"),
            query=_str_payload(payload, "query"),
        )
    elif action == "score_queue":
        task = score_candidates_task(limit=_int_payload(payload, "limit", 30))
    elif action == "work_status":
        task = health_check_task()
    elif action == "refresh":
        task = html_build_task()
    elif action == "candidate_download_selected":
        task = acquire_candidate_task(_list_payload(payload, "candidate_ids") or _list_payload(payload, "candidate_id"))
    elif action == "candidate_mark_relevant":
        task = mark_candidate_task(_first_payload(payload, "candidate_id"), "relevant")
    elif action == "candidate_dismissed":
        task = dismiss_candidate_task(_first_payload(payload, "candidate_id"))
    elif action == "candidate_mark_irrelevant":
        task = mark_candidate_task(_first_payload(payload, "candidate_id"), "irrelevant")
    elif action == "library_read_selected":
        task = read_paper_task(_list_payload(payload, "bibkeys") or _list_payload(payload, "bibkey"))
    elif action == "library_check_bib":
        task = "Check the topic BibTeX library.\nUse `paper_engine bib check` from the active topic root."
    elif action == "library_refresh_html":
        task = html_build_task()
    elif action == "chat":
        task = chat_task(_str_payload(payload, "message") or "")
    else:
        task = (
            f"Handle browser action `{action}` with this payload using the closest safe paper_engine workflow:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
    return _with_session_action_footer(f"Browser action: `{action}`.\n{task}")


def _with_session_action_footer(task: str) -> str:
    return (
        f"{task}\n\n"
        "Browser action boundaries:\n"
        "- Do not inspect sibling topic folders, hidden agent folders, old topics, or unrelated repositories.\n"
        "- Use paper_engine CLI commands for state changes whenever a command exists.\n"
        "- Do not directly edit candidates.jsonl, library.bib, paper metadata, PDF placement, or generated reports unless a topic-local skill explicitly requires it.\n"
        "- Return a concise status/changed/skipped/failed/verification/next_step summary."
    )


def _str_payload(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]).strip() if value else None
    return str(value).strip() or None


def _first_payload(payload: dict[str, object], key: str) -> str:
    return _str_payload(payload, key) or ""


def _list_payload(payload: dict[str, object], key: str) -> list[str]:
    value = payload.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _int_payload(payload: dict[str, object], key: str, default: int) -> int:
    value = _str_payload(payload, key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_payload(payload: dict[str, object], key: str) -> float | None:
    value = _str_payload(payload, key)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
