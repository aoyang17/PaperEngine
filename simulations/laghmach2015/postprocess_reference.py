#!/usr/bin/env python3
"""Build a partial acceptance record from the reduced reference solver."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from paper_engine.simulation_reproduction.timeseries import read_numeric_csv, tail_slope, time_to_fraction
from paper_engine.simulation_reproduction.spec import load_case_spec
from postprocess_comsol import _exponential_fit, compare_radius_curve, compare_surface_curves
from reference_solver import State, _topological_energy


def _result(run: Path) -> dict:
    return json.loads((run / "raw" / "result.json").read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--control-run", type=Path, required=True)
    parser.add_argument("--reference-radius", type=Path, required=True)
    parser.add_argument("--fine-grid-run", type=Path)
    parser.add_argument("--half-timestep-run", type=Path)
    parser.add_argument("--threshold-run", type=Path, action="append", default=[])
    parser.add_argument("--surface-large-nucleus-run", type=Path)
    parser.add_argument("--surface-small-nucleus-run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    spec = load_case_spec(args.case)
    baseline_result = _result(args.baseline_run)
    control_result = _result(args.control_run)
    baseline_history_path = args.baseline_run / "raw" / "radius_history.csv"
    control_history_path = args.control_run / "raw" / "radius_history.csv"
    baseline_rows = read_numeric_csv(baseline_history_path)
    control_rows = read_numeric_csv(control_history_path)
    baseline_radius = baseline_rows[-1]["effective_radius_nm"]
    baseline_slope = tail_slope(baseline_rows, "time_tau1", "effective_radius_nm")
    control_slope = tail_slope(control_rows, "time_tau1", "effective_radius_nm")

    fields = np.load(args.baseline_run / "raw" / "final_fields.npz")
    state = State(theta=fields["theta"], utx=fields["utx"], uty=fields["uty"])
    dx = float(baseline_result["diagnostics"]["grid_nm"]) / float(spec.parameters["interface_width_nm"])
    energy = _topological_energy(
        state,
        dx,
        float(spec.parameters["topological_lambda_Pa"]),
        float(spec.parameters["topological_mu_Pa"]),
    )
    g = 1.0 - state.theta**2 * (3.0 - 2.0 * state.theta)
    weighted = g * energy
    interface = (state.theta > 0.05) & (state.theta < 0.95)
    belt_overlap = float(weighted[interface].sum() / max(float(weighted.sum()), 1e-30))

    quality = {
        "theta_min": baseline_result["diagnostics"]["raw_theta_min"],
        "theta_max": baseline_result["diagnostics"]["raw_theta_max"],
    }
    if args.fine_grid_run:
        fine_radius = _result(args.fine_grid_run)["diagnostics"]["final_effective_radius_nm"]
        quality["radius_grid_relative_difference"] = abs(fine_radius - baseline_radius) / abs(fine_radius)
    if args.half_timestep_run:
        half_radius = _result(args.half_timestep_run)["diagnostics"]["final_effective_radius_nm"]
        quality["radius_timestep_relative_difference"] = abs(half_radius - baseline_radius) / abs(half_radius)
        half_rows = read_numeric_csv(args.half_timestep_run / "raw" / "radius_history.csv")
        baseline_t95 = time_to_fraction(baseline_rows, "time_tau1", "effective_radius_nm")
        half_t95 = time_to_fraction(half_rows, "time_tau1", "effective_radius_nm")
        quality["t95_timestep_relative_difference"] = abs(half_t95 - baseline_t95) / abs(half_t95)

    threshold_groups: dict[int, list[tuple[float, bool]]] = {}
    for run_path in args.threshold_run:
        run_result = _result(run_path)
        diagnostic = run_result["diagnostics"]
        run_rows = read_numeric_csv(run_path / "raw" / "radius_history.csv")
        temperature_key = int(round(float(diagnostic.get("temperature_K", spec.parameters["temperature_K"]))))
        grew = (
            diagnostic.get("termination_reason", "final_time") != "crystal_melted"
            and run_rows[-1]["effective_radius_nm"] > run_rows[0]["effective_radius_nm"]
        )
        threshold_groups.setdefault(temperature_key, []).append(
            (float(diagnostic.get("stretch_lambda", spec.parameters["stretch_lambda"])), grew)
        )
    threshold_metrics = {
        f"lambda_c_{temperature}K": min(stretch for stretch, grew in values if grew)
        for temperature, values in threshold_groups.items()
        if any(grew for _, grew in values)
    }

    surface_rows = baseline_rows
    surface_path = baseline_history_path
    if args.surface_large_nucleus_run:
        surface_path = args.surface_large_nucleus_run / "raw" / "radius_history.csv"
        surface_rows = read_numeric_csv(surface_path)
    surface_fit = _exponential_fit(
        [row["effective_radius_nm"] - surface_rows[0]["effective_radius_nm"] for row in surface_rows],
        [row.get("elastic_surface_tension_J_m2", 0.0) for row in surface_rows],
    )
    if args.surface_small_nucleus_run:
        surface_fit["nucleus_curve_nrmse"] = compare_surface_curves(
            surface_path,
            args.surface_small_nucleus_run / "raw" / "radius_history.csv",
        )

    metrics = {
        "scope": "partial reduced-model evidence; Eq. 18 and stress criteria intentionally absent",
        "baseline": {
            "final_effective_radius_nm": baseline_radius,
            "final_radius_slope_nm_per_tau1": baseline_slope,
            "final_relative_drift_per_100tau1": abs(baseline_slope) * 100.0 / baseline_radius,
            "elastic_belt_interface_overlap": belt_overlap,
        },
        "control": {
            "final_effective_radius_nm": control_rows[-1]["effective_radius_nm"],
            "final_radius_slope_nm_per_tau1": control_slope,
        },
        "quality": quality,
        "paper_curve": compare_radius_curve(baseline_history_path, args.reference_radius),
        "surface_fit": surface_fit,
        "threshold": threshold_metrics,
        "provenance": {
            "baseline_run": str(args.baseline_run.resolve()),
            "control_run": str(args.control_run.resolve()),
            "barrier_convention": spec.parameters["barrier_convention"],
            "current_case_sha256": hashlib.sha256(args.case.read_bytes()).hexdigest(),
            "baseline_run_case_sha256": baseline_result["provenance"].get("case_sha256"),
            "control_run_case_sha256": control_result["provenance"].get("case_sha256"),
            "note": "The case contract evolved during development; each run records its actual diagnostics and whole-file hash. run_reference_suite.sh regenerates a single-current-hash suite.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
