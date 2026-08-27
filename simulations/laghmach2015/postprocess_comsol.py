#!/usr/bin/env python3
"""Convert COMSOL global-evaluation CSV files into case acceptance metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import math

from paper_engine.simulation_reproduction.timeseries import (
    interpolate,
    mean_normalized_rmse,
    normalized_rmse,
    read_numeric_csv,
    tail_slope,
    time_to_fraction,
)


ALIASES = {
    "time": ("Time (s)", "time", "t", "time_tau1"),
    "radius": ("effectiveRadius (nm)", "effectiveRadius", "radius_nm", "effective_radius_nm"),
    "incompressibility_l2": ("incompL2", "incompL2 (1)"),
    "incompressibility_max": ("incompMax", "incompMax (1)", "detF_error"),
    "theta_max": ("maxop1(theta)", "Maximum 1 (1)", "theta_max"),
    "theta_min": ("minop1(theta)", "Minimum 1 (1)", "theta_min"),
    "stress": ("sigmaAmorph (MPa)", "sigmaAmorph", "stress_MPa"),
    "belt_overlap": ("beltInterfaceOverlap", "beltInterfaceOverlap (1)", "belt_overlap"),
    "elastic_gamma": (
        "elasticGamma (J/m^2)",
        "elasticGamma",
        "elastic_gamma_J_m2",
        "elastic_surface_tension_J_m2",
    ),
}

PARAMETER_ALIASES = {
    "temperature": ("T (K)", "T", "temperature_K"),
    "stretch": ("lamStretch", "stretch_lambda"),
}


def _column(row: dict[str, float], name: str) -> str:
    for candidate in ALIASES[name]:
        if candidate in row:
            return candidate
    raise KeyError(f"could not identify {name} column; available: {', '.join(row)}")


def _parameter_column(row: dict[str, float], name: str) -> str:
    for candidate in PARAMETER_ALIASES[name]:
        if candidate in row:
            return candidate
    raise KeyError(f"could not identify {name} parameter column; available: {', '.join(row)}")


def _exponential_fit(displacements: list[float], values: list[float]) -> dict[str, float]:
    usable = [(x, math.log(y)) for x, y in zip(displacements, values) if y > 0]
    if len(usable) < 3:
        return {"A_J_m2": float("nan"), "B_per_nm": float("nan"), "r_squared": float("nan")}
    xs, logs = zip(*usable)
    mean_x = sum(xs) / len(xs)
    mean_y = sum(logs) / len(logs)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator <= 0:
        return {"A_J_m2": float("nan"), "B_per_nm": float("nan"), "r_squared": float("nan")}
    slope = sum((x - mean_x) * (y - mean_y) for x, y in usable) / denominator
    intercept = mean_y - slope * mean_x
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in usable)
    total = sum((y - mean_y) ** 2 for y in logs)
    return {
        "A_J_m2": math.exp(intercept),
        "B_per_nm": slope,
        "r_squared": 1.0 - residual / total if total > 0 else 1.0,
    }


def extract_history(path: Path) -> tuple[dict[str, float], dict[str, float]]:
    rows = read_numeric_csv(path)
    columns = {name: _column(rows[0], name) for name in ALIASES}
    slope = tail_slope(rows, columns["time"], columns["radius"])
    final_radius = rows[-1][columns["radius"]]
    result = {
        "final_effective_radius_nm": final_radius,
        "final_radius_slope_nm_per_tau1": slope,
        "final_relative_drift_per_100tau1": abs(slope) * 100.0 / max(abs(final_radius), 1e-30),
        "theta_min": min(row[columns["theta_min"]] for row in rows),
        "theta_max": max(row[columns["theta_max"]] for row in rows),
        "l2_detF_minus_one": max(row[columns["incompressibility_l2"]] for row in rows),
        "max_abs_detF_minus_one": max(row[columns["incompressibility_max"]] for row in rows),
        "saved_time_points": len(rows),
        "elastic_belt_interface_overlap": rows[-1][columns["belt_overlap"]],
        "initial_stress_MPa": rows[0][columns["stress"]],
        "final_stress_MPa": rows[-1][columns["stress"]],
        "stress_drop_fraction": (rows[0][columns["stress"]] - rows[-1][columns["stress"]]) / max(abs(rows[0][columns["stress"]]), 1e-30),
    }
    radius0 = rows[0][columns["radius"]]
    fit = _exponential_fit(
        [row[columns["radius"]] - radius0 for row in rows],
        [row[columns["elastic_gamma"]] for row in rows],
    )
    return result, fit


def compare_radius_curve(comsol_path: Path, reference_path: Path) -> dict[str, float]:
    simulation = read_numeric_csv(comsol_path)
    reference = read_numeric_csv(reference_path)
    sim_time = _column(simulation[0], "time")
    sim_radius = _column(simulation[0], "radius")
    ref_time = "time_tau1"
    ref_radius = "effective_radius_nm"
    usable = [row for row in reference if simulation[0][sim_time] <= row[ref_time] <= simulation[-1][sim_time]]
    predicted = [interpolate(simulation, sim_time, sim_radius, row[ref_time]) for row in usable]
    observed = [row[ref_radius] for row in usable]
    sim_t95 = time_to_fraction(simulation, sim_time, sim_radius)
    ref_t95 = time_to_fraction(reference, ref_time, ref_radius)
    return {
        "radius_nrmse": normalized_rmse(predicted, observed),
        "plateau_relative_error": abs(simulation[-1][sim_radius] - reference[-1][ref_radius]) / reference[-1][ref_radius],
        "t95_relative_error": abs(sim_t95 - ref_t95) / ref_t95,
        "reference_t95_tau1": ref_t95,
        "simulation_t95_tau1": sim_t95,
        "comparison_points": len(usable),
    }


def compare_stress_curve(comsol_path: Path, reference_path: Path) -> dict[str, float]:
    simulation = read_numeric_csv(comsol_path)
    reference = read_numeric_csv(reference_path)
    sim_time = _column(simulation[0], "time")
    sim_stress = _column(simulation[0], "stress")
    usable = [
        row for row in reference
        if simulation[0][sim_time] <= row["time_tau1"] <= simulation[-1][sim_time]
    ]
    predicted = [
        interpolate(simulation, sim_time, sim_stress, row["time_tau1"])
        for row in usable
    ]
    observed = [row["sigma_xx_MPa"] for row in usable]
    return {
        "stress_nrmse": mean_normalized_rmse(predicted, observed),
        "stress_comparison_points": len(usable),
    }


def compare_surface_curves(large_nucleus_path: Path, small_nucleus_path: Path) -> float:
    def displacement_rows(path: Path) -> list[dict[str, float]]:
        rows = read_numeric_csv(path)
        radius = _column(rows[0], "radius")
        gamma = _column(rows[0], "elastic_gamma")
        initial_radius = rows[0][radius]
        return [
            {"displacement_nm": row[radius] - initial_radius, "gamma_J_m2": row[gamma]}
            for row in rows
            if row[gamma] > 0
        ]

    large = displacement_rows(large_nucleus_path)
    small = displacement_rows(small_nucleus_path)
    lower = max(large[0]["displacement_nm"], small[0]["displacement_nm"])
    upper = min(large[-1]["displacement_nm"], small[-1]["displacement_nm"])
    if upper <= lower:
        return float("nan")
    points = [lower + (upper - lower) * index / 29 for index in range(30)]
    large_values = [interpolate(large, "displacement_nm", "gamma_J_m2", point) for point in points]
    small_values = [interpolate(small, "displacement_nm", "gamma_J_m2", point) for point in points]
    return mean_normalized_rmse(small_values, large_values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--fine-grid", type=Path)
    parser.add_argument("--half-timestep", type=Path)
    parser.add_argument("--surface-large-nucleus", type=Path)
    parser.add_argument("--surface-small-nucleus", type=Path)
    parser.add_argument("--reference-radius", type=Path)
    parser.add_argument("--reference-stress", type=Path)
    parser.add_argument("--threshold-run", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline, baseline_surface_fit = extract_history(args.baseline)
    surface_fit = baseline_surface_fit
    surface_large_path = args.surface_large_nucleus or args.baseline
    if args.surface_large_nucleus:
        _, surface_fit = extract_history(args.surface_large_nucleus)
    if args.surface_small_nucleus:
        surface_fit["nucleus_curve_nrmse"] = compare_surface_curves(
            surface_large_path,
            args.surface_small_nucleus,
        )
    control, _ = extract_history(args.control)
    quality: dict[str, Any] = {
        "theta_min": baseline.pop("theta_min"),
        "theta_max": baseline.pop("theta_max"),
        "max_abs_detF_minus_one": baseline.pop("max_abs_detF_minus_one"),
    }
    control.pop("theta_min")
    control.pop("theta_max")
    control.pop("max_abs_detF_minus_one")
    if args.fine_grid:
        fine, _ = extract_history(args.fine_grid)
        quality["radius_grid_relative_difference"] = abs(
            fine["final_effective_radius_nm"] - baseline["final_effective_radius_nm"]
        ) / max(abs(fine["final_effective_radius_nm"]), 1e-30)
    if args.half_timestep:
        half, _ = extract_history(args.half_timestep)
        quality["radius_timestep_relative_difference"] = abs(
            half["final_effective_radius_nm"] - baseline["final_effective_radius_nm"]
        ) / max(abs(half["final_effective_radius_nm"]), 1e-30)
        baseline_rows = read_numeric_csv(args.baseline)
        half_rows = read_numeric_csv(args.half_timestep)
        baseline_t95 = time_to_fraction(
            baseline_rows,
            _column(baseline_rows[0], "time"),
            _column(baseline_rows[0], "radius"),
        )
        half_t95 = time_to_fraction(
            half_rows,
            _column(half_rows[0], "time"),
            _column(half_rows[0], "radius"),
        )
        quality["t95_timestep_relative_difference"] = abs(half_t95 - baseline_t95) / max(abs(half_t95), 1e-30)

    metrics = {"baseline": baseline, "control": control, "quality": quality, "surface_fit": surface_fit}
    if args.reference_radius:
        metrics["paper_curve"] = compare_radius_curve(args.baseline, args.reference_radius)
    if args.reference_stress:
        metrics.setdefault("paper_curve", {}).update(compare_stress_curve(args.baseline, args.reference_stress))
    threshold_groups: dict[int, list[tuple[float, bool]]] = {}
    for threshold_path in args.threshold_run:
        rows = read_numeric_csv(threshold_path)
        radius = _column(rows[0], "radius")
        temperature = _parameter_column(rows[0], "temperature")
        stretch = _parameter_column(rows[0], "stretch")
        grew = rows[-1][radius] > rows[0][radius] + 1.0
        temperature_key = int(round(rows[0][temperature]))
        threshold_groups.setdefault(temperature_key, []).append((rows[0][stretch], grew))
    if threshold_groups:
        metrics["threshold"] = {
            f"lambda_c_{temperature}K": min(stretch for stretch, grew in values if grew)
            for temperature, values in threshold_groups.items()
            if any(grew for _, grew in values)
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
