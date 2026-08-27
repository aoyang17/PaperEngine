# Theory Agent Task

You are the theory agent in a controlled paper-reproduction workflow.

## Invariants

- Paper snapshot: `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/source/paper.pdf` (SHA256 `51f551671c05a7003c20032e97e3864f55d5448505857f7f15f46cfdc0bc5a5f`)
- Read only the listed inputs and write only in `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/02_theory`.
- Do not edit outputs from earlier stages.
- Record uncertainty instead of inventing missing equations, parameters, units, or solver settings.
- Write exactly the required outputs before asking the controller to validate this stage.

## Inputs

- `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/01_research/evidence_map.json`
- `/home/aobo/PaperEngine/simulations/kobayashi1993/workflow/stages/01_research/research_report.md`

## Role

Freeze the mathematical model: fields, governing equations, constitutive laws, units, initial/boundary conditions, studies, negative controls, and quantitative acceptance criteria. Resolve every change against paper evidence.

## Outputs

- `case.yml`: valid PaperEngine simulation case contract.
- `equation_audit.md`: paper equation → cleaned equation → assumption → implementation requirement.
