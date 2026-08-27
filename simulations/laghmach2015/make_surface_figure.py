#!/usr/bin/env python3
"""Plot elastic surface tension against interface displacement for two nuclei."""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from paper_engine.simulation_reproduction.plotting import write_svg_line_plot
from paper_engine.simulation_reproduction.timeseries import read_numeric_csv


def _series(path: Path, label: str, color: str) -> dict[str, object]:
    rows = read_numeric_csv(path)
    radius0 = rows[0]["effective_radius_nm"]
    return {
        "label": label,
        "color": color,
        "x": [row["effective_radius_nm"] - radius0 for row in rows],
        "y": [row["elastic_surface_tension_J_m2"] for row in rows],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rn5", type=Path, required=True)
    parser.add_argument("--rn9", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rn5 = _series(args.rn5, "reduced model Rn=5 nm", "#2563eb")
    rn9 = _series(args.rn9, "reduced model Rn=9 nm", "#dc2626")
    max_displacement = min(max(rn5["x"]), max(rn9["x"]))  # type: ignore[arg-type]
    displacement = [max_displacement * index / 100 for index in range(101)]
    paper = {
        "label": "paper fit A exp(B r)",
        "color": "#111827",
        "x": displacement,
        "y": [6.7359e-4 * math.exp(0.308574 * value) for value in displacement],
    }
    write_svg_line_plot(
        args.output,
        [rn5, rn9, paper],
        title="Laghmach 2015: elastic surface tension and nucleus-size memory",
        x_label="interface displacement r (nm)",
        y_label="elastic surface tension (J/m2)",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
