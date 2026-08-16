# User Manual

## Start The Workbench

For a new topic, start the browser workbench from the parent directory:

```bash
cd /battery_research_literature/V3
./bin/battery_lit start --base-dir <parent-dir> --host 0.0.0.0 --port 10005
```

Create the topic in the browser. The init job uses Codex plus `battery_lit init`; it does not inspect sibling topic folders. If init fails, the Create Topic page shows the real error in Recent Jobs and the page status.

For an existing topic:

```bash
cd /battery_research_literature/V3
./bin/battery_lit start --root <topic> --host 0.0.0.0 --port 10005
```

Open:

```text
http://<server-ip>:10005/dashboard.html
```

The browser workbench is the ordinary user interface. A persistent Codex operator lives on the right side of every topic page. External Codex is an advanced/debug fallback for unusual maintenance, not the normal way to operate the topic.

Every topic page has Language, Codex model, and Effort selectors. Natural-language messages, quick command chips, and table buttons all enter the same persistent Codex session.

New sessions default to GPT-5.6 Sol with medium reasoning. Terra is the balanced everyday option, Luna is the faster low-cost option, and GPT-5.5 or Codex Spark remain available for compatibility and fast focused work. The browser exposes low through xhigh reasoning; Max and Ultra remain advanced CLI-only choices.

`battery_lit start` disables the Codex runtime sandbox by default for this serverlet process, because Docker user-namespace sandboxing can prevent Codex from running `battery_lit`. Topic `policy.yml` and the `battery_lit` CLI remain the safety boundary. Use `--codex-sandbox` only for debugging in an environment where Codex workspace sandboxing is known to work.

## Initialize A Topic From CLI

Use the CLI directly for scripts or debugging when title and direction are known:

```bash
./bin/battery_lit init --base-dir <parent-dir> --title "<topic title>" --direction "<one paragraph research direction>"
```

Advanced/debug fallback: if you want Codex to help refine a rough direction, attach the project README and ask it to run `battery_lit init`. It should not inspect sibling topic folders as examples.

## Collect Papers

In the right-side Codex operator:

- click Search +30 for a quick collection pass, or
- type a natural-language command such as `search 50 high-quality candidates and exclude existing papers`.

Codex uses topic skills and `battery_lit` commands. The UI keeps the same session alive across pages.

## Screen Candidates

On List:

- only admitted candidates are shown; raw search hits rejected by hard collection constraints do not enter All;
- use filters, sorting, and abstract expansion to review candidates;
- mark papers Relevant, Irrelevant, or Dismiss;
- select candidates and press Download Selected PDFs.

Preference marks are deterministic actions: they update candidate state immediately and refresh the page. Download Selected PDFs is also deterministic: the serverlet enriches metadata, downloads open PDFs, promotes BibTeX entries, and rebuilds HTML. Search, candidate scoring, and complex natural-language tasks still run through the persistent Codex session.

## Read Papers

On Library:

- open PDF or knowledge links from the title row;
- select papers and press Read Paper.

Codex follows the topic paper-reading skill, writes the structured reading artifact, validates it, and rebuilds note/report output. When multiple papers are selected, the backend uses `battery_lit read-many`: each paper gets an independent reader session plus an independent reviewer session.
Reading artifacts stay in the same paper directory: `papers/<bibkey>/paper.pdf`, `parsed.md`, `visual_index.md`, `page_images/`, `note.md`, and `reading_result.html`. The Library Knowledge link opens `reading_result.html`.

If an existing reading result is poor, tell the Codex operator:

```text
Use the paper_reread skill to reread <bibkey>, overwrite the old knowledge card, and do not reuse existing deep_read/note/html as evidence.
```

`paper_reread` treats old reading artifacts as overwrite targets, not evidence sources. For multiple papers it routes through `read-many`; for one paper it still uses `paper_deep_read`, then runs validation, quality audit, and note rebuild.

For a quick download-path check, select one existing candidate and press Download Selected PDFs. On success, the paper appears in Library with a PDF link next to the title.

## Import One Paper From Another Topic

Explicitly name the source topic path and source bibkey:

```bash
./bin/battery_lit library import-from-topic --root <target-topic> --source-root <source-topic> --source-bibkey <bibkey> --json
```

If you only know the title, Codex first uses `library find` against the named source topic and proceeds only with exactly one match. The command reports `imported`, `already_exists`, or a skipped/error result. An import creates an `in_library` candidate marked `relevant`; it does not immediately refresh `preferences.yml`. There is no browser button or batch import interface.

## Check State

Click Work Status in the Codex operator for ordinary checks. Useful CLI commands for debugging:

```bash
./bin/battery_lit status --root <topic> --json
./bin/battery_lit bib check --root <topic>
./bin/battery_lit pdf check --root <topic>
./bin/battery_lit html build --root <topic>
```

## Boundaries

Do not copy another topic as a template. The project templates are built into the tool. Existing sibling folders under the topic parent are out of scope unless you explicitly ask for migration or comparison.
