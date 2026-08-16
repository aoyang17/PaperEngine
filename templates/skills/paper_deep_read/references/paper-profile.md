# Paper Profile

Classify the paper by narrative role, not by venue. Choose one `primary_type` and any useful `active_lenses`.

## Primary Types

- `method`: new algorithm, model, inference procedure, training objective, or system mechanism.
- `theory`: theorem, proof, derivation, formal guarantee, or mathematical analysis is central.
- `dataset_benchmark`: dataset, benchmark, evaluation protocol, or leaderboard is the main contribution.
- `survey`: review, taxonomy, tutorial, roadmap, or position synthesis.
- `application`: empirical use of known methods in a science or engineering domain.
- `system_tooling`: software, workflow, infrastructure, or engineering tool.

## Lens Rules

A paper may activate multiple lenses. For example, use `method` plus `application` for an algorithm validated in a concrete engineering domain, or `method` plus `theory` when a new algorithm depends on a derivation.

Do not force every paper into a model-architecture format. Dataset papers need data construction and validity; survey papers need scope, taxonomy, and milestones; theory papers need assumptions and proof intuition.

`paper_profile.rationale` should explain why the selected profile follows from source blocks, but the actual source refs live in `argument_map` and evidence-bearing report fields.
