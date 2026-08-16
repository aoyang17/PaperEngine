---
name: reference_expansion
description: Use when the user asks to follow a paper's references, expand from a reference list, mine cited work, or batch collect papers from titles without adding new CLI commands.
---

# reference_expansion

Use this skill when the user asks to collect papers from an existing paper's references or from a list of paper titles.

## Inputs

Read only the named candidate or paper first. Do not read full `candidates.jsonl`, `library.bib`, or sibling topic folders.

Useful commands:

- `battery_lit candidates show --root <topic> CAND-ID --json`
- `battery_lit library find --root <topic> --query TEXT --json`
- `battery_lit status --root <topic> --json`

## Workflow: arXiv Reference Expansion

1. Save the named candidate to `reports/reference_expansion_<CAND-ID>_candidate.json` with `battery_lit candidates show --json`.
2. Extract reference titles:

```bash
python3 skills/reference_expansion/scripts/extract_arxiv_bib_titles.py \
  --candidate-json reports/reference_expansion_<CAND-ID>_candidate.json \
  --out reports/reference_titles_<CAND-ID>.tsv
```

3. Inspect the TSV and select only topic-relevant titles into `reports/selected_reference_titles_<CAND-ID>.txt`, one title per line. Prefer precision over volume. If the user gave hard constraints such as year, venue, field, or score threshold, apply them before title intake; rejected reference hits are not candidates.
4. Collect selected titles with the bundled helper:

```bash
python3 skills/literature_collect/scripts/collect_titles.py \
  --root <topic> \
  --titles-file reports/selected_reference_titles_<CAND-ID>.txt \
  --json
```

5. Run `battery_lit tool dedup --root <topic> --fix --json`.
6. If new candidates were added, follow `skills/candidate_scoring/SKILL.md` before reporting the expansion complete. Run a bounded `battery_lit candidates scoring-batch --status new --limit <added-count> --json`, write `reports/candidate_scores.jsonl`, and apply with `battery_lit candidates apply-scores --scores reports/candidate_scores.jsonl`. If scoring cannot complete, report the blocker and leave those candidates visibly unscored.

The extractor owns its temporary directory and cleans it automatically. Do not create fixed `/tmp/<task>` directories for arXiv source archives.

## Workflow: Title List

If the user gives paper titles directly, write them to `reports/title_intake_<short-name>.txt`, one title per line, then run `skills/literature_collect/scripts/collect_titles.py` as above.

If the title list came from a search preview, reference list, or another generated source, first filter it against the user's hard admission constraints. Only admitted titles should be passed to `collect_titles.py`; do not preserve rejected hits in `candidates.jsonl`.

After direct title-list intake adds candidates, run the same candidate-scoring step before screening or reporting ranked candidates.

## Blockers

Report a blocker instead of improvising if:

- the named paper has no arXiv ID/source archive and no user-provided title list
- the arXiv source has no `.bib` file with reference titles
- collection backend fails after one retry

## Output to User

Report how many reference titles were extracted, how many were selected, how many candidates were added after deduplication, whether scoring is complete, and the next screening step.
