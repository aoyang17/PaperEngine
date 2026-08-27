# PaperEngine

PaperEngine is a reusable research workspace for extracting the core knowledge of papers and reproducing their model simulations. It combines reproducible search, candidate screening, PDF acquisition, evidence-grounded deep reading, BibTeX management, research synthesis, and simulation-reproduction artifacts. The browser workbench is the ordinary interface, while `paper_engine` is the deterministic command layer.

The repository's current default topic remains silicon-carbon negative-electrode materials for high-energy traction batteries. Topic-specific scope lives in `research_profile/` and `topics/silicon-carbon-anodes/`; the engine and its templates are intended to remain reusable for other literature domains.

The initial review is organized around material architecture, prelithiation, binders and electrolytes, electrode engineering, degradation and safety, scale-up, and cell-level validation. See [`research_profile/scope.md`](research_profile/scope.md), [`research_profile/search_queries.md`](research_profile/search_queries.md), and [`research_profile/review_protocol.md`](research_profile/review_protocol.md).

Core properties:

- Pure file state: no SQLite.
- Self-contained package under this project root.
- No imports or runtime calls into unrelated local projects or private skill collections.
- BibTeX is generated from verified metadata, not model memory.
- Search/PDF fallback remains open-access only.
- Deep paper reading is a topic-local skill workflow: the Codex operation worker writes `papers/<bibkey>/deep_read.json`; `paper_engine` only parses, validates, rebuilds notes, and renders reports.

Naming:

- Product: `PaperEngine`
- Python package and primary CLI: `paper_engine`
- Distribution package: `paper-engine`
- The former `battery_lit` CLI remains as a deprecated compatibility alias; new code should use `paper_engine`.

Quick start:

```bash
python3 -m pip install -r requirements.txt -r requirements-dev.txt
bin/paper_engine start --base-dir /tmp --host 0.0.0.0 --port 10005
```

Then open `http://<server-ip>:10005/dashboard.html`, create a topic in the browser, and continue operating from the browser workbench.
Every page includes Language, Codex model, and Effort selectors in the right-side Codex operator. UI actions and natural-language messages enter the same persistent Codex session.
`paper_engine start` disables the Codex runtime sandbox by default for this serverlet process because Docker user-namespace sandboxing can block `paper_engine` itself. Topic `policy.yml` and the `paper_engine` CLI remain the project safety boundary. Use `--codex-sandbox` only when debugging in an environment where Codex workspace sandboxing is known to work.

If you have a title and a parent directory but not a final folder name, let the CLI derive a safe slug:

```bash
bin/paper_engine init --base-dir /tmp --title "Silicon-Carbon Anodes for Traction Batteries" --direction "Materials, interfaces, manufacturing, degradation, safety, and cell-level validation of silicon-carbon negative electrodes"
# creates /tmp/silicon-carbon-anodes-for-traction-batteries
```

Running from source:

- Prefer `bin/paper_engine ...`; the wrapper automatically adds this repository's `src/` directory to `PYTHONPATH`.
- If invoking Python modules directly from the project root, set the project-local source path explicitly:

```bash
PYTHONPATH=src python -m paper_engine.cli status --root /tmp/paper-topic --json
```

Serverlet-first entry:

- Start the serverlet before topic init:

```bash
./bin/paper_engine start --base-dir <parent-dir> --host 0.0.0.0 --port 10005
```

- Create the topic in the browser. The init job uses `templates/skills/topic_init/SKILL.md` and `paper_engine init --base-dir`; it must not inspect sibling topic folders.
- If initialization fails, the Create Topic page shows the real Codex/CLI error in Recent Jobs instead of failing silently.
- If a topic already exists, start directly from that topic:

```bash
./bin/paper_engine start --root <topic> --host 0.0.0.0 --port 10005
```

- Open `http://<server-ip>:10005/dashboard.html`.
- By default, `start` runs Codex turns without the Codex runtime sandbox so browser actions can execute `paper_engine` inside Docker. Add `--codex-sandbox` only to opt back into Codex workspace sandboxing.
- Use the right-side Codex operator to search, score candidates, read papers, and handle complex natural-language tasks. Quick command chips cover common actions such as search +30, score queue, and work status. Candidate preference buttons and selected PDF download are deterministic serverlet actions for responsiveness and reliability.
- The Overview page shows topic scope and four counters: Total Paper, Candidate, Downloaded, and Read Paper.
- The List page reviews all candidates with tabs, table sorting, venue filtering, abstract expansion, relevance buttons, dismiss, and selected PDF download.
- The Library page lists promoted papers; PDF and Note links live next to titles, and selected papers can be sent for reading.
- External interactive Codex is an advanced/debug fallback, not the normal operation path.

Advanced/debug fallback: Codex-assisted init when the user wants help refining a rough topic:

- Recommended init prompt:

```text
@/<path-to-PaperEngine>/README.md
使用 paper_engine 工具，在 <parent-dir>/ 下初始化一个新的 topic 目录。
名字定为 "<topic title>"。
检索方向是 <one paragraph research direction>.
```

- Example:

```text
@/<path-to-PaperEngine>/README.md
使用 paper_engine 工具，给我在 /paper_hub/ 下初始化一个新的 topic 目录。
名字定为 "动力电池硅碳负极"。
检索方向是收集硅碳负极的材料结构、预锂化、粘结剂与电解液、电极工程、衰减与安全、规模制造和全电池验证研究。
```

If the project is mounted at `/PaperEngine`, the first line becomes:

```text
@/PaperEngine/README.md
```

- Prefer explicitly referencing the project README with `@.../README.md`. Do not ask Codex to "load the paper_engine agent"; that wording can be confused with a multi-agent delegation instead of this repository workflow.
- To initialize a topic, ask Codex to use `templates/skills/topic_init/SKILL.md`. If title or direction is missing, Codex should ask for it before running `paper_engine init`.
- Ordinary init does not require listing parent directories, reading `.agents`/`.codex`, or inspecting existing topic repositories. If required inputs are missing, ask the user instead of inferring from local files.
- If only a base directory is known, Codex should use `--base-dir` and let the CLI slugify the title into a safe folder name. The base directory is not a context source: Codex should not inspect sibling topics or use them as templates.
- Codex should refine the user's rough description before writing final topic fields: preserve raw wording in `user_description_raw`, write a cleaned `direction`, and propose search terms/seed queries.
- After init, Codex should automatically enter the new topic with `skills/topic_enter/SKILL.md`.
- In a new session, say "enter <topic-root>" or "continue this topic"; Codex should read the topic guide/policy, run `policy check` and `status`, and avoid reading full `library.bib`, `candidates.jsonl`, or `papers/*` by default.

Advanced/debug deep-read workflow:

```bash
bin/paper_engine read --root /tmp/paper-topic <bibkey> --parse-only
```

This writes `papers/<bibkey>/parsed.md` and, when rendering is available, a lightweight visual index under `papers/<bibkey>/visual_index.md` and `papers/<bibkey>/page_images/`.

Then ask a Codex worker or advanced interactive Codex session to follow `/tmp/paper-topic/skills/paper_deep_read/SKILL.md`, write `/tmp/paper-topic/papers/<bibkey>/deep_read.json`, and run:

```bash
bin/paper_engine read --root /tmp/paper-topic <bibkey> --validate-report
bin/paper_engine read --root /tmp/paper-topic <bibkey> --rebuild-note
```

For an explicit reread that should overwrite stale results without using old notes as evidence, ask Codex to follow `/tmp/paper-topic/skills/paper_reread/SKILL.md`. A compact prompt is:

```text
Use the paper_reread skill to reread <bibkey>, overwrite the old knowledge card, and do not reuse existing deep_read/note/html as evidence.
```

For multiple selected papers, the controlled path is `paper_engine read-many`: one reader session and one independent reviewer session per paper, with final writes performed by the project controller after validation.

To import one already-library paper from an explicitly named source topic, use its source bibkey:

```bash
bin/paper_engine library import-from-topic --root /tmp/target-topic --source-root /tmp/source-topic --source-bibkey Example2026A --json
```

The import reports `imported` or `already_exists`; an import creates an `in_library`/`relevant` candidate without immediately refreshing `preferences.yml`. There is intentionally no browser button or batch import interface.

State-changing commands refresh static reports automatically. Run `bin/paper_engine html build --root /tmp/paper-topic` manually only after direct file edits, report repair work, or when `PAPER_ENGINE_AUTO_HTML=0` was used.
The static reading page is written to `papers/<bibkey>/reading_result.html`; generated paper assets stay under `papers/<bibkey>/`.

Serverlet direction:

- The browser UI is the ordinary user entry point.
- Topic operations should enter the persistent Codex session. Bootstrap init and compatibility endpoints may still use bounded jobs.
- Topic files remain the only source of truth.
- Use `./bin/paper_engine start --base-dir <parent-dir>` for ordinary first-time operation, or `./bin/paper_engine start --root <topic>` for an existing topic. `./bin/paper_engine web serve` is a compatibility alias for existing topics.

More docs:

- `docs/deployment.md`: install and run the tool.
- `docs/live_testing.md`: canonical "live testing" user-journey acceptance flow.
- `docs/user_manual.md`: concise English user guide.
- `docs/user_manual_zh.md`: concise Chinese user guide.
- `docs/simulation_reproduction.md`: five-stage agent architecture and COMSOL reproduction contract.
