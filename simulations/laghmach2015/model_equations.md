# Model transcription and COMSOL mapping

All lengths below are nondimensionalized by the interface width `w = 1 nm`,
and time by `tau1`. The interpolation function is

`g(theta) = 1 - theta^2 (3 - 2 theta)`, `g'(theta) = 6 theta (theta - 1)`.

For an isotropic interface, Eq. (27) is transcribed as

```text
theta_t = (Gamma/fscale) [laplacian(theta)
          - theta(1-theta)(1-2theta)/2]
          - g'(theta) [Delta_flory - Wtopo/fscale]

Delta_flory = hm/(R Tm0) (Tm0-T)/Tm0 + T/(n Tm0) Tr(E)
Wtopo = lambda_topo/2 Tr(eps_topo)^2
        + mu_topo Tr(eps_topo^2)
```

## Published barrier-term inconsistency

The printed Eqs. (10), (13), and (27) show
`+theta(1-theta)(1-2theta)/4`. That term is inconsistent with three other
equations in the same paper:

1. differentiating the double well in Eq. (4),
   `Gamma theta^2(1-theta)^2/4`, in the negative-gradient Allen–Cahn law gives
   `-Gamma theta(1-theta)(1-2theta)/2`;
2. that coefficient makes the Eq. (29) profile with width `2 sqrt(2) w` an
   exact planar stationary solution at coexistence;
3. the same Eq. (4) plus the gradient energy in Eq. (5) yields the reported
   surface tension `gamma=w Gamma/(6 sqrt(2))` in Eq. (8).

The case therefore defaults to the variational coefficient `-1/2`. The
literal printed coefficient `+1/4` remains recorded and can be selected as a
sensitivity control. Any report must state which convention was used.

`E = (F^T F-I)/2` is the Green-Lagrange strain and incompressibility is
`det(F)=1`. In the paper's Eulerian coordinates, Eq. (19) gives

```text
F = [[1-d(uy,y), d(uy,x)], [d(ux,y), 1-d(ux,x)]]
```

and Eq. (18) is

```text
u_i,t = alpha_u F_kj d/dx_k [ -P delta_ij
        + g(theta) rho R T/n d(u_i)/dX_j ]
```

with `d(u_i)/dX_j = d(u_i)/d(x_l) F_lj`. COMSOL enforces
`det(F)=1` using pressure as a Lagrange multiplier and uses
`tau2/tau1=0.1`.

The mixed system otherwise has a free constant-pressure mode. The COMSOL
algebraic equation therefore uses the disclosed gauge
`det(F)-1+1e-8*P=0`. This is a numerical nullspace regularization, not a new
material compressibility: both the L2 and maximum errors in `det(F)-1` are
exported and the original incompressibility threshold remains mandatory.

The topology field follows Eq. (20):

```text
utopo_t + v dot grad(utopo) = v
v = -theta_t grad(theta) / (|grad(theta)|^2 + alpha_cut)
alpha_cut = 1e-4
eps_topo = sym(grad(utopo))
```

The `alpha_cut` expression is dimensionless after the length scaling. The
topological energy is multiplied by `g(theta)`, so it is stored in the
amorphous/interfacial phase and rejected from the crystal.

The isotropic baseline is the mandatory first gate. Anisotropic Eq. (13) is a
separate study because its orientation-dependent gradient terms require a
distinct weak contribution. No isotropic result may be relabeled as the
anisotropic reproduction.

## Observable definitions

- Effective radius: `sqrt(integral(theta)/pi)` (the paper's definition).
- Plateau slope: least-squares slope over the last 20% of saved time points.
- Crystal core dimensions: axis extents of the `theta=0.99` and `theta=0.95`
  contours, reported separately as required by Figures 12-13.
- Elastic belt: connected high-`Wtopo` annulus intersecting `0.05 < theta < 0.95`.
- Far-field stress: area average of `sigma_xx` over `theta < 0.05`.
- Incompressibility error: maximum of `abs(det(F)-1)` over space and time.

## Initial and boundary data

Equation (28) fixes the homogeneous incompressible displacement
`ux=(lambda-1)x/lambda`, `uy=(1-lambda)y`. Equation (29) initializes
`theta=0.5{1-tanh[(r-Rn)/(2 sqrt(2) w)]}`. The phase field is zero at the box
edge; `ux` is fixed on the left/right sides and `uy` on the top/bottom sides,
exactly as specified below Eq. (29). The unspecified tangential components use
natural boundary conditions. Pressure and topological displacement start at
zero.
