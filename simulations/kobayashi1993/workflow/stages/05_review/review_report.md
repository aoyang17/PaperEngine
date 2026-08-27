# Independent Review — Kobayashi (1993) COMSOL reproduction

## Verdict

**Accepted.** The evidence chain is internally consistent, the COMSOL equation
translation is executable rather than symbolic-only, all declared runs finished
successfully, and all 12 frozen acceptance criteria pass.

## Fidelity and implementation audit

- The frozen paper snapshot has SHA256
  `51f551671c05a7003c20032e97e3864f55d5448505857f7f15f46cfdc0bc5a5f`.
- Paper equations (3) and (5) are represented as two scalar COMSOL General Form
  PDE interfaces in fixed dependent-variable order `[p,T]`.
- For `p`, `ea=0`, `da=tau`,
  `Gamma=(epsilon*epsilon_theta*p_y-epsilon^2*p_x,
  -epsilon*epsilon_theta*p_x-epsilon^2*p_y)`, and
  `f=p(1-p)(p-0.5+m(T))+a*p(1-p)*chi`.
- For `T`, `ea=0`, `da=1`, `Gamma=(-D*T_x,-D*T_y)`, and
  `f=K*d(p,t)`. Both equations use `g=q=0`, with no `h/r`, giving natural
  zero flux; this is adiabatic for Fig. 7.
- `nojac` is confined to the Newton linearization of orientation-dependent
  coefficients and does not alter the residual equation.

## Execution and numerical health

The run manifest contains 11/11 completed COMSOL Multiphysics 6.4 Build 293
runs: the five-value anisotropy sweep, two deterministic controls, mesh and
time-step refinement, and two seed-radius perturbations. Every run records
`COMPLETED|0:0`; the archived logs contain no detected COMSOL error. The final
`delta020_solved.mph` is 1,659,129,698 bytes and its local SHA256 exactly equals
the remote manifest value
`1954c1bcd4039b2d7268c55947d126654b32cd30bb2248c7844090ae0ee703fa`.

All 12 required gates pass. The principal quantitative results are:

| Audit quantity | Result | Gate |
|---|---:|---:|
| Fig. 7 mean silhouette IoU | 0.3283 | >= 0.25 |
| Fig. 7 normalized contour Chamfer | 0.02620 | <= 0.10 |
| delta=0.05 / delta=0 tip ratio | 1.8509 | > 1.02 |
| delta=0.05 vertical/horizontal extent | 2.0135 | > 1.10 |
| mesh tip relative difference | 0.00354 | <= 0.05 |
| time-step tip relative difference | 0.00000 | <= 0.05 |
| seed-radius tip relative range | 0.00211 | <= 0.15 |
| maximum relative enthalpy drift | 2.09e-13 | <= 0.01 |

## Limits on the claim

The paper omits nucleus radius, random seed, and noise-update cadence. The
baseline `R0=0.15`, deterministic hash noise, and computational `L0/t0` units
are disclosed reproduction choices; radius sensitivity and noise-free controls
bound their effect. The paper itself characterizes its mesh/time-step results
as qualitative, so acceptance supports the reported anisotropy-driven trend
and morphology class, not exact pixel identity or physical-SI calibration.
Some individual silhouettes are weaker than the aggregate, while the frozen
criterion is the mean across Fig. 7. The exactly zero time-step tip difference
is also quantized by the threshold-based tip metric and should not be read as
proof that the full fields are identical.

No rework is required for the stated qualitative reproduction scope.
