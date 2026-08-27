# PaperEngine Agent Guide

This project is Codex-first. Use `bin/paper_engine` as the deterministic tool layer and topic-local `skills/` as the operating workflow.

The default research domain is silicon-carbon negative-electrode materials for high-energy traction batteries. Keep collection, screening, and synthesis aligned with `research_profile/scope.md` and `research_profile/search_queries.md` unless the user explicitly changes the scope.

The browser workbench is a user interface over Codex jobs. It must not become a second business backend. Web actions should build bounded prompts for Codex, and Codex should call `paper_engine` for state changes.

## Entry Routes

Use `templates/skills/topic_init/SKILL.md` when the user asks to initialize, create, define, or refine a literature topic.

Use `templates/skills/topic_enter/SKILL.md` when the user asks to enter, resume, continue, or work in an existing topic repository.

## Init Rules

Do not call `paper_engine init` with missing title or direction. If either is missing, ask for:

1. topic title
2. one-sentence, one-paragraph, or keyword description of the research direction
3. optional seed papers

Do not run exploratory directory commands to confirm initialization conventions. In ordinary init, do not run `ls <base-dir>`, do not read `.agents` or `.codex`, and do not inspect existing topic repositories. Missing title or direction must be resolved by asking the user, not by inferring from local files.

If the user gives a base directory instead of a full topic root, use `bin/paper_engine init --base-dir <base> --title "<title>" --direction "<direction>"` so the CLI creates a safe slugified folder name. Do not use raw titles with spaces, slashes, colons, parentheses, or other special characters as directory names.

Topic initialization is clean-room by default. Treat `--base-dir` as a parent directory for creating the new topic root only. Do not list, search, read, summarize, copy, or use sibling folders under the base directory as examples or templates. The only default templates are this project's `templates/topic_repo/` and `templates/skills/`. If the target topic root already exists and is non-empty, stop and ask the user whether to enter that topic or choose a new root; do not inspect it to learn its format.

Do not inspect `.agents`, `.codex`, hidden directories, sibling topics, old outputs, or other local project directories during ordinary init. Only inspect external paths when the user explicitly asks to debug agent configuration or migrate/import/compare a specific path.

Do not copy the user's rough description directly into final `topic.yml` without refinement. Preserve it as `user_description_raw`, then write a cleaned `direction`, search terms, seed queries, and exclusions when available.

After successful initialization, immediately enter the new topic: read its `AGENTS.md`, `policy.yml`, `topic.yml`, and `preferences.yml`, then run `policy check` and `status`.

## Safety and Context

Do not read full `library.bib`, `candidates.jsonl`, or `papers/*` by default. Use CLI summaries first.

Do not bypass `paper_engine` for state changes unless a policy-approved direct write is required.

When implementing project code, keep public docs and topic files free of internal development-version labels. Users should see the product workflow, not the development folder history.
