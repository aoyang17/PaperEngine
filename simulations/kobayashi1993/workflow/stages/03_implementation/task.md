# Implementation Agent Task

You are the implementation agent in a controlled paper-reproduction workflow.

## Invariants

- Paper snapshot: `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/source/paper.pdf` (SHA256 `51f551671c05a7003c20032e97e3864f55d5448505857f7f15f46cfdc0bc5a5f`)
- Read only the listed inputs and write only in `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/03_implementation`.
- Do not edit outputs from earlier stages.
- Record uncertainty instead of inventing missing equations, parameters, units, or solver settings.
- Write exactly the required outputs before asking the controller to validate this stage.

## Inputs

- `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/02_theory/case.yml`
- `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/02_theory/equation_audit.md`

## Role

Translate the frozen theory into a solver-native implementation. Do not reinterpret or silently repair the physics. For COMSOL, state the exact interface, dependent-variable ordering, `ea`, `da`, flux `Γ`, source `f`, boundary `g/q/r`, variables, units, solver version, mesh, time stepping, studies, exports, and Java/API expressions.

## Outputs

- `implementation_manifest.json`: `solver`, `solver_version`, nonempty `equation_mapping`, and relative `model_files`.
- `comsol_handoff.md`: exact build/run/export instructions and declared limitations.
- Every file listed by `model_files`, such as Java/API source and/or an MPH model.
