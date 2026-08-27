# Paper simulation reproduction architecture

PaperEngine treats a simulation reproduction as a controlled five-stage
workflow, not as one long agent conversation:

```text
Paper snapshot
    ↓
Research Agent        evidence and missing-information audit
    ↓
Theory Agent          frozen equations, parameters, studies, acceptance
    ↓
Implementation Agent  solver-native translation, especially COMSOL
    ↓
Experiment Agent      immutable runs, controls, convergence, metrics
    ↓
Review Agent          independent verdict and targeted rework
```

One `ReproductionWorkflow` controller owns all state transitions. Agents never
edit another stage's outputs and cannot publish a result directly. A rejected
review identifies the earliest stage that needs repair; downstream artifacts
are moved into a cycle archive before the workflow resumes, preventing stale
models or metrics from leaking into a new attempt.

## Workspace contract

```text
<workspace>/
├── workflow.json                 # controller state and append-only history
├── source/
│   └── paper.pdf                 # immutable source snapshot with SHA256
├── stages/
│   ├── 01_research/
│   │   ├── task.md
│   │   ├── evidence_map.json
│   │   └── research_report.md
│   ├── 02_theory/
│   │   ├── task.md
│   │   ├── case.yml
│   │   └── equation_audit.md
│   ├── 03_implementation/
│   │   ├── task.md
│   │   ├── implementation_manifest.json
│   │   ├── comsol_handoff.md
│   │   └── <solver-native model files>
│   ├── 04_experiment/
│   │   ├── task.md
│   │   ├── run_manifest.json
│   │   └── metrics.json
│   └── 05_review/
│       ├── task.md
│       ├── review.json
│       └── review_report.md
├── archive/                      # rejected cycles, never silently reused
└── publication.json              # emitted only after accepted review
```

## Controller commands

Initialize a clean workspace and snapshot the source PDF:

```bash
paper_engine reproduce init \
  --workspace simulations/<case-id>/workflow \
  --case-id <case-id> \
  --title "<paper title>" \
  --paper paper/<paper.pdf>
```

For each stage, generate its bounded task, let the named agent write only the
declared outputs, then validate and advance:

```bash
paper_engine reproduce prepare --workspace <workspace>
paper_engine reproduce check-stage --workspace <workspace>
paper_engine reproduce submit --workspace <workspace>
paper_engine reproduce status --workspace <workspace>
```

`prepare` writes the active `task.md`; it does not launch an arbitrary agent or
grant access to unrelated project files. This lets the browser workbench,
Codex sessions, a batch runner, or a human operator use the same deterministic
controller.

## Stage boundaries

### Research

Extract source-addressable claims, equations, figures, parameters, and
ambiguities. Every evidence item needs a PDF page and source text. This stage
must not select discretizations or repair missing physics.

### Theory

Turn the evidence map into the frozen `case.yml`: fields, governing equations,
constitutive relations, units, initial/boundary conditions, studies, negative
controls, and quantitative acceptance criteria. `equation_audit.md` records
paper equation → cleaned equation → assumption → implementation requirement.

### Implementation and COMSOL

Translate the frozen theory without changing it. For COMSOL, the handoff must
state the physics interface, dependent-variable order, `ea`, `da`, conservative
flux `Γ`, source `f`, boundary `g/q/r`, variables, units, COMSOL version, mesh,
time stepping, studies, exports, and exact Java/API expressions. The manifest
lists every solver-native source or model file and maps paper equations to
their implementation locations.

### Experiment

Run the frozen model. Preserve model hashes, solver version, parameters, raw
outputs, logs, baseline, negative controls, parameter sweeps, mesh convergence,
and time-step convergence. Exploratory tuning must be labeled and cannot replace
the declared baseline.

#### Remote COMSOL Agent

PaperEngine provides one gateway-aware remote execution layer for all papers.
It supports password-authenticated SSH gateways that present an instance menu,
strict host-key checking, COMSOL environment loading, Slurm submission/status,
and fail-closed artifact verification. Paper-specific scripts contain only the
model, studies, exports, and resource request; they do not duplicate SSH logic.

Copy `templates/comsol_remote.example.json` to a private location and fill in
the non-secret gateway settings. Keep the password in a separate mode-0600 file
outside the repository. Passwords are never accepted in JSON or command output.

```bash
paper_engine reproduce comsol probe \
  --config ~/.paperengine/comsol_remote.json \
  --password-file ~/.paperengine/secrets/comsol_ssh_password

paper_engine reproduce comsol submit \
  --config ~/.paperengine/comsol_remote.json \
  --password-file ~/.paperengine/secrets/comsol_ssh_password \
  --remote-workdir '~/paperengine-runs/<case-id>' \
  --script run.slurm

paper_engine reproduce comsol status \
  --config ~/.paperengine/comsol_remote.json \
  --password-file ~/.paperengine/secrets/comsol_ssh_password \
  --job-id <job-id>
```

Submission always changes into `--remote-workdir` before calling `sbatch`, so
relative MPH inputs resolve deterministically. A Slurm `COMPLETED` state alone
is insufficient: `comsol verify` also requires nonempty logs and the declared
solver artifact, and rejects COMSOL errors or exceptions found in either log.

### Review

Review is independent of implementation. It checks paper fidelity, equation
mapping, numerical health, controls, convergence, and quantitative agreement.
An accepted decision is rejected automatically when any required `case.yml`
acceptance metric fails. A rejected decision must return to `research`,
`theory`, `implementation`, or `experiment` with concrete findings.

## Solver-run artifacts

The existing `RunArtifacts` contract remains the solver-run layer below the
workflow:

```text
<output-root>/<case-id>/<run-id>/
├── raw/
├── figures/
├── logs/
├── model/
└── reports/
```

Validate a case or completed metrics independently of the five-stage workflow:

```bash
paper_engine reproduce check-case path/to/case.yml
paper_engine reproduce init-run path/to/case.yml --output-root <runs>
paper_engine reproduce validate path/to/case.yml path/to/metrics.json \
  --report acceptance.md --json-report acceptance.json
```

The compatibility entry `python -m paper_engine.simulation_reproduction ...`
delegates to the same command implementation; it no longer contains a duplicate
CLI workflow.
