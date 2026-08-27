# Equation audit — Kobayashi 1993

## Frozen fields and convention

Dependent-variable order is **`[p, T]`**. `p` is dimensionless (`0` liquid,
`1` solid); `T` is the dimensionless temperature (`0` cooling temperature,
`1` equilibrium temperature). COMSOL uses computational coordinates measured
in `L0` and time in `t0`; the Java model represents `L0` by `m` and `t0` by `s`
only to make coefficient dimensions consistent. These are not physical metres
or seconds.

COMSOL General Form PDE uses

`ea*u_tt + da*u_t + div(Gamma) = f`, with boundary
`-n·Gamma = g-q*u` and optional Dirichlet `h*u=r`.

No Dirichlet boundary is used. On all four sides `g=0`, `q=0`; therefore the
natural boundary is `n·Gamma=0`.

## Paper equation (3): anisotropic phase field

Paper form (PDF p.3):

`tau*p_t = -d_x(epsilon*epsilon_theta*p_y)
             +d_y(epsilon*epsilon_theta*p_x)
             +div(epsilon^2*grad(p))
             +p*(1-p)*(p-1/2+m(T)) + noise`.

Definitions:

- `theta=atan2(-p_y,-p_x)` because the outward normal is `-grad(p)`;
- `sigma=1+delta*cos(j*(theta-theta0))`;
- `epsilon=epsilon_bar*sigma`;
- `epsilon_theta=-epsilon_bar*delta*j*sin(j*(theta-theta0))`;
- `m(T)=(alpha/pi)*atan(gamma*(1-T))`;
- `noise=a*p*(1-p)*chi`, `chi in [-1/2,1/2]`.

Exact General Form mapping:

- `ea_p=0`
- `da_p=tau`
- `Gamma_px=epsilon*epsilon_theta*p_y-epsilon^2*p_x`
- `Gamma_py=-epsilon*epsilon_theta*p_x-epsilon^2*p_y`
- `f_p=p*(1-p)*(p-0.5+m(T))+a*p*(1-p)*chi`
- boundary `g_p=0`, `q_p=0`, no `h/r`

Expanding `div(Gamma_p)` on the left reproduces every sign in paper equation
(3). `nojac(epsilon)` and `nojac(epsilon_theta)` may be used in the Newton
Jacobian to avoid differentiating `atan2` where `grad(p)=0`; this changes the
linearization only, not the residual equation.

## Paper equation (5): heat and latent heat

Paper form (PDF p.4): `T_t=laplacian(T)+K*p_t` with equal diffusivity in solid
and liquid. Exact General Form mapping is:

- `ea_T=0`
- `da_T=1`
- `Gamma_Tx=-D*T_x`, `Gamma_Ty=-D*T_y`, `D=1 L0^2/t0`
- `f_T=K*d(p,t)`
- boundary `g_T=0`, `q_T=0`, no `h/r` (adiabatic Fig. 7)

The invariant under these boundaries is
`H=int_Omega(T-K*p)dOmega`; its drift is a required numerical-health metric.

## Initial state and disclosed assumptions

The paper fixes `T=0` and says nucleation occurs at the centre of the bottom
edge, but supplies no radius/profile. The reproduction freezes

`p0=0.5*(1-tanh((sqrt((x-4.5)^2+y^2)-R0)/(sqrt(2)*epsilon_bar)))`

with baseline `R0=0.15`, plus `R0={0.12,0.18}` sensitivity runs. This is a
semicircle because its centre lies on the bottom boundary.

The paper reports uniform random noise but not seed/cadence. The reproducible
implementation uses a deterministic hash field on paper-grid/time cells,
mapped to `[-0.5,0.5]`, and records seed `1993`. Noise-free runs are the
authority for convergence; noisy runs are used for Fig. 7 morphology.

## Numerical and evidence boundary

The original `300x300`, `dt=0.0002` settings are reproduced, but the paper
explicitly states they were selected for qualitative morphology rather than
precise interfacial velocity (PDF p.13). Consequently:

- Fig. 7 silhouette/contour comparisons use tolerant qualitative thresholds;
- mesh, time-step, and seed-size sensitivity are separate hard gates;
- structures at or below `epsilon_bar` are excluded from branch metrics;
- a Slurm success code without clean COMSOL logs, exports, and a nonempty final
  MPH can never satisfy acceptance.
