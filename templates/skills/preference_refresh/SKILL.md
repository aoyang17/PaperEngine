# preference_refresh

Use this skill when the user asks to update, refresh, synthesize, or rebuild topic preferences from candidate feedback.

## Goal

Convert existing candidate labels into a small `preferences.yml` memory that improves the next search and candidate scoring. This is an LLM synthesis task, not a rule-based keyword extractor.

## Inputs

Read only:

- `topic.yml`
- `preferences.yml`
- bounded candidate batches from `battery_lit candidates list --json`

Do not read PDFs, `library.bib`, paper directories, deep-read JSON, parsed text, sibling topics, or the full `candidates.jsonl`.

## Workflow

1. Run `battery_lit preferences check --root <topic> --json`.
2. Collect at most 40 labeled candidates using CLI summaries:
   - `battery_lit candidates list --root <topic> --status relevant --sort score --limit 25 --json`
   - `battery_lit candidates list --root <topic> --status irrelevant --sort score --limit 25 --json`
3. Use only the candidate title, abstract, venue, year, score, decision, and score reasons as evidence.
4. Rewrite `preferences.yml` directly with this compact shape:

```yaml
schema_version: v2
effective_feedbacks: <existing count>
evidence_count: <number of relevant/irrelevant candidates used>
like:
  - short supported preference
dislike:
  - short supported negative preference
query_hints:
  - concise search phrase
exclude_hints:
  - concise exclusion phrase
rationale: >
  One short explanation of what the labels imply.
updated_at: "<current UTC timestamp>"
```

5. Keep each list short: 3-8 items is enough. Do not include unsupported guesses.
6. Run `battery_lit preferences check --root <topic> --json` and `battery_lit status --root <topic> --json`.

## Evidence Rules

- Every `like`, `dislike`, `query_hints`, and `exclude_hints` item must be supported by at least one labeled candidate.
- `relevant` candidates are positive evidence.
- `irrelevant` candidates are negative evidence.
- `dismissed` candidates are not semantic preference evidence by default.
- `none` candidates are not preference evidence.
- Do not invent venues, authors, fields, paper claims, or user preferences from model memory.
- Do not update `topic.yml`; it is the stable research direction.

## Output to User

Report the number of labeled candidates used, the main positive and negative preferences, whether `preferences.yml` passed validation, and how these preferences should affect the next search.
