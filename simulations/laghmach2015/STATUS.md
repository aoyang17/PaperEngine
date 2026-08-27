# Reproduction status

Status is deliberately evidence-based. A generated script is not counted as a
successful COMSOL result until compilation, solver completion, and acceptance
metrics are recorded.

| Gate | Current evidence | Status |
|---|---|---|
| Source/PDF identity | DOI and local publisher PDF verified | PASS |
| Equation transcription | Eqs. 1-30 mapped in `equation_audit.md`; implementation coverage explicit | PASS |
| Unit consistency | Molar `R`, `fscale=37.03 MJ/m3`, nm nondimensionalization | PASS |
| Generic case validation | 27 machine-readable criteria (22 required); missing metrics fail closed | PASS |
| Targeted module/case tests | `9 passed` | PASS |
| Reference solver core | `Rinf=23.008 nm`; Figure 6b NRMSE 6.06%; t95 error 8.09% | PASS |
| Mechanism cross-check | Topology-on saturates; topology-off reaches 48.66 nm and continues growing | PASS |
| Reference convergence | 0.5 nm radius difference 1.413%; half-step radius/t95 differences 0.0191%/0.0156% | PASS |
| Reference threshold sweep | `lambda_c={3,4,5}` at `{298,303,308} K` | PASS |
| Reference acceptance total | 17/22 required criteria pass; five full-mechanics/surface-fit gaps remain | PARTIAL |
| Reference nucleus-memory check | Rn=5/9 nm gamma-vs-displacement curve NRMSE 6.82% | PASS |
| Reference surface-energy fit | `A=7.81e-4`, `B=0.222`, `R2=0.841`; A passes, B and R2 fail | FAIL |
| COMSOL Java compilation | COMSOL 6.4 Build 293 compile + smoke passed; prodargs parameter injection audited | PASS |
| COMSOL segregated formulation | Automatic segregated sequence (phase/topology; mechanics/pressure) compiles and converges in 0.05τ₁ smoke run; MPH/CSV archived under `tmp/runs/comsol/laghmach2015/segsmoke` | PASS |
| COMSOL baseline solve | Full 1 nm/150τ₁ coupled runs fail at early nonlinear/DAE singularity; 5 nm prescribed-strain coarse MPH/CSV succeeds | PARTIAL |
| COMSOL grid/time convergence | Full coupled matrix failed before paired outputs; fine-grid run cancelled after prolonged Newton factorization | BLOCKED |
| COMSOL parameter sweep / surface fit | Full threshold/surface jobs fail early; stable coarse topology-on 0.2τ₁ result archived | PARTIAL |
| Anisotropic second stage | Equation is parameterized in source; not solved | NOT RUN |

Verified COMSOL artifacts are under `tmp/runs/comsol/laghmach2015/coarse*` and
`tmp/runs/comsol/laghmach2015/segsmoke`. The segregated sequence is now the
default solver formulation; long, fine-grid quantitative acceptance runs still
remain to be executed.
