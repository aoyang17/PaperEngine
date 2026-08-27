#!/usr/bin/env python3
"""Create dependency-free SVG diagnostics from distributedECM COMSOL exports."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import re
from typing import Iterable


def read_comsol_csv(path: Path) -> tuple[list[str], list[list[float]]]:
    header: list[str] | None = None
    rows: list[list[float]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("%"):
                candidate = line[1:].lstrip()
                if "," in candidate:
                    header = next(csv.reader([candidate]))
                continue
            values = next(csv.reader([line]))
            try:
                rows.append([float(value) for value in values])
            except ValueError as exc:
                raise ValueError(f"nonnumeric COMSOL row in {path}: {values[:4]}") from exc
    if header is None or not rows:
        raise ValueError(f"missing header or data in {path}")
    if len(header) != len(rows[0]):
        raise ValueError(f"header/data width mismatch in {path}: {len(header)} != {len(rows[0])}")
    return [item.strip() for item in header], rows


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def column_index(header: list[str], name: str, *, latest: bool = False) -> int:
    target = normalized(name)
    matches = [index for index, label in enumerate(header) if normalized(label).startswith(target)]
    if not matches:
        raise KeyError(f"column {name!r} not found in {header}")
    return matches[-1] if latest else matches[0]


def field_columns(header: list[str], expression: str) -> list[int]:
    target = normalized(expression)
    return [index for index, label in enumerate(header) if normalized(label).startswith(target)]


def final_field(header: list[str], rows: list[list[float]], expression: str) -> list[tuple[float, float, float]]:
    ix = column_index(header, "X")
    iy = column_index(header, "Y")
    candidates = field_columns(header, expression)
    if not candidates:
        raise KeyError(f"field {expression!r} absent")
    iv = candidates[-1]
    return [(row[ix], row[iy], row[iv]) for row in rows if math.isfinite(row[iv])]


def binned(points: list[tuple[float, float, float]], nx: int = 50, ny: int = 40):
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    sums = [[0.0 for _ in range(nx)] for _ in range(ny)]
    counts = [[0 for _ in range(nx)] for _ in range(ny)]
    for x, y, value in points:
        i = min(nx - 1, max(0, int((x - xmin) / max(xmax - xmin, 1e-30) * nx)))
        j = min(ny - 1, max(0, int((y - ymin) / max(ymax - ymin, 1e-30) * ny)))
        sums[j][i] += value
        counts[j][i] += 1
    grid: list[list[float | None]] = []
    for j in range(ny):
        grid.append([sums[j][i] / counts[j][i] if counts[j][i] else None for i in range(nx)])
    return grid, (xmin, xmax, ymin, ymax)


def color(value: float, lower: float, upper: float) -> str:
    stops = ((0.0, (48, 18, 59)), (0.25, (50, 103, 164)), (0.5, (34, 168, 132)),
             (0.75, (190, 220, 66)), (1.0, (252, 242, 38)))
    ratio = 0.5 if upper <= lower else min(1.0, max(0.0, (value - lower) / (upper - lower)))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if ratio <= b:
            f = (ratio - a) / (b - a)
            rgb = tuple(round(ca[k] + f * (cb[k] - ca[k])) for k in range(3))
            return "#%02x%02x%02x" % rgb
    return "#fcf226"


def finite_values(grid: list[list[float | None]]) -> list[float]:
    return [value for row in grid for value in row if value is not None and math.isfinite(value)]


def heatmap_panel(grid, x: int, y: int, width: int, height: int, title: str,
                  lower: float, upper: float, bounds, unit: str) -> list[str]:
    ny, nx = len(grid), len(grid[0])
    cell_w, cell_h = width / nx, height / ny
    parts = [f'<text x="{x}" y="{y-18}" class="title">{title}</text>',
             f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="#eee"/>']
    for j, row in enumerate(grid):
        for i, value in enumerate(row):
            if value is None:
                continue
            py = y + height - (j + 1) * cell_h
            parts.append(
                f'<rect x="{x+i*cell_w:.2f}" y="{py:.2f}" width="{cell_w+0.2:.2f}" '
                f'height="{cell_h+0.2:.2f}" fill="{color(value, lower, upper)}"/>'
            )
    xmin, xmax, ymin, ymax = bounds
    parts.extend([
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" class="frame"/>',
        f'<text x="{x}" y="{y+height+22}" class="axis">0</text>',
        f'<text x="{x+width-30}" y="{y+height+22}" class="axis">{(xmax-xmin)*1000:.0f} mm</text>',
        f'<text x="{x-5}" y="{y+height+38}" class="axis">y: 0–{(ymax-ymin)*1000:.0f} mm</text>',
    ])
    legend_y = y + height + 52
    for i in range(100):
        parts.append(f'<rect x="{x+i*width/100:.2f}" y="{legend_y}" width="{width/100+0.2:.2f}" '
                     f'height="12" fill="{color(lower+(upper-lower)*i/99, lower, upper)}"/>')
    parts.extend([
        f'<text x="{x}" y="{legend_y+28}" class="axis">{lower:.3g}</text>',
        f'<text x="{x+width/2-24}" y="{legend_y+28}" class="axis">{unit}</text>',
        f'<text x="{x+width-45}" y="{legend_y+28}" class="axis">{upper:.3g}</text>',
    ])
    return parts


def write_heatmaps(output: Path, uniform_points, heterogeneous_points, resistance_points) -> None:
    uniform_grid, bounds = binned(uniform_points)
    hetero_grid, _ = binned(heterogeneous_points)
    resistance_grid, _ = binned(resistance_points)
    current_values = finite_values(uniform_grid) + finite_values(hetero_grid)
    current_min, current_max = min(current_values), max(current_values)
    resistance_values = finite_values(resistance_grid)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="570" viewBox="0 0 1200 570">',
             '<style>text{font-family:Arial,sans-serif;fill:#202124}.title{font-size:17px;font-weight:700}'
             '.axis{font-size:12px}.frame{fill:none;stroke:#333;stroke-width:1}</style>',
             '<rect width="1200" height="570" fill="white"/>',
             '<text x="36" y="34" style="font-size:23px;font-weight:700">Distributed ECM — final-time boundary fields</text>']
    parts += heatmap_panel(uniform_grid, 36, 88, 340, 340, "Uniform impedance: local C-rate",
                           current_min, current_max, bounds, "local C-rate")
    parts += heatmap_panel(hetero_grid, 430, 88, 340, 340, "Nonuniform impedance: local C-rate",
                           current_min, current_max, bounds, "local C-rate")
    parts += heatmap_panel(resistance_grid, 824, 88, 340, 340, "Nonuniform case: resistance factor",
                           min(resistance_values), max(resistance_values), bounds, "R/R̄")
    parts.append('</svg>')
    output.write_text("\n".join(parts), encoding="utf-8")


def profile(points: list[tuple[float, float, float]], bins: int = 40) -> list[tuple[float, float]]:
    ymin = min(point[1] for point in points)
    ymax = max(point[1] for point in points)
    sums = [0.0] * bins
    counts = [0] * bins
    for _, y, value in points:
        index = min(bins - 1, max(0, int((y - ymin) / max(ymax - ymin, 1e-30) * bins)))
        sums[index] += value
        counts[index] += 1
    return [((ymin + (index + 0.5) / bins * (ymax - ymin)) * 1000, sums[index] / counts[index])
            for index in range(bins) if counts[index]]


def polyline(points, xmin, xmax, ymin, ymax, x0=80, y0=60, width=760, height=340) -> str:
    coords = []
    for x, y in points:
        px = x0 + (x - xmin) / max(xmax - xmin, 1e-30) * width
        py = y0 + height - (y - ymin) / max(ymax - ymin, 1e-30) * height
        coords.append(f"{px:.2f},{py:.2f}")
    return " ".join(coords)


def write_profile(output: Path, uniform_points, heterogeneous_points) -> None:
    uniform = profile(uniform_points)
    heterogeneous = profile(heterogeneous_points)
    all_points = uniform + heterogeneous
    xmin, xmax = min(x for x, _ in all_points), max(x for x, _ in all_points)
    ymin, ymax = min(y for _, y in all_points), max(y for _, y in all_points)
    pad = max((ymax - ymin) * 0.08, 0.01)
    ymin, ymax = ymin - pad, ymax + pad
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="920" height="500" viewBox="0 0 920 500">
<style>text{{font-family:Arial,sans-serif;fill:#202124}}.axis{{stroke:#333;stroke-width:1}}.grid{{stroke:#ddd;stroke-width:1}}</style>
<rect width="920" height="500" fill="white"/><text x="80" y="32" style="font-size:22px;font-weight:700">Final-time current profile along impedance gradient</text>
<line x1="80" y1="400" x2="840" y2="400" class="axis"/><line x1="80" y1="60" x2="80" y2="400" class="axis"/>
<polyline points="{polyline(uniform,xmin,xmax,ymin,ymax)}" fill="none" stroke="#3465a4" stroke-width="3"/>
<polyline points="{polyline(heterogeneous,xmin,xmax,ymin,ymax)}" fill="none" stroke="#d1495b" stroke-width="3"/>
<text x="350" y="465">y position (mm): {xmin:.1f} → {xmax:.1f}</text><text x="12" y="235" transform="rotate(-90 12 235)">mean local C-rate</text>
<text x="650" y="82" fill="#3465a4">— uniform</text><text x="650" y="106" fill="#d1495b">— nonuniform</text>
<text x="80" y="420">{ymin:.3g}</text><text x="800" y="420">{ymax:.3g}</text></svg>'''
    output.write_text(svg, encoding="utf-8")


def final_global(path: Path) -> tuple[list[str], list[float]]:
    header, rows = read_comsol_csv(path)
    return header, rows[-1]


def value(header: list[str], row: list[float], expression: str) -> float:
    return row[column_index(header, expression)]


def summarize(results: Path, output: Path) -> dict:
    metric_columns = {
        "C_rate": 1,
        "hetero_amp": 2,
        "load_factor": 3,
        "imposed_current_A": 4,
        "integrated_boundary_current_A": 5,
        "mean_local_C_rate": 6,
        "min_local_C_rate": 7,
        "max_local_C_rate": 8,
        "current_cv": 9,
        "min_R_factor": 10,
        "max_R_factor": 11,
        "terminal_voltage_V": 12,
        "mean_layer_voltage_V": 13,
        "mean_boundary_SOC": 14,
        "min_boundary_SOC": 15,
        "max_boundary_SOC": 16,
    }
    cases = {}
    for name in ("uniform", "heterogeneous"):
        header, row = final_global(results / name / f"{name}_global.csv")
        if len(header) != 17 or len(row) != 17:
            raise ValueError(f"unexpected global metric schema for {name}: {header}")
        cases[name] = {
            "time_s": row[0],
            **{metric: row[index] for metric, index in metric_columns.items()},
        }
        cases[name]["current_balance_relative_error"] = abs(
            cases[name]["integrated_boundary_current_A"] / cases[name]["imposed_current_A"] - 1
        )
    uniform = cases["uniform"]
    heterogeneous = cases["heterogeneous"]
    summary = {
        "cases": cases,
        "comparison": {
            "current_cv_ratio": heterogeneous["current_cv"] / max(uniform["current_cv"], 1e-30),
            "peak_local_C_rate_increase": heterogeneous["max_local_C_rate"] - uniform["max_local_C_rate"],
            "terminal_voltage_shift_V": heterogeneous["terminal_voltage_V"] - uniform["terminal_voltage_V"],
        },
    }
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def write_markdown(path: Path, summary: dict) -> None:
    u = summary["cases"]["uniform"]
    h = summary["cases"]["heterogeneous"]
    c = summary["comparison"]
    text = f"""# Distributed ECM simulation summary

| Metric at {h['time_s']:.0f} s | Uniform | Nonuniform |
|---|---:|---:|
| Integrated boundary current (A) | {u['integrated_boundary_current_A']:.6g} | {h['integrated_boundary_current_A']:.6g} |
| Current-balance relative error | {u['current_balance_relative_error']:.3e} | {h['current_balance_relative_error']:.3e} |
| Mean local C-rate | {u['mean_local_C_rate']:.6g} | {h['mean_local_C_rate']:.6g} |
| Min / max local C-rate | {u['min_local_C_rate']:.6g} / {u['max_local_C_rate']:.6g} | {h['min_local_C_rate']:.6g} / {h['max_local_C_rate']:.6g} |
| Current coefficient of variation | {u['current_cv']:.6g} | {h['current_cv']:.6g} |
| Terminal voltage (V) | {u['terminal_voltage_V']:.6g} | {h['terminal_voltage_V']:.6g} |
| Mean boundary SOC | {u['mean_boundary_SOC']:.6g} | {h['mean_boundary_SOC']:.6g} |

The nonuniform/uniform current-CV ratio is **{c['current_cv_ratio']:.4g}**,
the peak local C-rate changes by **{c['peak_local_C_rate_increase']:+.4g}**, and
the terminal voltage changes by **{c['terminal_voltage_shift_V']:+.4g} V**.

See `current_distribution.svg` and `current_profile.svg` for spatial diagnostics.
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fields = {}
    for name in ("uniform", "heterogeneous"):
        header, rows = read_comsol_csv(args.results / name / f"{name}_fields.csv")
        fields[name] = {
            "current": final_field(header, rows, "C_rate_loc"),
            "resistance": final_field(header, rows, "R_factor"),
        }
    write_heatmaps(args.output / "current_distribution.svg", fields["uniform"]["current"],
                   fields["heterogeneous"]["current"], fields["heterogeneous"]["resistance"])
    write_profile(args.output / "current_profile.svg", fields["uniform"]["current"],
                  fields["heterogeneous"]["current"])
    summary = summarize(args.results, args.output / "summary.json")
    write_markdown(args.output / "analysis_summary.md", summary)


if __name__ == "__main__":
    main()
