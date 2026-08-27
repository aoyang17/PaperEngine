#!/usr/bin/env python3
"""Analyze downloaded COMSOL 6.4 Kobayashi runs and build Fig. 7 evidence."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import re
import shutil
from typing import Any

from PIL import Image, ImageDraw


DELTA_CASES = {
    0.0: "delta000",
    0.005: "delta005",
    0.01: "delta010",
    0.02: "delta020",
    0.05: "delta050",
}
REQUIRED_CASES = tuple(DELTA_CASES.values()) + (
    "control_delta000",
    "control_delta020",
    "mesh_fine",
    "timestep_fine",
    "seed_small",
    "seed_large",
)
ERROR_PATTERN = re.compile(r"(?:\bError\b|Exception|FileNotFound|Cannot open display)", re.IGNORECASE)
TIME_PATTERN = re.compile(r"(?:^|[@,; ])t\s*=\s*([-+0-9.eE]+)", re.IGNORECASE)


def _tokens(line: str) -> list[str]:
    return [item.strip() for item in next(csv.reader([line.lstrip("% ")]))]


def read_comsol_csv(path: Path) -> tuple[list[str], list[list[float]]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"missing COMSOL CSV: {path}")
    headers: list[list[str]] = []
    rows: list[list[float]] = []
    for raw in path.read_text(encoding="utf-8-sig", errors="strict").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("%"):
            candidate = _tokens(line)
            if len(candidate) >= 2:
                headers.append(candidate)
            continue
        values = [float(item.strip()) for item in next(csv.reader([line]))]
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"non-finite value in {path}")
        rows.append(values)
    if not rows:
        raise ValueError(f"no numeric data in {path}")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError(f"ragged COMSOL CSV: {path}")
    matching = [header for header in headers if len(header) == width]
    if not matching:
        raise ValueError(f"no full-width commented header in {path}")
    return matching[-1], rows


def _column(header: list[str], *names: str) -> int:
    compact = [re.sub(r"\s+", "", item).lower() for item in header]
    for name in names:
        target = re.sub(r"\s+", "", name).lower()
        matches = [i for i, item in enumerate(compact) if item == target or item.startswith(target + "(")]
        if len(matches) == 1:
            return matches[0]
    raise ValueError(f"missing unique column {names}; available={header}")


def history(path: Path) -> dict[str, Any]:
    header, rows = read_comsol_csv(path)
    columns = {
        "time": _column(header, "Time", "Time(s)", "t"),
        "enthalpy": _column(header, "enthalpyInvariant"),
        "tip": _column(header, "tipY"),
        "half_width": _column(header, "halfWidth"),
        "p_min": _column(header, "pMin"),
        "p_max": _column(header, "pMax"),
    }
    initial = rows[0][columns["enthalpy"]]
    scale = max(abs(initial), 1e-12)
    return {
        "header": header,
        "rows": rows,
        "columns": columns,
        "p_min": min(row[columns["p_min"]] for row in rows),
        "p_max": max(row[columns["p_max"]] for row in rows),
        "max_relative_enthalpy_drift": max(abs(row[columns["enthalpy"]] - initial) / scale for row in rows),
    }


def interpolate(hist: dict[str, Any], metric: str, target: float) -> float:
    rows = hist["rows"]
    ti = hist["columns"]["time"]
    yi = hist["columns"][metric]
    if target < rows[0][ti] - 1e-12 or target > rows[-1][ti] + 1e-12:
        raise ValueError(f"target time {target} outside [{rows[0][ti]}, {rows[-1][ti]}]")
    for left, right in zip(rows, rows[1:]):
        if left[ti] <= target <= right[ti]:
            if abs(right[ti] - left[ti]) <= 1e-15:
                return left[yi]
            weight = (target - left[ti]) / (right[ti] - left[ti])
            return left[yi] + weight * (right[yi] - left[yi])
    return rows[-1][yi]


def _phase_columns(header: list[str]) -> dict[float, int]:
    result: dict[float, int] = {}
    for index, value in enumerate(header):
        if not re.match(r"^(?:comp1\.)?p(?:\s|\(|@|$)", value.strip(), re.IGNORECASE):
            continue
        match = TIME_PATTERN.search(value)
        if not match:
            raise ValueError(f"phase column lacks explicit time: {value}")
        time_value = float(match.group(1))
        if time_value in result:
            raise ValueError(f"duplicate phase time {time_value}")
        result[time_value] = index
    if not result:
        raise ValueError("no phase-field columns")
    return result


def field_masks(path: Path, requested: list[tuple[float, str]], output: Path) -> None:
    header, rows = read_comsol_csv(path)
    xi = _column(header, "X")
    yi = _column(header, "Y")
    phase = _phase_columns(header)
    xs = sorted({row[xi] for row in rows})
    ys = sorted({row[yi] for row in rows})
    if len(rows) != len(xs) * len(ys) or len(xs) < 2 or len(ys) < 2:
        raise ValueError(f"incomplete regular grid in {path}")
    xmap = {value: i for i, value in enumerate(xs)}
    ymap = {value: i for i, value in enumerate(ys)}
    output.mkdir(parents=True, exist_ok=True)
    for target, filename in requested:
        actual = min(phase, key=lambda item: abs(item - target))
        if abs(actual - target) > 1e-8:
            raise ValueError(f"missing t={target} in {path}; available={sorted(phase)}")
        image = Image.new("L", (len(xs), len(ys)), 0)
        pixels = image.load()
        seen: set[tuple[int, int]] = set()
        for row in rows:
            point = (xmap[row[xi]], len(ys) - 1 - ymap[row[yi]])
            if point in seen:
                raise ValueError(f"duplicate grid point in {path}: {point}")
            seen.add(point)
            pixels[point[0], point[1]] = 255 if row[phase[actual]] >= 0.5 else 0
        image.resize((192, 192), Image.Resampling.NEAREST).save(output / filename)


def _mask(path: Path) -> list[list[bool]]:
    image = Image.open(path).convert("L").resize((192, 192), Image.Resampling.NEAREST)
    px = image.load()
    return [[px[x, y] >= 128 for x in range(192)] for y in range(192)]


def _contour(mask: list[list[bool]]) -> list[tuple[int, int]]:
    points = []
    for y in range(192):
        for x in range(192):
            if mask[y][x] and any(
                xx < 0 or yy < 0 or xx >= 192 or yy >= 192 or not mask[yy][xx]
                for xx, yy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            ):
                points.append((x, y))
    return points


def _distance_map(points: list[tuple[int, int]]) -> list[list[float]]:
    distance = [[float("inf")] * 192 for _ in range(192)]
    for x, y in points:
        distance[y][x] = 0.0
    diagonal = math.sqrt(2.0)
    for y in range(192):
        for x in range(192):
            value = distance[y][x]
            if x:
                value = min(value, distance[y][x - 1] + 1)
            if y:
                value = min(value, distance[y - 1][x] + 1)
                if x:
                    value = min(value, distance[y - 1][x - 1] + diagonal)
                if x < 191:
                    value = min(value, distance[y - 1][x + 1] + diagonal)
            distance[y][x] = value
    for y in range(191, -1, -1):
        for x in range(191, -1, -1):
            value = distance[y][x]
            if x < 191:
                value = min(value, distance[y][x + 1] + 1)
            if y < 191:
                value = min(value, distance[y + 1][x] + 1)
                if x:
                    value = min(value, distance[y + 1][x - 1] + diagonal)
                if x < 191:
                    value = min(value, distance[y + 1][x + 1] + diagonal)
            distance[y][x] = value
    return distance


def compare_masks(reference: Path, simulation: Path) -> dict[str, float]:
    ref = _mask(reference)
    sim = _mask(simulation)
    intersection = sum(ref[y][x] and sim[y][x] for y in range(192) for x in range(192))
    union = sum(ref[y][x] or sim[y][x] for y in range(192) for x in range(192))
    ref_contour, sim_contour = _contour(ref), _contour(sim)
    if not union or not ref_contour or not sim_contour:
        raise ValueError(f"empty comparison mask: {reference}, {simulation}")
    rd, sd = _distance_map(ref_contour), _distance_map(sim_contour)
    chamfer = 0.5 * (
        sum(rd[y][x] for x, y in sim_contour) / len(sim_contour)
        + sum(sd[y][x] for x, y in ref_contour) / len(ref_contour)
    )
    return {"iou": intersection / union, "normalized_chamfer": chamfer / 192.0}


def _error_count(case_dir: Path) -> int:
    count = 0
    for pattern in ("*.log", "slurm.*.out", "slurm.*.err"):
        for path in case_dir.glob(pattern):
            count += len(ERROR_PATTERN.findall(path.read_text(encoding="utf-8", errors="replace")))
    return count


def _relative(left: float, right: float) -> float:
    return abs(left - right) / max(abs(right), 1e-12)


def _properties(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            key, value = line.split("=", 1)
            result[key] = value
    return result


def _comparison_figure(manifest: dict[str, Any], reference: Path, masks: Path, output: Path) -> None:
    panel = 192
    label = 24
    canvas = Image.new("RGB", (6 * panel, 5 * (panel + label)), "white")
    draw = ImageDraw.Draw(canvas)
    for row, delta in enumerate(DELTA_CASES):
        items = [item for item in manifest["panels"] if math.isclose(float(item["delta"]), delta, abs_tol=1e-12)]
        for col, item in enumerate(items):
            source = Image.open(reference / item["source"]).convert("RGB").resize((panel, panel))
            simulation = Image.open(masks / item["mask"]).convert("RGB")
            x = 2 * col * panel
            y = row * (panel + label) + label
            canvas.paste(source, (x, y))
            canvas.paste(simulation, (x + panel, y))
            draw.text((x + 4, y - label + 5), f"paper d={delta:g}, t={float(item['time']):g}", fill="black")
            draw.text((x + panel + 4, y - label + 5), "COMSOL p>=0.5", fill="black")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)


def analyze(suite: Path, job_status_path: Path, reference: Path, output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    statuses = json.loads(job_status_path.read_text(encoding="utf-8"))
    histories: dict[str, dict[str, Any]] = {}
    runs = []
    errors = 0
    for case in REQUIRED_CASES:
        status = statuses.get(case)
        if not isinstance(status, dict) or status.get("state") != "COMPLETED" or str(status.get("exit_code")) != "0:0":
            raise ValueError(f"unclean Slurm job: {case}: {status}")
        case_dir = suite / case
        for suffix in ("global.csv", "fields.csv", "comsol_batch.log", "manifest.sha256"):
            artifact = case_dir / f"{case}_{suffix}"
            if not artifact.is_file() or artifact.stat().st_size == 0:
                raise ValueError(f"missing raw artifact: {artifact}")
        histories[case] = history(case_dir / f"{case}_global.csv")
        errors += _error_count(case_dir)
        runs.append({
            "id": case,
            "job_id": str(status["job_id"]),
            "status": "complete",
            "state": status["state"],
            "exit_code": status["exit_code"],
            "elapsed": status["elapsed"],
            "parameters": _properties(case_dir / "case.properties"),
            "raw_outputs": [f"raw/comsol_suite/{case}/{case}_global.csv", f"raw/comsol_suite/{case}/{case}_fields.csv"],
            "logs": [f"raw/comsol_suite/{case}/{case}_comsol_batch.log", f"raw/comsol_suite/{case}/slurm.{status['job_id']}.out", f"raw/comsol_suite/{case}/slurm.{status['job_id']}.err"],
            "remote_solved_mph": status["solved_mph"],
            "remote_solved_mph_bytes": status["solved_mph_bytes"],
            "remote_solved_mph_sha256": status["solved_mph_sha256"],
        })

    reference_manifest = json.loads((reference / "manifest.json").read_text(encoding="utf-8"))
    masks = output / "figures" / "simulation_masks"
    for delta, case in DELTA_CASES.items():
        requested = [
            (float(item["time"]), str(item["mask"]))
            for item in reference_manifest["panels"]
            if math.isclose(float(item["delta"]), delta, abs_tol=1e-12)
        ]
        field_masks(suite / case / f"{case}_fields.csv", requested, masks)
    panels = []
    for item in reference_manifest["panels"]:
        result = compare_masks(reference / item["mask"], masks / item["mask"])
        panels.append({"delta": item["delta"], "time": item["time"], **result})
    figure_metrics = {
        "mean_iou": sum(item["iou"] for item in panels) / len(panels),
        "normalized_chamfer": sum(item["normalized_chamfer"] for item in panels) / len(panels),
        "panels": panels,
    }
    (output / "figures").mkdir(parents=True, exist_ok=True)
    (output / "figures" / "fig7_metrics.json").write_text(json.dumps(figure_metrics, indent=2) + "\n", encoding="utf-8")
    _comparison_figure(reference_manifest, reference, masks, output / "figures" / "fig7_paper_vs_comsol.png")

    baseline = histories["control_delta020"]
    seed = [
        interpolate(histories["seed_small"], "tip", 0.8),
        interpolate(baseline, "tip", 0.8),
        interpolate(histories["seed_large"], "tip", 0.8),
    ]
    d0 = interpolate(histories["delta000"], "tip", 1.4)
    d5 = interpolate(histories["delta050"], "tip", 1.4)
    d5_width = interpolate(histories["delta050"], "half_width", 1.4)
    final_mph = output / "final_mph" / "delta020_solved.mph"
    if not final_mph.is_file() or final_mph.stat().st_size <= 1_000_000:
        raise ValueError(f"missing downloaded authoritative final MPH: {final_mph}")
    metrics = {
        "artifacts": {"final_mph_bytes": final_mph.stat().st_size},
        "quality": {
            "comsol_error_count": errors,
            "p_min": min(item["p_min"] for item in histories.values()),
            "p_max": max(item["p_max"] for item in histories.values()),
            "max_relative_enthalpy_drift": max(item["max_relative_enthalpy_drift"] for item in histories.values()),
        },
        "convergence": {
            "mesh_tip_relative_difference": _relative(interpolate(baseline, "tip", 0.8), interpolate(histories["mesh_fine"], "tip", 0.8)),
            "timestep_tip_relative_difference": _relative(interpolate(baseline, "tip", 0.8), interpolate(histories["timestep_fine"], "tip", 0.8)),
            "seed_tip_relative_range": (max(seed) - min(seed)) / max(abs(seed[1]), 1e-12),
        },
        "paper_trend": {
            "delta050_to_delta000_tip_ratio": d5 / max(d0, 1e-12),
            "delta050_vertical_to_horizontal_extent_ratio": d5 / max(d5_width, 1e-12),
        },
        "paper_figure": {
            "fig7_mean_iou": figure_metrics["mean_iou"],
            "fig7_normalized_chamfer": figure_metrics["normalized_chamfer"],
        },
    }
    run_manifest = {
        "solver": "COMSOL Multiphysics 6.4 Build 293",
        "model_sha256": "5595a5eff4f3a384e06ef0d55ea0875e5786ddcb3566503d0cf54b8bfc0783af",
        "remote_suite": "~/paperengine_kobayashi1993_20260826/suite_attempt4",
        "runs": runs,
        "authoritative_final_mph": "final_mph/delta020_solved.mph",
    }
    return run_manifest, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--job-status", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_manifest, metrics = analyze(args.suite, args.job_status, args.reference, args.output)
    (args.output / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2) + "\n", encoding="utf-8")
    (args.output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
