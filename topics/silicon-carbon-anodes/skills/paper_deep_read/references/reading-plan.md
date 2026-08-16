# Reading Plan

Write `note_plan.json` before `deep_read.json`.

The plan is a compact contract for what the final note must explain. It prevents the reading from becoming a generic summary.

## Required Fields

- `schema_version`: use `v3-note-plan-2026-06`.
- `primary_type`: one of the paper types.
- `active_lenses`: one or more paper types, including `primary_type`.
- `type_rationale`: why the type/lenses fit the paper.
- `must_cover`: essential mechanisms, claims, datasets, experiments, caveats, or definitions.
- `key_numbers`: metrics, dataset statistics, complexity numbers, or important counts to extract.
- `central_claims`: claims the final note must evaluate.
- `claim_boundaries`: what the paper does not prove.
- `mechanism_result_map`: how mechanism, theory, dataset, or system details connect to results.
- `comparative_positioning`: how the paper positions against prior methods, baselines, or taxonomies.
- `negative_or_limiting_results`: failures, weak results, limitations, or narrow assumptions.
- `visual_plan`: figures/tables/algorithms that should appear in the final note.
- `section_plan`: the intended final note structure.

Keep each list short and concrete. Do not write a second abstract.
