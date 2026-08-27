# Paper-equation audit

This audit maps every numbered equation needed for the reproduction to its
role in the model.  The transcription was checked against the publisher PDF
`paper/laghmach2015.pdf`, not only against extracted text.  Symbols follow the
paper; the implementation uses molar `R` wherever the paper's tabulated molar
parameters make the printed `k_B` notation dimensionally inconsistent.

## Thermodynamics and phase field

| Eq. | Paper content | Reproduction use | Implementation / status |
|---:|---|---|---|
| 1 | `Delta G_melt = nu[n h_m(Tm0-T)/Tm0 + k_B T(lambda^2/2 + 1/lambda - 3/2)]` | Macroscopic 3D Flory reference | Audit/reference only; the 2D calculation uses local Eq. 2. |
| 2 | `Delta G_melt = nu[n h_m(Tm0-T)/Tm0 + k_B T Tr(E)]`, `E=(F^T F-I)/2` | Local strain-dependent bulk driving force | `trE` and `drive` in `Laghmach2015.java`; reduced solver substitutes the prescribed homogeneous 2D stretch. |
| 3 | `f_bulk(1)=0`, `f_bulk(0)=Delta G_melt` | Fixes crystal and amorphous well depths | Enforced by Eq. 4 interpolation. |
| 4 | `f_bulk = Gamma theta^2(1-theta)^2/4 + g(theta) Delta G_melt`, `g=1-theta^2(3-2theta)` | Double well and thermodynamic coupling | `g`, `gp`, `drive`; also used for the Stage-0 free-energy plot. |
| 5 | `F = integral[f_bulk + Gamma w^2 |grad theta|^2/2] dV` | Variational source for Allen-Cahn dynamics | Gradient and bulk terms in Weak Form PDE `pf`. |
| 6 | `F_ij = partial u_i/partial X_j + delta_ij` | Reference-to-current deformation gradient | Evaluated through the Eulerian identities in Eqs. 18-19. |
| 7 | `gamma = w integral_0^1 sqrt(2 Gamma f_bulk) dtheta` at coexistence | Interface-energy consistency check | Analytic audit, not an evolution equation. |
| 8 | `gamma = w Gamma/(6 sqrt(2))` | Sets `Gamma` from `gamma` and `w` | Parameter audit: gives about `20 mJ/m^2` for the table values. |
| 9 | `theta_t = -alpha_theta delta F/delta theta` | Nonconserved Allen-Cahn kinetics | Weak Form PDE `pf`; every non-time term carries `/tau1`, so COMSOL unit checking preserves the paper's time scale. |
| 10 | Isotropic phase evolution | Mandatory isotropic baseline | Same weak equation as Eq. 27 with `anisOn=0` and `topoOn=0`. |
| 11 | `n_hat=grad(theta)/|grad(theta)|=(cos phi,sin phi)` | Interface-normal angle | `phi=atan2(thetay,thetax)`. |
| 12 | `f_w=1+delta cos[a(phi-phi0)]+delta sin^2[a(phi-phi0)]/2` | Interfacial anisotropy | `fw`, `fwp`; disabled for the mandatory baseline. |
| 13 | Anisotropic phase evolution | Optional Figure 12-13 reproduction | Flux form `qphix`, `qphiy`; parameterized but not yet solved in COMSOL. |

### Published barrier-term inconsistency

The PDF prints a `+1/(4w^2) theta(1-theta)(1-2theta)` contribution in Eqs.
10, 13, and 27.  That sign and coefficient do not follow from the paper's own
free energy.  Differentiating Eq. 4 in the negative-gradient law of Eq. 9 gives

`-1/(2w^2) theta(1-theta)(1-2theta)`.

The `-1/2` coefficient is also the one for which the Eq. 29 tanh profile is
stationary at coexistence and for which Eq. 8 follows from Eqs. 4-7.  A literal
`+1/4` run produces qualitatively excessive growth.  Therefore:

- the default acceptance convention is `barrierCoeff=-0.5`;
- `CASE_BARRIER_COEFF=0.25` retains the printed convention for sensitivity;
- every result must record the selected convention.

This is an explicit reproduction decision, not an unreported correction.

## Finite deformation and topology constraints

| Eq. | Paper content | Reproduction use | Implementation / status |
|---:|---|---|---|
| 14 | `div sigma=0` | Mechanical-equilibrium limit | Approached dynamically with `tau2/tau1=0.1`. |
| 15 | `u_t=-alpha_u delta F/delta u=alpha_u div_X sigma` | Mechanical relaxation | Basis for the two displacement Weak Form PDEs. |
| 16 | Explicit divergence of the entropic-elastic stress | Constitutive force without pressure | Included in `qij` / `mechX` / `mechY`. |
| 17 | Adds pressure Lagrange multiplier for incompressibility | Constrained displacement relaxation | `P` enters diagonal `qij`; a separate pressure equation enforces `detF=1`, with a disclosed `1e-8 P` pressure-nullspace gauge whose error is measured. |
| 18 | Eulerian finite-deformation relaxation `u_i,t = alpha_u F_kj partial_k[-P delta_ij + g rho R T/n partial u_i/partial X_j]` | Mandatory full-mechanics equation | `mechX`, `mechY`, physics `mechx` and `mechy`; requires remote compile/solve validation. |
| 19 | In 2D, `F=[[1-u_y,y, u_y,x],[u_x,y,1-u_x,x]]` under `detF=1` | Eulerian deformation-gradient identity | `F11`...`F22`, with dimensionless displacements scaled by `w`. |
| 20 | `D u_topo/Dt = u_topo,t + v dot grad u_topo = v` | Expels conserved topological constraints | Two-component Weak Form PDE `topo`. |
| 21 | `D theta/Dt=theta_t+v dot grad theta=0` | Defines interface-following frame | Used to derive Eqs. 22-23. |
| 22 | `v=-theta_t grad(theta)/|grad(theta)|^2` | Formal interface velocity | Replaced by regularized Eq. 23 in computation. |
| 23 | `v=-theta_t grad(theta)/(|grad(theta)|^2+alpha_cut)` | Localized, regularized interface velocity | `vix`, `viy`, `alphaCut=1e-4`. |
| 24 | `epsilon_topo,ij=(partial_j u_topo,i + partial_i u_topo,j)/2` | Topological small strain | `et11`, `et22`, `et12`. |
| 25 | `f_topo=mu* Tr(epsilon_topo^2)+lambda*/2 [Tr(epsilon_topo)]^2` | Elastic-belt energy | `Wtopo`; 2D Lamé constants from the paper. |
| 26 | `f_bulk -> f_bulk - g(theta) f_topo` | Restricts the penalty to the amorphous side | The negative `Wtopo/fscale` contribution in `drive`; Eq. 27 then contains `-g' f_topo`. |
| 27 | Full anisotropic phase equation including topological energy | Mandatory coupled phase equation | Physics `pf`; isotropic baseline by `anisOn=0`, topology switch by `topoOn`. |

## Initial/boundary data and observables

| Eq. | Paper content | Reproduction use | Implementation / status |
|---:|---|---|---|
| 28 | `u_x=(lambda-1)x/lambda`, `u_y=(1-lambda)y` | Homogeneous incompressible initial and boundary displacement | Initial values; `u_x` fixed only left/right and `u_y` only top/bottom, matching the PDF. |
| 29 | `theta(r,0)=[1-tanh((r-R_n)/(2 sqrt(2)w))]/2` | Circular diffuse nucleus | Exact initial expression, `R_n=9 nm`. |
| 30 | 2D amorphous stress tensor; in particular `sigma_xx=g rho R T/n (u_x,x-u_y,y)` | Stress-relaxation observable | `sigxx`, averaged with an amorphous-region weight as `sigmaAmorph`. |

## Acceptance implications

The reduced reference solver gives useful evidence for Eqs. 20, 23-27, and 29,
but it prescribes the far-field strain and therefore cannot validate Eq. 18,
incompressibility, or Eq. 30.  Those criteria remain fail-closed until a COMSOL
model compiles, completes a solve, exports finite metrics, and produces a saved
solved MPH artifact.  A generated Java file alone is not evidence of a solved
multiphysics reproduction.
