#!/usr/bin/env python3
"""Independent unit/parameter identities for the Laghmach 2015 case."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from paper_engine.simulation_reproduction.spec import load_case_spec


def audit(case_path: Path) -> dict[str, object]:
    parameters = load_case_spec(case_path).parameters
    rho = float(parameters["monomer_density_mol_m3"])
    gas_constant = float(parameters["gas_constant_J_mol_K"])
    melting_temperature = float(parameters["Tm0_K"])
    gamma = float(parameters["gamma_J_m2"])
    width_m = float(parameters["interface_width_nm"]) * 1e-9
    gamma_barrier = float(parameters["Gamma_J_m3"])
    fscale_tabulated = float(parameters["free_energy_scale_J_m3"])
    lam = float(parameters["topological_lambda_Pa"])
    mu = float(parameters["topological_mu_Pa"])

    fscale_derived = rho * gas_constant * melting_temperature
    gamma_derived = width_m * gamma_barrier / (6.0 * math.sqrt(2.0))
    # From the paper's 2D identities: lambda/mu=2 nu/(1-nu).
    poisson_2d = lam / (lam + 2.0 * mu)
    young_2d = 2.0 * mu * (1.0 + poisson_2d)
    result = {
        "free_energy_scale": {
            "tabulated_J_m3": fscale_tabulated,
            "derived_rho_R_Tm0_J_m3": fscale_derived,
            "relative_difference": abs(fscale_derived - fscale_tabulated) / fscale_tabulated,
        },
        "surface_tension": {
            "tabulated_J_m2": gamma,
            "derived_w_Gamma_over_6sqrt2_J_m2": gamma_derived,
            "relative_difference": abs(gamma_derived - gamma) / gamma,
        },
        "topological_lame_2d": {
            "lambda_Pa": lam,
            "mu_Pa": mu,
            "implied_poisson_ratio": poisson_2d,
            "implied_young_modulus_Pa": young_2d,
            "relative_difference_from_500kPa": abs(young_2d - 500000.0) / 500000.0,
        },
    }
    result["passed"] = (
        result["free_energy_scale"]["relative_difference"] < 0.001  # type: ignore[index]
        and result["surface_tension"]["relative_difference"] < 0.001  # type: ignore[index]
        and result["topological_lame_2d"]["relative_difference_from_500kPa"] < 0.05  # type: ignore[index]
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.case)
    content = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
