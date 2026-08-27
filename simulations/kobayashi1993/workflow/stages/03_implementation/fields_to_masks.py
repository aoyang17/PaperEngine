#!/usr/bin/env python3
"""Convert fail-closed COMSOL regular-grid phase-field CSV exports to Fig. 7 masks."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import re

from PIL import Image


DELTA_CASES = {
    0.0: "delta000",
    0.005: "delta005",
    0.01: "delta010",
    0.02: "delta020",
    0.05: "delta050",
}
TIME_PATTERN = re.compile(r"(?:^|[@,; ])t\s*=\s*([-+0-9.eE]+)", re.IGNORECASE)


def _tokens(line: str) -> list[str]:
    return [item.strip() for item in next(csv.reader([line.lstrip("% ")]))]


def _read_export(path: Path) -> tuple[list[str], list[list[float]]]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"missing COMSOL field export: {path}")
    headers: list[list[str]] = []
    rows: list[list[float]] = []
    for raw in path.read_text(encoding="utf-8-sig", errors="strict").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("%"):
            candidate = _tokens(line)
            if len(candidate) >= 3:
                headers.append(candidate)
            continue
        values = [float(item.strip()) for item in next(csv.reader([line]))]
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"non-finite field value in {path}")
        rows.append(values)
    if not rows:
        raise ValueError(f"COMSOL field export contains no numeric rows: {path}")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError(f"ragged COMSOL field export: {path}")
    matching = [header for header in headers if len(header) == width]
    if not matching:
        raise ValueError(f"missing full-width COMSOL column header: {path}")
    return matching[-1], rows


def _coord_column(header: list[str], name: str) -> int:
    matches = [index for index, value in enumerate(header) if value.strip().lower() == name]
    if len(matches) != 1:
        raise ValueError(f"expected one {name} coordinate column, found {len(matches)}")
    return matches[0]


def _phase_columns(header: list[str]) -> dict[float, int]:
    result: dict[float, int] = {}
    for index, value in enumerate(header):
        expression = value.strip()
        if not re.match(r"^(?:comp1\.)?p(?:\s|\(|@|$)", expression, re.IGNORECASE):
            continue
        match = TIME_PATTERN.search(expression)
        if not match:
            raise ValueError(f"phase column lacks an explicit time: {expression}")
        time_value = float(match.group(1))
        if time_value in result:
            raise ValueError(f"duplicate phase column at t={time_value}")
        result[time_value] = index
    if not result:
        raise ValueError("no time-labelled phase-field columns found")
    return result


def _nearest_time(columns: dict[float, int], target: float) -> int:
    actual = min(columns, key=lambda value: abs(value - target))
    if abs(actual - target) > 1e-8:
        raise ValueError(f"missing phase field at t={target}; available times: {sorted(columns)}")
    return columns[actual]


def export_masks(path: Path, requested: list[tuple[float, str]], output_dir: Path) -> None:
    header, rows = _read_export(path)
    x_column = _coord_column(header, "x")
    y_column = _coord_column(header, "y")
    phase_columns = _phase_columns(header)
    xs = sorted({row[x_column] for row in rows})
    ys = sorted({row[y_column] for row in rows})
    if len(xs) < 2 or len(ys) < 2 or len(rows) != len(xs) * len(ys):
        raise ValueError(
            f"expected a complete 2D regular grid, got rows={len(rows)}, nx={len(xs)}, ny={len(ys)}"
        )
    x_index = {value: index for index, value in enumerate(xs)}
    y_index = {value: index for index, value in enumerate(ys)}
    output_dir.mkdir(parents=True, exist_ok=True)
    for target_time, filename in requested:
        phase_column = _nearest_time(phase_columns, target_time)
        image = Image.new("L", (len(xs), len(ys)), 0)
        pixels = image.load()
        occupied: set[tuple[int, int]] = set()
        for row in rows:
            x_pos = x_index[row[x_column]]
            y_pos = len(ys) - 1 - y_index[row[y_column]]
            point = (x_pos, y_pos)
            if point in occupied:
                raise ValueError(f"duplicate regular-grid coordinate in {path}: {point}")
            occupied.add(point)
            pixels[x_pos, y_pos] = 255 if row[phase_column] >= 0.5 else 0
        image.resize((192, 192), Image.Resampling.NEAREST).save(output_dir / filename)


def build_suite(suite: Path, manifest_path: Path, output_dir: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    panels = manifest.get("panels")
    if not isinstance(panels, list):
        raise ValueError("Fig. 7 manifest lacks panels")
    for delta, case in DELTA_CASES.items():
        requested = [
            (float(item["time"]), str(item["mask"]))
            for item in panels
            if math.isclose(float(item["delta"]), delta, rel_tol=0.0, abs_tol=1e-12)
        ]
        if len(requested) != 3:
            raise ValueError(f"expected three Fig. 7 panels for delta={delta}")
        export_masks(suite / case / f"{case}_fields.csv", requested, output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build_suite(args.suite, args.manifest, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
