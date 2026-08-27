#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from paper_engine.simulation_reproduction.plotting import write_svg_line_plot
from paper_engine.simulation_reproduction.timeseries import read_numeric_csv


def _series(path: Path, label: str, color: str) -> dict[str, object]:
    rows = read_numeric_csv(path)
    stride = max(1, len(rows) // 500)
    rows = rows[::stride]
    return {
        "label": label,
        "color": color,
        "x": [row["time_tau1"] for row in rows],
        "y": [row["effective_radius_nm"] for row in rows],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reference = read_numeric_csv(args.reference)
    series = [
        _series(args.baseline, "topology on", "#15803d"),
        _series(args.control, "topology off", "#dc2626"),
        {
            "label": "paper Figure 6b",
            "color": "#111827",
            "x": [row["time_tau1"] for row in reference],
            "y": [row["effective_radius_nm"] for row in reference],
        },
    ]
    write_svg_line_plot(
        args.output,
        series,
        title="Laghmach 2015: effective radius at 303 K, lambda=4",
        x_label="t / tau1",
        y_label="effective radius (nm)",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
