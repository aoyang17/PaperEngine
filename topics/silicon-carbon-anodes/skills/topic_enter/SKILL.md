# topic_enter

Use this skill whenever the user asks to enter, resume, continue, inspect, or work in this PaperEngine topic.

## Context Budget

Read only these files first:

- `AGENTS.md`
- `policy.yml`
- `topic.yml`
- `preferences.yml`

Do not read full `library.bib`, `candidates.jsonl`, `papers/*/parsed.md`, `papers/*/deep_read.json`, or PDFs by default.

## Workflow

1. Confirm the given root is a topic by checking `AGENTS.md`, `policy.yml`, and `topic.yml`.
2. Run `paper_engine policy check --root <topic> --json`.
3. Run `paper_engine status --root <topic> --json`.
4. Use `paper_engine library list --root <topic> --json --limit 20` only if the user asks about existing library contents.
5. If status reports unscored candidates and the user wants screening or ranking, follow `skills/candidate_scoring/SKILL.md`.
6. Use `paper_engine candidates list --root <topic> --json --status new --sort score --min-score 0` only if the user asks to screen candidates.

## Output

Report the topic title, policy health, status counts including unscored candidates, blockers, and the most natural next actions: collect, score, screen, acquire, read, or digest.
