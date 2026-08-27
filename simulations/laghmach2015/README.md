# Laghmach et al. (2015) reproduction case

This directory contains the auditable source for reproducing the phase-field
model in *J. Chem. Phys.* **142**, 244905 (2015), DOI
`10.1063/1.4923226`.

The reproduction has two solver paths:

1. `reference_solver.py` is a transparent finite-difference implementation of
   Eqs. (20) and (27). It is intended for equation/unit checks and parameter
   sweeps. The far-field rubber strain is prescribed; consequently it is not
   the authority for the paper's stress-relaxation result.
2. `comsol/Laghmach2015.java` builds the coupled COMSOL model. Its mechanics
   equations, phase field and topology transport are solved together. The
   generated `.mph` and CSV exports are the acceptance authority.

`case.yml` is the machine-readable contract. Results are evaluated by the
generic `paper_engine.simulation_reproduction` package. Solver output belongs
below the ignored project path `tmp/runs/` rather than in Git.

Run the reference calculation with a Python environment containing NumPy:

```bash
python simulations/laghmach2015/reference_solver.py \
  --case simulations/laghmach2015/case.yml \
  --output-root tmp/runs/reference
```

To regenerate the complete reduced-reference evidence suite from one command,
including controls, convergence, threshold and nucleus-memory runs, use:

```bash
LAGHMACH_PYTHON_BIN=/path/to/python \
  bash simulations/laghmach2015/run_reference_suite.sh
```

The suite reports validator exit `2` while full-mechanics metrics are absent;
that is the intended fail-closed partial-reproduction state, not a script
failure.

After downloading a completed COMSOL suite arranged as `core/`, `threshold/`,
and `surface/`, aggregate and validate all mandatory metrics with:

```bash
LAGHMACH_PYTHON_BIN=/path/to/python \
  bash simulations/laghmach2015/evaluate_comsol_suite.sh \
  /path/to/comsol-suite tmp/runs/comsol/laghmach2015/final
```

The paper uses molar density and molar enthalpy. Therefore the symbol printed
as `k_B` in the article is evaluated as the molar gas constant `R`; using the
particle-scale Boltzmann constant would be dimensionally inconsistent.

The printed phase-barrier coefficient is internally inconsistent with the
paper's free energy, surface tension, and analytic interface profile. See
`equation_audit.md`; both conventions are retained, and the default
`-1/2` is the variationally consistent one.

Generate the Stage-0 free-energy cross-check and final reduced-model field
maps with:

```bash
PYTHONPATH=src python simulations/laghmach2015/make_free_energy_figure.py \
  --output tmp/runs/reference/laghmach2015/free_energy_figure2.svg
PYTHONPATH=src python simulations/laghmach2015/make_field_figures.py \
  --fields tmp/runs/reference/laghmach2015/variational_central_topology_on_t150/raw/final_fields.npz \
  --output-directory tmp/runs/reference/laghmach2015/field_figures
```

The independent parameter identities can be checked with:

```bash
PYTHONPATH=src python simulations/laghmach2015/audit_parameters.py \
  --case simulations/laghmach2015/case.yml \
  --output tmp/runs/reference/laghmach2015/parameter_audit.json
```

Build the self-contained Chinese offline report, with all five SVG figures
embedded and no network dependencies, with:

```bash
python simulations/laghmach2015/build_offline_report.py \
  --output tmp/laghmach2015_offline_summary.html
```
