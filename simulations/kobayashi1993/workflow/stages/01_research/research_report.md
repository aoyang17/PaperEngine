# Research report — Kobayashi 1993

## Scope and decisive evidence

The reproduction authority is the coupled two-dimensional phase-field/heat
system in paper equations (3) and (5), not the sharp-interface limit. The phase
field uses the orientation-dependent interface width
`epsilon(theta)=epsilon_bar[1+delta*cos(j*(theta-theta0))]`, while latent heat
enters the temperature equation as `K*pt`. For the target Fig. 7, the paper
fixes `K=2`, `j=4`, `theta0=0`, `epsilon_bar=0.01`, `tau=0.0003`, `alpha=0.9`,
`gamma=10`, domain `9x9`, paper mesh `300x300`, and paper time step `0.0002`;
it scans `delta={0,0.005,0.01,0.02,0.05}` and reports shapes at
`t={0.2,0.8,1.4}`.

The paper's conclusion relevant to Fig. 7 is qualitative: increasing `delta`
raises the principal-branch velocity and changes the branch structure sharply.
It also states that the original discretization suppresses features comparable
to the diffuse-interface thickness and was not fine enough for quantitatively
precise interfacial velocity. Pixel-level matching is therefore not a defensible
acceptance target.

## Initial and boundary conditions

Fig. 7 begins with uniformly supercooled melt (`T=0`) and nucleation at the
center of the bottom edge, followed by adiabatic growth. The phase field is
`p=0` in liquid and near `p=1` in the nucleus. Natural zero flux is explicit for
`p` and inferred for `T` from “adiabatic condition.”

## Missing information that must remain visible

- The nucleus radius/profile is not reported. A smooth semicircle and a seed
  sensitivity study are required.
- The random seed and update cadence are not reported. A deterministic baseline
  plus a documented reproducible pseudo-random perturbation are required.
- The paper does not provide digitized coordinates or scalar morphology
  metrics. Acceptance must combine source-figure masks/contours with robust
  topology and growth metrics, not invented numerical precision.

The full source-addressable record is in `evidence_map.json`; extracted page
text is retained under `pdf_extract/` for audit only.
