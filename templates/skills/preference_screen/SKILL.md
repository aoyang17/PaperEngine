# preference_screen

Use this skill whenever the user asks to screen, rank, label, archive, or review candidates.

## Context Budget

Do not read full `candidates.jsonl`. Use:

- `battery_lit candidates list --json --status new`
- `battery_lit candidates list --json --status new --sort score --min-score 0`
- `battery_lit candidates list --json --status relevant`
- `battery_lit candidates list --json --status irrelevant`

Show candidates in batches of five unless the user asks for another number.

## Workflow

1. If new candidates are unscored, follow `skills/candidate_scoring/SKILL.md` before asking the user to screen them.
2. Show title, year, venue, authors, score, source, score reasons, and a concise abstract summary.
3. Ask the user to mark each visible candidate as relevant, irrelevant, none, or dismissed.
4. Apply labels with `battery_lit candidates mark` or `battery_lit candidates dismiss`.
5. Before the topic has at least 10 library papers or effective feedback labels, prefer human labels.
6. After enough feedback, auto-label only obvious low-risk items and explain why.
7. If the user asks to refresh preferences, or if 10-20 effective relevant/irrelevant labels have accumulated, switch to `skills/preference_refresh/SKILL.md`. Do not update `preferences.yml` after every click.

## Output to User

Report label counts, candidates needing a decision, and whether preferences were updated.
