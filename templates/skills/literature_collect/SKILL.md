# literature_collect

Use this skill whenever the user asks to search, collect, add candidates, follow a venue, or find papers for the topic.

## Default Inputs

Read only:

- `topic.yml`
- `preferences.yml`
- recent `reports/last_collect.json` if it exists

Do not read full `library.bib` or `candidates.jsonl`. Use CLI summaries and built-in deduplication instead.

## Workflow

1. Run `paper_engine status --json` to understand current counts and health.
2. Select exactly one of the four `research_modules` for each search pass. Build one concise query from that module's `seed_queries`, required/positive concepts, exclusions, `preferences.yml`, and any explicit seed paper/title. Do not blend all four modules into one broad query.
3. Run `paper_engine collect --query "..." --target-new N` or `paper_engine tool search --query "..." --json` when the user only wants a preview.
4. Run `paper_engine tool dedup --fix --json` after adding candidates.
5. If new candidates were added, follow `skills/candidate_scoring/SKILL.md` before screening; unscored candidates have `score: 0` and are not yet ranked.
6. If the user asks for library overlap, use `paper_engine library find --json --query TEXT` rather than reading full BibTeX.
7. Write a short report under `reports/` only when the user asked for a durable summary or the search hit a blocker.

OpenAlex results are automatically treated as discovery/metadata hits, not final PDF evidence. When an OpenAlex result lacks `pdf_url` or arXiv ID, `paper_engine` tries a bounded Semantic Scholar lookup and fills only missing `pdf_url`, `arxiv_id`, `semantic_scholar_id`, abstract, and source evidence. If Semantic Scholar is unavailable or rate-limited, collection still succeeds and the report records the failed enrichment count.

## Batch Sidecar Acceleration

Sidecars may help with collection only before candidate admission:

- Good sidecar work: query variants, source-specific preview scans, exact-title lookup suggestions, and preview scoring notes.
- Bad sidecar work: writing `candidates.jsonl`, running `paper_engine collect` concurrently against the same topic, running `tool dedup --fix`, acquiring PDFs, or applying scores.
- The main worker must choose the admitted title list, run the collect/title-intake command, run dedup once, merge any score shards, and apply scores once.
- Sidecar preview artifacts must live under `.paper_engine/jobs/<job-id>/sidecars/` or `/tmp/paper-engine-sidecar-*` and be cleaned after the main worker consumes them.

## Constrained Collection

The candidate list is the admission gate, not a raw search log. If the user says "only", "must", "after 2025", "score > 0.1", "top venue", or gives any other hard admission constraint, do not run broad `paper_engine collect` and then leave rejected hits in candidates.

Use this workflow instead:

1. Run `paper_engine tool search --root <topic> --query "..." --json` to preview raw search hits.
2. Filter the preview in the current Codex turn using the user's hard constraints. Reject nonmatching years, venues, domains, or other explicit exclusions before candidate admission.
3. If the constraint includes a relevance score threshold, use `skills/candidate_scoring/SKILL.md` preview scoring and keep only records above the requested threshold.
4. Write the admitted titles only to `reports/selected_titles_<short-name>.txt`, one title per line.
5. Add only those admitted titles with `skills/literature_collect/scripts/collect_titles.py`, then run `paper_engine tool dedup --root <topic> --fix --json`.

Rejected preview hits must not be written to `candidates.jsonl`, marked dismissed, or shown in the All tab. Report only counts and short reasons for rejected preview hits unless the user asks for details.

For a `strict_scope` module, preview-filter results against every required concept group before admission. A generic silicon-carbon composite paper is not a match for the target-material module unless the available title/abstract supports the porous-carbon host, vapor-deposition process, and internal-pore/pore-wall deposition location.

## Preference-Aware Search

If `preferences.yml` has `like`, `dislike`, `query_hints`, or `exclude_hints`, use them before searching:

- `query_hints` can expand the query when they match the user's request.
- `exclude_hints` should be treated as directions to avoid in the query and screening.
- `like` and `dislike` help score and filter candidates; they are not hard constraints unless the user says so.
- If preferences look stale or empty after many labels, switch to `skills/preference_refresh/SKILL.md` before another broad collection.

## Exact Title Intake

If the user gives a specific paper title to add to the candidate queue, use an exact-title query:

```bash
paper_engine collect --root <topic> --query "\"<paper title>\"" --target-new 1
paper_engine tool dedup --root <topic> --fix --json
```

Exact-title candidates must be scored before reporting them as ready for screening. If the collect result added a candidate, follow `skills/candidate_scoring/SKILL.md`: run a small `paper_engine candidates scoring-batch --status new --limit 1 --json`, write `reports/candidate_scores.jsonl`, then apply with `paper_engine candidates apply-scores --scores reports/candidate_scores.jsonl`. If scoring fails, report the candidate as unscored rather than treating `score: 0` as a real relevance score.

Then inspect the new candidate with `paper_engine candidates list --json --status new --sort candidate_id --limit 10` or `paper_engine candidates show --json CAND-ID`. Do not write a custom one-off Python loop for a single title.

## Batch Title Intake

If the user gives multiple titles or another skill produces a title file, write one title per line to `reports/selected_titles_<short-name>.txt` and run:

```bash
python3 skills/literature_collect/scripts/collect_titles.py \
  --root <topic> \
  --titles-file reports/selected_titles_<short-name>.txt \
  --json
```

This helper calls existing `paper_engine collect` commands and then `paper_engine tool dedup`. It exists to avoid ad hoc shell/Python loops, not to replace the CLI.

Batch-title candidates must also be scored before screening. After the helper reports added candidates, follow `skills/candidate_scoring/SKILL.md` for the new/unscored queue and apply the scores. If scoring cannot complete, report the blocker and leave the candidates visibly unscored.

## Reference Lists

If the user asks to follow references, mine citations, or collect from a paper's bibliography, switch to `skills/reference_expansion/SKILL.md`.

## Output to User

Report the query, added count, skipped/duplicate count when available, whether scoring is complete, and the next recommended screening step. Do not paste full candidate JSON unless requested.
