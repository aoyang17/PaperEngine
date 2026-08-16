# Paper Type Contracts

Choose one primary type and any useful active lenses. The primary type is the main route. Active lenses add extra sections for mixed papers.

## `method`

Required section: `method_understanding`.

Cover:

- mechanism pipeline;
- input/output and training/inference flow;
- pseudocode when the paper has an algorithmic procedure;
- implementation details;
- how the mechanism explains the reported results.

## `theory`

Required section: `theory_understanding`.

Fields:

- `problem_formulation`;
- `key_equations`;
- `theorem_or_principle_chain`;
- `assumptions`;
- `key_results`;
- `engineering_proof_sketch`;
- `limitations`.

Extract cleaned equations from parsed text when it preserves enough signal. If parser quality is poor, use `math_index.json` and the listed `math_pages` images as the current Codex session's vision fallback before giving up. A key equation item should name the equation, preserve a readable multiline formula or symbolic relation, explain what each term is doing at a high level, and cite source refs. Explain derivations in engineering language: what is assumed, what is transformed, why the result follows, and when it stops applying.

## `dataset_benchmark`

Required section: `dataset_benchmark_understanding`.

New reports must use `format: "structured_v2"` with these fields:

- `key_numbers`: one row per dataset fact with `label`, `value`, optional `unit`, `context`, and `source_refs`;
- `construction_steps`: ordered rows with `stage`, `action`, `output`, optional `quality_control`, and `source_refs`;
- `biases_or_limits`.

`key_numbers` is a dataset-at-a-glance table, not an experiment-results dump. Prefer facts that describe the released corpus itself: sample/case count, geometry or subject count, train/validation/test split, modalities, parameter ranges, mesh or resolution scale, storage size, labels/targets, and coverage. Put model accuracy, solver speedups, and downstream benchmark scores in `evaluation`, not in this table.

`construction_steps` must reconstruct how the dataset was made in causal order, for example geometry/source acquisition -> parameter sampling -> simulation or measurement -> post-processing/labeling -> quality control -> split/package/release. Name the actual tools, solvers, governing setup, filtering checks, and produced artifacts when the paper provides them. Do not replace the pipeline with generic phrases such as "data were generated and validated".

Use the top-level `availability` section for code/data links and access status; do not duplicate those prose blocks inside the dataset section. Every structured row must cite paper-specific `source_refs`. If the paper does not report a desired statistic or construction stage, omit that row and record the concrete gap in `extraction_notes` rather than inventing it.

## `survey`

Required section: `survey_understanding`.

Fields:

- `scope`;
- `taxonomy`;
- `method_family_matrix`;
- `timeline_milestones`;
- `coverage_gaps`.

The method-family matrix should compare at least three families when the paper covers them: core idea, strengths, limitations, and best use case. For timeline items, identify milestone papers or method families when the survey provides them. Do not invent missing history; if the paper gives no timeline, say so in extraction notes.

## `application`

Required section: `application_understanding`.

Fields:

- `task_context`;
- `experimental_setup`;
- `constraints`;
- `transfer_limits`.

Focus on what scientific/engineering task is being solved, what assumptions make the application valid, and what does not transfer.

## `system_tooling`

Required section: `system_understanding`.

Fields:

- `architecture`;
- `interfaces`;
- `workflow`;
- `failure_modes`.

Include reproducible operation steps only when the paper gives enough detail.
