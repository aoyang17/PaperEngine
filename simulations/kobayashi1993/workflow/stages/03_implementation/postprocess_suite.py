#!/usr/bin/env python3
"""Build fail-closed Kobayashi 1993 acceptance metrics from a downloaded COMSOL suite."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from typing import Any

from paper_engine.simulation_reproduction.timeseries import interpolate, read_numeric_csv


DELTA_CASES = ("delta000", "delta005", "delta010", "delta020", "delta050")
REQUIRED_CASES = DELTA_CASES + (
    "control_delta000",
    "control_delta020",
    "mesh_fine",
    "timestep_fine",
    "seed_small",
    "seed_large",
)
ERROR_PATTERN = re.compile(r"(?:\bError\b|Exception|FileNotFound)", re.IGNORECASE)


def _column(row: dict[str, float], *needles: str) -> str:
    normalized = {key.lower().replace(" ", ""): key for key in row}
    for needle in needles:
        compact = needle.lower().replace(" ", "")
        for candidate, original in normalized.items():
            if candidate == compact or candidate.startswith(compact + "("):
                return original
    raise KeyError(f"missing columns {needles}; available: {', '.join(row)}")


def _history(path: Path) -> dict[str, Any]:
    rows = read_numeric_csv(path)
    first = rows[0]
    columns = {
        "time": _column(first, "Time(s)", "Time", "t"),
        "enthalpy": _column(first, "enthalpyInvariant"),
        "tip": _column(first, "tipY"),
        "half_width": _column(first, "halfWidth"),
        "p_min": _column(first, "pMin"),
        "p_max": _column(first, "pMax"),
    }
    initial_enthalpy = rows[0][columns["enthalpy"]]
    enthalpy_scale = max(abs(initial_enthalpy), 1e-12)
    return {
        "rows": rows,
        "columns": columns,
        "p_min": min(row[columns["p_min"]] for row in rows),
        "p_max": max(row[columns["p_max"]] for row in rows),
        "max_relative_enthalpy_drift": max(
            abs(row[columns["enthalpy"]] - initial_enthalpy) / enthalpy_scale for row in rows
        ),
    }


def _at(history: dict[str, Any], metric: str, time_value: float) -> float:
    return interpolate(
        history["rows"],
        history["columns"]["time"],
        history["columns"][metric],
        time_value,
    )


def _relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(right), 1e-12)


def _error_count(case_dir: Path) -> int:
    count = 0
    for path in sorted(case_dir.glob("*.log")) + sorted(case_dir.glob("slurm.*.out")) + sorted(case_dir.glob("slurm.*.err")):
        if path.is_file():
            count += len(ERROR_PATTERN.findall(path.read_text(encoding="utf-8", errors="replace")))
    return count


def _validate_jobs(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("job status must be a JSON object")
    for case in REQUIRED_CASES:
        record = data.get(case)
        if not isinstance(record, dict):
            raise ValueError(f"missing job status: {case}")
        if record.get("state") != "COMPLETED" or str(record.get("exit_code")) != "0:0":
            raise ValueError(f"job did not complete cleanly: {case}: {record}")
    return data


def build_metrics(suite: Path, job_status: Path, fig7_metrics: Path) -> dict[str, Any]:
    _validate_jobs(job_status)
    histories: dict[str, dict[str, Any]] = {}
    error_count = 0
    for case in REQUIRED_CASES:
        case_dir = suite / case
        global_csv = case_dir / f"{case}_global.csv"
        solved_mph = case_dir / f"{case}_solved.mph"
        fields_csv = case_dir / f"{case}_fields.csv"
        for artifact in (global_csv, solved_mph, fields_csv):
            if not artifact.is_file() or artifact.stat().st_size == 0:
                raise ValueError(f"missing solver artifact: {artifact}")
        histories[case] = _history(global_csv)
        error_count += _error_count(case_dir)

    figure = json.loads(fig7_metrics.read_text(encoding="utf-8"))
    mean_iou = float(figure["mean_iou"])
    normalized_chamfer = float(figure["normalized_chamfer"])
    baseline = histories["control_delta020"]
    fine_mesh = histories["mesh_fine"]
    fine_time = histories["timestep_fine"]
    seed_values = [
        _at(histories["seed_small"], "tip", 0.8),
        _at(baseline, "tip", 0.8),
        _at(histories["seed_large"], "tip", 0.8),
    ]
    delta000_tip = _at(histories["delta000"], "tip", 1.4)
    delta050_tip = _at(histories["delta050"], "tip", 1.4)
    delta050_half_width = _at(histories["delta050"], "half_width", 1.4)
    all_histories = list(histories.values())
    final_mph = suite / "delta020" / "delta020_solved.mph"

    metrics = {
        "artifacts": {"final_mph_bytes": final_mph.stat().st_size},
        "quality": {
            "comsol_error_count": error_count,
            "p_min": min(history["p_min"] for history in all_histories),
            "p_max": max(history["p_max"] for history in all_histories),
            "max_relative_enthalpy_drift": max(
                history["max_relative_enthalpy_drift"] for history in all_histories
            ),
        },
        "convergence": {
            "mesh_tip_relative_difference": _relative_difference(
                _at(baseline, "tip", 0.8), _at(fine_mesh, "tip", 0.8)
            ),
            "timestep_tip_relative_difference": _relative_difference(
                _at(baseline, "tip", 0.8), _at(fine_time, "tip", 0.8)
            ),
            "seed_tip_relative_range": (max(seed_values) - min(seed_values))
            / max(abs(seed_values[1]), 1e-12),
        },
        "paper_trend": {
            "delta050_to_delta000_tip_ratio": delta050_tip / max(delta000_tip, 1e-12),
            "delta050_vertical_to_horizontal_extent_ratio": delta050_tip
            / max(delta050_half_width, 1e-12),
        },
        "paper_figure": {
            "fig7_mean_iou": mean_iou,
            "fig7_normalized_chamfer": normalized_chamfer,
        },
    }
    for section in metrics.values():
        if isinstance(section, dict):
            for value in section.values():
                if isinstance(value, (int, float)) and not math.isfinite(float(value)):
                    raise ValueError("non-finite acceptance metric")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--job-status", type=Path, required=True)
    parser.add_argument("--fig7-metrics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_metrics(args.suite, args.job_status, args.fig7_metrics)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
