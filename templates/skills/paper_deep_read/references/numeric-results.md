# Numeric Results

Use `evaluation.numeric_results` for numbers that materially affect the paper's claims.

Each item must include:

- `dataset_or_task`;
- `metric`;
- `value`;
- `unit`;
- `baseline`;
- `comparison`;
- `higher_is_better`;
- `source_refs`;
- `interpretation`;
- `what_it_does_not_prove`.

## Rules

- Only include numbers visible in source blocks or tables/figures you inspected.
- Do not include parser, page-rendering, source-map, token, artifact-count, or workflow metadata. Examples to exclude: parsed PDF pages, rendered pages, number of visual screenshots, validation counts, or file counts.
- Percent values must be in `[0, 100]`.
- If a result compares against a baseline, explain what the comparison means.
- Do not treat a single benchmark win as broad generalization; put limits in `what_it_does_not_prove`.
- If the paper has no trustworthy claim-bearing numeric result, leave the array empty and explain the reason in extraction notes. The HTML renderer hides an empty Numeric Results section.
