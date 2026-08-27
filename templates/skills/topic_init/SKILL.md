# topic_init

Use this skill to initialize or refine a literature topic. The goal is to turn a rough user intent into a concise, searchable topic definition.

## Do Not Explore Before Init

First contact rule: when initializing a topic from the repository root, use `bin/paper_engine init` directly. Do not search for local examples or similar topics first.

Ordinary init does not require confirming conventions from local folders. Do not run `ls <base-dir>`, do not run `find .agents .codex`, and do not read sibling topics, old outputs, hidden directories, or local agent configuration.

If title or direction is missing, ask the user directly. Do not infer missing inputs from the filesystem.

## Required User Inputs

Ask only for missing information:

1. title
2. one-sentence, one-paragraph, or keyword description of the research direction
3. optional seed papers

Do not require the user to prepare YAML. Do not call `paper_engine init` with missing title or direction.

## Topic Folder Name

If the user provides a base directory but not a full topic root, derive the folder name from the title with `paper_engine init --base-dir <base> --title "<title>"`. The CLI slugifies the title: lowercase ASCII, spaces and special characters become `-`, and path-unsafe punctuation is removed. Do not use the raw title as a folder name.

## Clean-room Init Boundary

Treat the base directory as a parent directory only. Do not list, search, read, summarize, copy, or use sibling folders under the base directory as examples or templates.

Allowed context during ordinary init:

- this project guide and this skill
- built-in `templates/topic_repo/` and `templates/skills/`
- user-provided title, direction, and seed papers
- optional external paper search previews
- the target topic root, only for the minimum existence/non-empty check

Forbidden context during ordinary init:

- sibling paths under the base directory, regardless of name
- existing topic repositories or old outputs
- `.agents`, `.codex`, hidden directories, and local agent configuration
- other local project directories

Do not initialize a topic by imitating another topic under any parent directory.

If the target topic root already exists and is non-empty, stop and ask the user whether to enter that topic or choose a new root. Do not inspect existing files to learn their format.

Only read an existing external topic during init if the user explicitly asks to migrate, copy, compare, or reference a specific path.

## Refinement

Do not copy the user's rough description directly into final `direction`.

Preserve the raw wording as `user_description_raw`, then write a cleaned topic definition:

- concise `direction`
- `follow.keywords`
- `search.positive_terms`
- `search.negative_terms`
- `search.seed_queries`
- `search.exclude_terms`

Use the style of the superpowers brainstorming pattern: clarify intent before committing the final definition.

## Optional Search Preview

If the backend is available and the user is not blocked on speed, run one or two small previews with `paper_engine tool search --query "..." --json` using 5-10 likely results per query. Use the result titles/venues to calibrate the topic, not to fill the library.

Search previews may include Semantic Scholar PDF/arXiv completion for OpenAlex hits. Use those signals only to judge whether the topic is collectable; do not admit preview records into the queue during init.

If search preview fails, report the blocker and continue from the user's description.

## Refinement Questions

Ask 2-4 short multiple-choice or compact questions when the scope is broad. Prefer questions that affect search:

- include or exclude adjacent areas
- prioritize theory, systems, benchmarks, or applications
- include or exclude software engineering agents
- year recency preference
- venue or author follows

Record answered refinements in `topic.yml` under `refinement_questions_answered`.

## After Init

Run `paper_engine init`, then immediately enter the new topic with `skills/topic_enter/SKILL.md`: read `AGENTS.md`, `policy.yml`, `topic.yml`, and `preferences.yml`, then run policy check and status.
