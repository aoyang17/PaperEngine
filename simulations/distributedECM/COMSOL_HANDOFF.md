# distributedECM COMSOL handoff

## Active model

`distributeECM.java` builds a reduced distributed equivalent-circuit model.
The electrochemical layer is the planar interface (boundary 9). A Boundary
ODE advances its local dimensionless state `SOCb`, while Electric Currents
solves the three-dimensional aluminum and copper current collectors.

The interface is coupled through a stable Robin current-voltage relation:

`ec.nJ = (V1-linext2(V1)-OCV)/R_area`

`R_area` combines the prescribed spatial ohmic factor with the activation
resistance linearized at the 1C operating point. `OCV=int1(SOCb)`. The reduced
model sets concentration overpotential to zero; it does not solve particle
diffusion. Legacy extra-dimension geometry declarations remain inert and are
not included in the active physics.

The heterogeneous case uses `R_factor=1+hetero_amp*int2(y)`. With
`hetero_amp=0.8`, the factor varies linearly from 0.2 to 1.8 across the layer.
The uniform case uses `hetero_amp=0`.

## Reproduction

Run through PaperEngine's COMSOL remote workflow. The Slurm scripts compile
the Java source with COMSOL 6.4, solve each properties file, export CSV data,
save built and solved MPH files, and write SHA-256 manifests.

- `comsol_smoke.slurm`: short heterogeneous smoke test.
- `comsol_suite.slurm`: final uniform and heterogeneous comparison.
- `run_suite.sh`: deterministic compile/run/export wrapper.
- `cases/*.properties`: solver and case parameters.

The final comparison horizon is 500 s. A diagnostic 1200 s run converged
numerically but was rejected because the strong heterogeneity drove local SOC
outside the OCV interpolation range after roughly 600 s.

## Outputs

Each final case directory contains its configuration, built and solved MPH
models, COMSOL batch log, global time-series CSV, boundary-field CSV, and a
SHA-256 manifest. The global export includes applied and integrated current,
local C-rate statistics, current coefficient of variation, impedance range,
terminal and layer voltage, and boundary SOC statistics.

Run `postprocess.py` to create the JSON/Markdown summary and two SVG figures.
