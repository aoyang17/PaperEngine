# literature_digest

Use this skill whenever the user asks for a summary, progress report, map of the knowledge base, or gaps in the topic.

## Context Budget

Do not read full `library.bib`, full `candidates.jsonl`, or every paper note by default.

Start with:

- `battery_lit status --json`
- `battery_lit library list --json --limit 50`
- `battery_lit candidates list --json --status new`
- recent small files under `reports/`

Read `papers/<bibkey>/note.md` only for papers needed by the user's question. Use `battery_lit library find --json --query TEXT` to narrow the set first.

## Output

Separate established facts from open questions. Include counts, strongest covered themes, missing venues/topics, and concrete next collection or reading steps.
