# candidate_scoring

Use this skill whenever the user asks to score, rank, prioritize, or filter candidates by topic relevance.

## Inputs

Read only:

- `topic.yml`
- `preferences.yml`
- candidate batches from `paper_engine candidates scoring-batch --json`

Do not read full `candidates.jsonl`, `library.bib`, or paper directories.

## Rubric

Classification always comes before relevance scoring. Read the four `research_modules` in `topic.yml`, then:

1. Estimate a `module_score` in `[0, 1]` for every plausible module.
2. Assign a module only when its score is at least `0.45` and the title/abstract contains concrete supporting evidence.
3. For a module with `strict_scope: true`, all `required_concepts` groups must be supported. Related silicon-carbon work that lacks the specified host, process, or deposition location must not be assigned to that module.
4. Set `primary_module_id` to the strongest assigned module. Assign multiple modules when independently supported; the controller records such papers as cross-module.
5. A paper outside all four modules gets empty `module_ids` and should normally receive a negative relevance score.

Do not force every paper into a module. Record short quoted or closely paraphrased `scope_evidence` from the title/abstract; do not invent evidence.

Score each candidate for topic relevance in `[-1, 1]`. A score of `0` is the default admission threshold.

- `content` in `[-0.70, 0.70]`: use title and abstract. Directly addresses the topic: positive. Broadly adjacent: small positive. Off-topic or excluded direction: negative.
- `preference` in `[-0.15, 0.15]`: use explicit positive and negative preferences from `topic.yml` and `preferences.yml`.
- `credibility` in `[-0.15, 0.15]`: use venue and authors only as a small tie-breaker. Strong or field-relevant venue may get a small boost. arXiv is neutral by default. Penalize only clearly low-quality, predatory, or unreliable venues.

Do not use DOI, PDF URL, publication year, search backend, or retrieval source as scoring factors.

## Workflow

1. Run `paper_engine candidates scoring-batch --root <topic> --status new --limit 20 --json`.
2. Classify each candidate into zero or more research modules, then score it using the rubric above. If uncertain, use `score_confidence: "low"` and keep the score near zero.
3. Write JSONL to `reports/candidate_scores.jsonl`, one candidate per line.
4. Apply the scores with `paper_engine candidates apply-scores --root <topic> --scores reports/candidate_scores.jsonl`.
5. Inspect ranked candidates with `paper_engine candidates list --root <topic> --status new --sort score --min-score 0 --json`.

## Batch Sidecar Acceleration

For large scoring batches, sidecars may speed up the judgment step only. The main Codex worker still owns validation and the single `apply-scores` mutation.

- Use sidecars only for independent candidate-score shards.
- Each sidecar writes a job-local shard such as `.paper_engine/jobs/<job-id>/sidecars/score_shard_01.jsonl` or a temporary `/tmp/paper-engine-sidecar-*` artifact.
- Sidecars must not run `paper_engine candidates apply-scores`, edit `candidates.jsonl`, edit `preferences.yml`, or mutate the topic.
- Merge shards with project validation before applying. Reject malformed JSONL, duplicate score identities, scores outside `[-1, 1]`, and missing `candidate_id`.
- Apply the merged score file once from the main worker.
- Remove temporary sidecar directories after the merge unless the user explicitly asks to keep them for debugging.

## Preview Scoring Before Admission

When `skills/literature_collect/SKILL.md` asks for score-gated collection, score raw `paper_engine tool search --json` preview results in the current Codex turn before they become candidates. Use the same rubric, but do not call `paper_engine candidates apply-scores` because these records are not in `candidates.jsonl` yet.

Keep only preview results that satisfy the requested score threshold, then pass their titles to the literature collection title-intake workflow. Preview results below threshold are search hits, not candidates; do not mark them dismissed or write them to `candidates.jsonl`.

## JSONL Output

Each line must include classification and scoring:

```json
{"candidate_id":"CAND-001","module_ids":["cvd_porous_carbon_silicon"],"primary_module_id":"cvd_porous_carbon_silicon","module_scores":{"cvd_porous_carbon_silicon":0.92},"module_reasons":{"cvd_porous_carbon_silicon":["Uses silane CVD to deposit silicon inside a porous-carbon host."]},"scope_evidence":["silane CVD","silicon deposited inside porous carbon"],"content":0.65,"preference":0.08,"credibility":0.02,"score":0.75,"score_confidence":"high","reasons":["Directly satisfies the strict target-material definition."],"scored_by":"codex"}
```

The final `score` must equal the intended overall judgment and stay within `[-1, 1]`.

## Output to User

Report how many candidates were scored, how many are above `0`, and the top few candidates with short reasons.
