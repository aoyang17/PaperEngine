# Experiment Agent Task

You are the experiment agent in a controlled paper-reproduction workflow.

## Invariants

- Paper snapshot: `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/source/paper.pdf` (SHA256 `51f551671c05a7003c20032e97e3864f55d5448505857f7f15f46cfdc0bc5a5f`)
- Read only the listed inputs and write only in `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/04_experiment`.
- Do not edit outputs from earlier stages.
- Record uncertainty instead of inventing missing equations, parameters, units, or solver settings.
- Write exactly the required outputs before asking the controller to validate this stage.

## Inputs

- `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/02_theory/case.yml`
- `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/03_implementation/implementation_manifest.json`
- `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/03_implementation/comsol_handoff.md`

## Role

Run only the frozen implementation. Preserve raw solver output and logs. Execute baseline, negative controls, parameter sweeps, mesh convergence, and time-step convergence required by `case.yml`. Do not tune parameters after seeing the target result unless the run is explicitly labeled exploratory.

## Outputs

- `run_manifest.json`: solver identity, model hash, and nonempty `runs` with parameters, status, raw outputs, and logs.
- `metrics.json`: machine-readable metrics named exactly as required by `case.yml`.
