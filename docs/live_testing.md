# Live Testing

In this project, "live testing" means the full user-journey acceptance flow below. It is not the same as unit tests, fake-runner tests, static render checks, or a narrow Codex probe.

The purpose is to catch first-step user failures and cross-module regressions before claiming the browser workbench is usable.

## Standard Environment

Run live testing from the PaperEngine project root:

```bash
cd /path/to/PaperEngine
PYTHONPATH=/home/battery/.local/lib/python3.10/site-packages:src ./bin/paper_engine --help
codex --help
```

Playwright should use the container-installed Python package and Chromium:

```text
PYTHONPATH=/home/battery/.local/lib/python3.10/site-packages:src
/home/battery/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome
```

The canonical command is:

```bash
cd /path/to/PaperEngine
PYTHONPATH=/home/battery/.local/lib/python3.10/site-packages:src \
python3 scripts/run_live_user_journey_e2e.py
```

A run is not a live test unless it exercises the browser UI and the real Codex worker path. If the script is unavailable or fails before preflight, report that as a project test infrastructure blocker.

## Required Artifacts

Write all test output under an isolated topic parent:

```text
/paper_hub/_paper_engine_e2e/<timestamp>/
```

Keep successful and failed runs. Each run must preserve:

- the generated topic directory;
- `e2e_report.json`;
- screenshots for every major stage;
- `.paper_engine_serverlet/` and topic `.paper_engine/` job summaries, events, and stderr logs;
- any downloaded PDFs, parsed notes, and generated HTML reading output.

Do not write this test into an ordinary user topic.

## Required User Journey

1. **Preflight**
   - Confirm `./bin/paper_engine --help` works from `/path/to/PaperEngine`.
   - Confirm `codex --help` works in the same environment that starts the serverlet.
   - Confirm Playwright and Chromium are importable/runnable.
   - Confirm the chosen port is free and do not kill a user's running server.
   - If any check fails, stop and report the blocker as environment, dependency, Codex, network, or code.

2. **Create Topic From UI**
   - Start the workbench with `./bin/paper_engine start --base-dir /paper_hub/_paper_engine_e2e/<timestamp> --host 127.0.0.1 --port <free-port>`.
   - Open `/dashboard.html` in Playwright.
   - Fill title, direction, and optional seed paper in the Create Topic page.
   - Click Create Topic and wait until the app binds to the new topic.
   - Assert `topic.yml`, `policy.yml`, `preferences.yml`, `README.md`, and `AGENTS.md` exist.
   - Save screenshots before submit, after submit, and after the dashboard appears.

3. **Search Candidates**
   - Use the right-side Codex chat or quick action from the browser UI to request at least 12 real candidates.
   - Wait for the Codex task to finish.
   - Assert at least 3 candidates are present, candidate IDs are unique, titles are nonempty, and abstracts are nonempty.
   - Record missing venue fields as a quality warning rather than an automatic failure.
   - Save a candidates page screenshot.

4. **Preference Actions**
   - Pick three visible candidates.
   - Mark one relevant, one irrelevant, and one dismissed through the UI buttons.
   - After each action, wait for state/UI refresh.
   - Assert the queue tab removes handled candidates, the relevant/irrelevant/all tabs show the correct status, and the chosen preference button stays highlighted.
   - Save screenshots after each preference action.

5. **Download PDF And Promote**
   - Select relevant candidates and click Download PDF from the browser UI.
   - If a candidate has no open-access PDF, try additional relevant candidates and record each failure reason.
   - Passing threshold: at least one real PDF is stored as `papers/<bibkey>/paper.pdf`.
   - Assert no duplicate official PDF is shown from `.tmp` or `_incoming`.
   - Run and record `./bin/paper_engine bib check --root <topic>` and `./bin/paper_engine pdf check --root <topic>`.
   - Assert the Library page shows the promoted paper and that the title-row PDF icon opens the PDF.

6. **Read Paper**
   - In the Library page, select one downloaded paper and click Read Paper.
   - The reading step must use the current Codex operation path; do not start a hidden nested Codex process unless the project explicitly changes that design.
   - Assert the paper directory contains parsed text, structured deep-read JSON, a Markdown note, and the rendered HTML reading output.
   - Assert the Library note/knowledge icon points to the rendered HTML result.
   - Save Library and paper detail screenshots after reading.

7. **Visual Checks**
   - Capture desktop screenshots at `1440x900`.
   - Capture mobile screenshots at `390x844` for dashboard and candidates.
   - Assert no horizontal overflow, no obvious text overlap, no disabled buttons stuck after task completion, and no chat sidebar obstruction.
   - The visual gate is screenshot plus DOM/layout assertions, not strict pixel diff.

## Pass/Fail Rules

Live testing passes only if all of the following are true:

- topic creation works from the browser UI;
- real Codex execution is used for user actions;
- at least 3 candidates are collected;
- relevant, irrelevant, and dismissed actions all change topic state and UI state;
- at least 1 real PDF is downloaded and promoted into the Library;
- BibTeX and PDF checks pass;
- at least 1 downloaded paper is read and has rendered HTML output;
- required screenshots and `e2e_report.json` are written;
- blockers are absent or explicitly classified as external availability issues.

A failed live test must report the first failing stage, the last successful stage, the exact error, the related job directory, and the screenshot that shows the user-visible state.

## Relationship To Other Tests

- `python3 -m pytest -q` remains the required fast regression suite.
- `scripts/check_web_render.py` remains a render-health check, not a live test.
- `scripts/run_live_codex_probe.py` and `scripts/run_live_web_flow_probe.py` are useful probes, but they are not sufficient live testing.
- From now on, when development notes or user requests say "live测试", they refer to this full user-journey flow.

## Subagent Adversarial Probe

Use this gate when a change touches sidecar/subagent execution, batch candidate scoring, batch collection, batch rereading, job locking, or temporary artifact cleanup.

```bash
cd /path/to/PaperEngine
PYTHONPATH=/home/battery/.local/lib/python3.10/site-packages:src \
python3 scripts/run_subagent_adversarial_probe.py --json
```

This probe is intentionally deterministic and does not call a real model by default. It creates a temporary `/tmp/paper-engine-subagent-adversarial-*` workspace, then checks:

- topic-level job locking blocks concurrent state writers;
- score shards can be merged only after schema/range/identity validation;
- malformed or out-of-range score shards do not produce an applyable merged score file;
- paper-reading sidecar findings stay isolated from final `source_map.json`, `note_plan.json`, and `deep_read.json`;
- temporary sidecar workspaces are removed by default.

Use `--keep-work-dir` only while debugging the probe itself. Passing this probe does not replace reading-quality live testing; it only validates that the batch sidecar protocol is safe to use.

## Reading Quality Acceptance

Use this gate when a change touches paper reading, translation, PDF parsing, formula fallback, reading-result rendering, or the `paper_deep_read` skill. This is a separate acceptance gate from the browser user journey above: it exists to catch fake rereads, repeated knowledge cards, prompt leakage, weak Chinese output, and math/formula failures.

The gate must use a temporary copy of a real topic, not an ordinary user topic. The probe script copies only the named paper folders plus topic metadata, then validates the copied artifacts.

### Required Scale

A formal reading-quality live test must reread at least five distinct papers:

```bash
cd /path/to/PaperEngine
PAPER_ENGINE_ALLOW_UNSANDBOXED_PROBE=1 \
PYTHONPATH=/home/battery/.local/lib/python3.10/site-packages:src \
python3 scripts/run_reading_quality_probe.py \
  --topic-root /paper_hub/optimal-control-multiple-shooting-in-ode \
  --codex-reread \
  --codex-bypass-sandbox \
  --min-papers 5 \
  --model gpt-5.6-sol \
  --effort medium \
  --per-paper-timeout 1800 \
  --bibkey Bonalli2017Solving \
  --bibkey Zhang2018Solve \
  --bibkey LemosPaiao2020Survey \
  --bibkey Riera2026On \
  --bibkey Janssens2024Parallel
```

`--codex-bypass-sandbox` is only for the Docker environment where Codex cannot create user namespaces. It is intentionally guarded by `PAPER_ENGINE_ALLOW_UNSANDBOXED_PROBE=1`; do not set that variable for ordinary topic work.

For a one-paper debugging smoke test, explicitly lower the gate:

```bash
python3 scripts/run_reading_quality_probe.py \
  --topic-root <topic-root> \
  --codex-reread \
  --min-papers 1 \
  --bibkey <bibkey>
```

Do not report a one-paper smoke test as reading-quality live acceptance.

The 1800-second single-paper budget is deliberate. Math-heavy and PDE/control papers can finish validation and artifact generation after 900 seconds but fail to exit cleanly before the probe timeout. Use a shorter timeout only for debugging a fast paper, not for formal acceptance.

For bulk-workflow testing, use one realistic multi-paper Codex prompt instead of one Codex process per paper:

```bash
cd /path/to/PaperEngine
PAPER_ENGINE_ALLOW_UNSANDBOXED_PROBE=1 \
PYTHONPATH=/home/battery/.local/lib/python3.10/site-packages:src \
python3 scripts/run_reading_quality_probe.py \
  --topic-root /paper_hub/optimal-control-multiple-shooting-in-ode \
  --codex-reread \
  --bulk-prompt-probe \
  --codex-bypass-sandbox \
  --min-papers 5 \
  --model gpt-5.6-sol \
  --effort medium \
  --bulk-timeout 7200 \
  --bibkey Bonalli2017Solving \
  --bibkey Zhang2018Solve \
  --bibkey LemosPaiao2020Survey \
  --bibkey Riera2026On \
  --bibkey Janssens2024Parallel
```

This is the required gate for changes to multi-paper rereading behavior. It checks whether the real Codex worker routes through `read-many`, creates reader/reviewer records under `.tmp/read_pool`, and avoids helper scripts, deterministic draft generators, parsed/index-only schema fillers, or other shortcuts under `.tmp/read_pool` or `.tmp/read_batch`.

When two planned validation rounds both exercise the `read-many` reader/reviewer path, merge them into one larger adversarial run instead of running two near-duplicate probes. Use at least five papers for ordinary development acceptance; use at least ten papers only when the change touches all-library behavior, cross-paper reduce audit, or large-run orchestration.

For release-level reading claims, run at least 30 papers from a temporary topic copy. Use a mixed sample: math/theory, survey, method/algorithm, application/experiment, and mixed papers. The release gate may take hours and token budget; do not replace it with a deterministic fake draft test. Full-library stress testing is optional for ordinary changes but required before claiming a whole topic can be reliably reread end to end.

### Pass/Fail Rules

The probe passes only if all of the following are true:

- at least five unique bibkeys are provided;
- every named paper is reread by Codex in the temporary topic copy;
- `source_map.json`, `note_plan.json`, or `deep_read.json` changes for each reread paper;
- bulk prompt runs produce a `read_pool_audit` result with reader/reviewer records for every named paper;
- bulk prompt runs do not create helper scripts, deterministic draft generators, parsed/index-only schema fillers, or other shortcut files under `.tmp/read_pool` or `.tmp/read_batch`;
- Codex transcripts do not describe using deterministic draft writers, schema-valid draft generators, staging helpers, or parsed/index-only bulk generation;
- `paper_engine read <bibkey> --validate-report` passes for every paper;
- `paper_engine read <bibkey> --quality-audit` passes for every paper;
- `paper_engine tool audit-readings --json` passes for the temporary topic copy;
- theory/math papers do not leave required formula-vision fallback in a pending state;
- generated `note.md`, `note_zh.md`, and `reading_result.html` do not contain prompt text, validator wording, or workflow instructions.

If the probe fails, inspect the generated `reading_quality_probe_*.json` report first. The report records `successful_rereads`, changed artifacts, per-paper validator output, per-paper quality-audit output, and the library-level repeated-text audit.

### Existing Artifact Audit

To audit current topic artifacts without launching Codex rereads:

```bash
./bin/paper_engine tool audit-readings --root <topic-root> --json
```

This command is allowed to fail on old topics. A failing result is useful evidence: it means the current knowledge cards need selective rereading or repair before they should be trusted.
