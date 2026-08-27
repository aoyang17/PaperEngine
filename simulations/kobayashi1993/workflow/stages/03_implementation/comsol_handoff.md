# COMSOL 6.4 handoff — Kobayashi 1993

## Solver-native model

`comsol/Kobayashi1993.java` builds two scalar **General Form PDE** interfaces
with dependent-variable order `[p,T]`. It reads only the whitelisted values in
`case.properties` is parsed and whitelisted by the shell launcher, then passed
as COMSOL `-prodargs` key-value arguments. Java performs no arbitrary file
reads, so COMSOL's default file-system security policy remains enabled. The
class saves a pre-solve MPH, solves `std1`, exports global and raw field CSV
files, then saves the authoritative solved MPH.

The field export is a `301 x 301` regular grid with explicit time
interpolation. Production cases export only `t={0.2,0.8,1.4}` (or the subset
not exceeding the case final time); smoke exports its final time. This keeps
the raw evidence complete for Fig. 7 without multiplying it over every solver
output time. `fields_to_masks.py` accepts only a complete grid and explicit
time-labelled `p` columns, flips the increasing physical `y` axis into image
row order, and thresholds the documented `p=0.5` interface.

### Interface `gp`: paper equation (3)

| COMSOL coefficient | Java/API expression |
|---|---|
| `ea` | `0` |
| `da` | `tau` |
| `Gamma_x` | `GammaPx = nojac(epsilon*epsilonTheta)*py-nojac(epsilon^2)*px` |
| `Gamma_y` | `GammaPy = -nojac(epsilon*epsilonTheta)*px-nojac(epsilon^2)*py` |
| `f` | `phaseSource = p*(1-p)*(p-0.5+mT)+noiseAmp*p*(1-p)*chi` |
| boundary | default Zero Flux: `g=0`, `q=0`; no `h/r` |

`theta=atan2(-py,-px)`, `epsilon=epsbar*(1+delta*cos(jmode*(theta-theta0)))`,
`epsilonTheta=-epsbar*delta*jmode*sin(...)`, and
`mT=alpha/pi*atan(gamma*(Teq-T))`. `nojac` stabilizes only the Newton Jacobian
at zero phase gradient; the nonlinear residual is the exact paper flux.

### Interface `gT`: paper equation (5)

| COMSOL coefficient | Java/API expression |
|---|---|
| `ea` | `0` |
| `da` | `1` |
| `Gamma` | `(-D*Tx,-D*Ty)` with `D=1 L0^2/t0` |
| `f` | `Klatent*d(p,t)` |
| boundary | default Zero Flux (`adiabatic`): `g=0`, `q=0`; no `h/r` |

The global export contains `intop1(T-Klatent*p)` for the adiabatic enthalpy
invariant, tip/width measures, extrema, and the run-defining parameters.

## Units and geometry

The paper is nondimensional. COMSOL requires consistent dimensions, so one
COMSOL `m` represents one computational `L0` and one `s` represents one `t0`.
No statement in the report may interpret the 9 m model geometry as a physical
nine-metre crystal.

The default smoke run uses `h=0.06`, `tfinal=0.002`; production reproduces the
paper `h=0.03`, `maxStep=0.0002`, `tfinal=1.4`. The fine grid is `h=0.02` and
the fine time step is `0.0001`.

## Remote sequence

1. Verify the gateway fingerprint and run `paper_engine reproduce comsol probe`.
2. Upload the complete `comsol/` directory to a fresh remote case root.
3. Submit only `cases/smoke.properties` first with `submit_cases.sh`.
4. Require COMSOL compilation success, `COMPLETED|0:0`, clean logs, nonempty
   `smoke_solved.mph`, and both CSV exports.
5. Submit the delta, control, grid, time-step, and seed cases only after smoke.
6. Download the entire immutable suite and calculate SHA256 locally.
7. Run `fields_to_masks.py`, then `compare_fig7_masks.py`, only on the
   downloaded solver exports. Never use source masks as simulated masks.

Example on the remote instance:

```bash
remote_root="$HOME/paperengine_runs/kobayashi1993"
bash submit_cases.sh "$remote_root" cases/smoke.properties
```

Production cases are submitted by explicitly listing property files; no glob
is used as the authority. Each run directory contains source, properties,
Slurm logs, COMSOL batch log, built/solved MPH, raw/global CSV, and SHA256
manifest.

## Known limitations before remote compile

- The Java API property names are based on the COMSOL 6.4 General Form PDE API
  (`gfeq1`, `Ga`, `ea`, `da`, `f`) and still require authoritative compilation.
- The Data export properties (`innerinput=interp`, `t`, `location=regulargrid`)
  still require the same authoritative COMSOL 6.4 compile-and-smoke gate.
- The hash-noise residual is reproducible and bounded but cannot reconstruct
  the paper's unreported 1993 random sequence.
- Source-figure comparison and postprocessing are Experiment outputs and are
  not yet evidence of a successful solve.
