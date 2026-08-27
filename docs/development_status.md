# Development Status

This file is the compact recovery point for long-running development.

Current phase: persistent Codex workbench refactor in progress on branch `feature/persistent-session-workbench`.

Repository rules:

- Keep this component runnable on `main`.
- Use feature branches for substantial phases.
- Prefer focused tests before implementation changes.
- Do not copy runtime caches, generated dependency folders, or old topic repositories into source control.
- Public user docs should describe the product workflow, not internal development-version history.

Architecture target:

- Browser workbench is the ordinary user entry point.
- `paper_engine start --root <topic>` is the default user entry after topic initialization.
- Chat messages and UI actions enter one persistent Codex operator session.
- Codex uses `paper_engine` CLI primitives for state changes.
- Topic files are the only source of truth.
- The web server may render state and manage job logs, but should not directly perform literature workflow mutations.

Latest verified state:

- Added an app-server backed persistent Codex session manager plus fake session tests.
- Added `/api/session/start`, `/api/session/state`, `/api/session/events`, `/api/session/message`, `/api/session/action`, and `/api/session/stop`.
- Refactored the browser shell into a two-pane workbench: workspace pages on the left, persistent Codex operator on the right.
- Moved common actions into the Codex operator quick chips: Search +30, Score Queue, and Work Status.
- Refactored List/Candidates so relevance, dismiss, and selected PDF download route through session actions instead of old direct page forms.
- Refactored Library so titles carry PDF/Note links, selected papers route through `library_read_selected`, and markdown note links no longer appear in the browser library.
- Simplified Overview metrics to Total Paper, Candidate, Downloaded, and Read Paper.
- Bootstrap pages keep the Codex session disabled until a topic is created and bound.
- Local verification after this refactor: `python3 -m pytest -q` passed with 203 tests.
- Local render verification after this refactor: `python3 scripts/check_web_render.py --root .tmp/v3c-final-render-topic --out .tmp/v3c-final-render-out` passed with 7 pages. The local environment still lacks Playwright/Chromium, so browser-pixel screenshots were not available locally.
- Remote sync used explicit file pushes rather than `rpush-all` because dry-run showed `.tmp`, `.git`, and adjacent project cache files would otherwise be pushed.
- Remote verification after final sync: `python3 -m pytest -q` passed with 203 tests in the `battery_research_literature` container.
- Remote render verification after final sync: `python3 scripts/check_web_render.py --root .tmp/v3c-remote-final-render-topic-2 --out .tmp/v3c-remote-final-render-out-2` passed with 7 pages.
- Remote live Codex app-server probe passed with a real persistent session, returned status `idle`, and reported `context_left` around 0.9458.

- Source baseline copied from the existing file-state implementation.
- Runtime caches and Git metadata were excluded during copy.
- This directory is an independent Git repository.
- Baseline commit: `70cae69 Bootstrap V3 baseline`.
- Added `CodexRunner`, `FakeCodexRunner`, bounded prompt contracts, and file-backed `JobManager`.
- Job artifacts are written under `.paper_engine/jobs/<job_id>/` with prompt, events, stderr, summary, active-job state, and append-only job log.
- Added a minimal web workbench skeleton with `paper_engine web serve`.
- Web pages currently render dashboard, candidates, library, active job, and recent job state from topic files.
- Web skeleton is read-only; it does not mutate literature workflow state.
- Dashboard collect/search form now enqueues a bounded Codex job.
- Web handler creates job artifacts only; it does not directly edit candidate/library/PDF state.
- Active-job conflicts return a 409 JSON response.
- Candidate page now has relevant, irrelevant, and download PDF controls.
- Candidate controls enqueue bounded Codex jobs for `paper_engine candidates mark`, `paper_engine acquire`, and `paper_engine promote`.
- Candidate web handlers do not directly mutate `candidates.jsonl` or download files.
- Library page now has a read-paper control.
- Library read action enqueues a bounded Codex job that runs parse, follows `skills/paper_deep_read/SKILL.md`, validates the report, and rebuilds notes.
- Library web handler does not directly parse PDFs or write `deep_read.json`.
- Added server-rendered web page checks for nonblank dashboard, candidates, library, and CSS route.
- Added deployment guide plus English and Chinese user manuals.
- Verification: `python3 -m pytest -q` passed with 108 tests.
- Local web probe: dashboard, candidates, library, and CSS routes returned HTTP 200 with nonempty bodies on `127.0.0.1:18005`.
- Codex CLI live probe succeeded with account default model: `codex exec --json --sandbox workspace-write`.
- `gpt-5.5-medium` was rejected by the active ChatGPT account, so worker jobs intentionally omit `--model` unless `PAPER_ENGINE_CODEX_MODEL` is set.
- Candidate and library pages now expose client-side search and sortable columns.
- Candidate page has a status filter.
- Verification: `python3 -m pytest -q` passed with 112 tests.
- Final local web probe: dashboard, candidates, library, CSS, and JS routes returned HTTP 200 with nonempty bodies on `127.0.0.1:18006`.
- Review follow-up fixed job runtime issues: active-job locking is atomic, web actions return 202 after creating a background job, and Codex stderr is merged into stdout to avoid pipe deadlocks.
- Web action inputs now reject unsafe candidate IDs, bibkeys, and query text containing prompt-injection-prone characters.
- Verification: `python3 -m pytest -q` passed with 116 tests.
- Added JSON API routes for status, jobs, dashboard Codex actions, candidate actions, and library actions.
- Added opt-in `scripts/run_live_codex_probe.py`; default run skips unless `PAPER_ENGINE_LIVE_CODEX=1`.
- Added `scripts/check_web_render.py` for lightweight render artifact checks.
- Deployment troubleshooting now covers connection, Codex, stuck job, dependency, search backend, and stale state issues.
- Candidate UI now includes tabs, year/venue/source/status filters, checkbox selection, expandable abstract metadata, and dismiss/download controls.
- Library UI now includes checkbox selection, PDF/knowledge links, missing-PDF state, and selected-paper action affordance.
- Paper compatibility detail route is available under `/papers/<bibkey>.html`; generated reading output is stored under `papers/<bibkey>/reading_result.html`.
- Verification: `python3 -m pytest -q` passed with 127 tests.
- `python3 scripts/check_web_render.py --root <tmp-topic> --out <tmp-out>` passed with 5 pages and produced valid PNG artifacts for dashboard desktop/mobile, candidates desktop, library desktop, and paper detail desktop.
- `PAPER_ENGINE_LIVE_CODEX=1 python3 scripts/run_live_codex_probe.py` passed locally with a real `codex exec --json` worker job.
- Playwright is not installed in the current local Python environment; render verification currently uses lightweight HTML artifacts rather than browser screenshots.
- Remote workstation sync: `/battery_research_literature/V3` created in container mount.
- Remote container verification: `python3 -m pytest -q` passed with 127 tests on commit `84c5016`.
- Remote container render verification: `scripts/check_web_render.py` passed with 5 pages using the remote container Python environment.
- Remote container Git safe.directory configured for `/battery_research_literature/V3`; Git status is clean.
- Remote container Codex CLI is available.
- V3b branch `feature/serverlet-first-v3b` started from clean `main`.
- Baseline verification before V3b: `python3 -m pytest -q` passed with 127 tests.
- Added `paper_engine start` as the serverlet-first entry; `web serve` remains a compatibility path.
- Centralized serverlet operation prompt: every job states browser UI is the user interface, forbids sibling-topic inspection, forbids direct business file edits, and requires CLI-based state changes.
- `SubprocessCodexRunner` now invokes `codex exec --json --sandbox workspace-write -C <topic_root> -` and sends the operation prompt through stdin.
- Added job detail and event APIs under `/api/jobs/<job_id>` and `/api/jobs/<job_id>/events`.
- Dashboard now includes a command console, Search, Score Candidates, Health Check, Rebuild HTML, active job display, recent jobs, async action submission, and job polling.
- Candidate and library actions now route through `/api/codex/...` endpoints; selected candidate PDF download and selected paper reading create batched Codex jobs.
- Added serverlet safety tests for multiline chat, control-character rejection, missing shell bridge, and blocker-reporting prompt behavior.
- Added workflow-level fake-runner test showing browser action creates job artifacts and recent summary without direct candidate mutation.
- Public user manuals now present browser/serverlet operation as the normal path; external Codex is documented only as an advanced/debug fallback.
- Local verification after V3b refactor: `python3 -m pytest -q` passed with 155 tests.
- Local render verification after V3b refactor: `python3 scripts/check_web_render.py --root .tmp/v3b-render-topic --out .tmp/v3b-render-out` passed with 5 pages.
- Local sandbox live Codex probe was attempted with `PAPER_ENGINE_LIVE_CODEX=1 python3 scripts/run_live_codex_probe.py`; the local sandbox failed before model work with `failed to initialize in-process app-server client: Read-only file system`.
- Remote container dependencies were installed from `requirements.txt` and `requirements-dev.txt`. In this container, Python has `ENABLE_USER_SITE=False`, so verification used `PYTHONPATH=/home/battery/.local/lib/python3.10/site-packages`.
- Remote container verification after V3b sync: `python3 -m pytest -q` passed with 155 tests.
- Remote container render verification after V3b sync: `python3 scripts/check_web_render.py --root .tmp/v3b-remote-render-topic --out .tmp/v3b-remote-render-out` passed with 5 pages.
- Remote container live Codex probe after V3b sync: `PAPER_ENGINE_LIVE_CODEX=1 python3 scripts/run_live_codex_probe.py --root .tmp/v3b-remote-live-codex-topic` returned `ok: true` and created job `20260618T214216Z-27b5ad97`.
- The remote live Codex probe emitted a Codex cache TTL log line, but the job completed successfully; treat this as non-blocking Codex runtime noise unless it starts failing jobs.
- Final local verification on the current branch head: `python3 -m pytest -q` passed with 155 tests.
- Final remote verification on the current branch head: `python3 -m pytest -q` passed with 155 tests.
- Completion audit: the browser/serverlet is the ordinary user path, Web actions enqueue Codex jobs rather than direct business mutations, the prompt contract is centralized, docs present serverlet-first usage, and local plus remote verification gates passed.
- Added start-before-init bootstrap mode: `paper_engine start --base-dir <parent-dir>` serves a Create Topic page, enqueues a clean-room Codex init job, stores bootstrap jobs in `<base-dir>/.paper_engine_serverlet/`, and binds the running WebApp to the created topic after required topic files exist.
- Existing-topic startup remains available through `paper_engine start --root <topic>`.
- Local verification after bootstrap mode: `python3 -m pytest -q` passed with 168 tests.
- Local render verification after bootstrap mode: `python3 scripts/check_web_render.py --root .tmp/bootstrap-final-render-topic --out .tmp/bootstrap-final-render-out` passed with 7 pages, including bootstrap desktop/mobile artifacts.
- Remote verification after bootstrap mode: `python3 -m pytest -q` passed with 168 tests.
- Remote render verification after bootstrap mode: `python3 scripts/check_web_render.py --root .tmp/bootstrap-remote-render-topic --out .tmp/bootstrap-remote-render-out` passed with 7 pages.
- Remote live Codex bootstrap smoke created and bound temporary topic `.tmp/live-bootstrap-base/live-bootstrap-probe` through `/api/codex/init-topic`.
- Browser screenshot tooling is not installed in the local or remote container environment; visual confirmation used server-rendered HTML artifacts plus lightweight PNG render-health artifacts.

Open risks:

- Local sandbox still cannot run live Codex because its Codex runtime hits a read-only filesystem during app-server initialization.
- Concurrent active-job locking and invalid active lock handling are covered by tests.
- Rendering checks cover nonblank pages, nav links, action forms, static CSS, and static JS, but Playwright is still optional.
- Current web pages cover core serverlet-first operation; advanced UX polish remains future work.
