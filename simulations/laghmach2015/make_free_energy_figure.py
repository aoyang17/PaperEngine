#!/usr/bin/env python3
"""Reproduce the qualitative bulk-free-energy curves in paper Figure 2."""
from __future__ import annotations

import argparse
from pathlib import Path

from paper_engine.simulation_reproduction.plotting import write_svg_line_plot


TM0_K = 303.0
NSEG = 95.0
HM_J_MOL = 4.986e3
RGAS = 8.31446261815324
FSCALE_J_M3 = 37.03e6
GAMMA_J_M3 = 169.7e6


def g(theta: float) -> float:
    return 1.0 - theta * theta * (3.0 - 2.0 * theta)


def trace_e_2d(stretch: float) -> float:
    """Tr[(F.T F-I)/2] for incompressible F=diag(lambda,1/lambda)."""
    return 0.5 * (stretch * stretch + stretch ** -2 - 2.0)


def normalized_bulk_energy(theta: float, temperature_k: float, stretch: float) -> float:
    thermal = HM_J_MOL / (RGAS * TM0_K) * (TM0_K - temperature_k) / TM0_K
    elastic = temperature_k / (NSEG * TM0_K) * trace_e_2d(stretch)
    barrier = GAMMA_J_M3 / FSCALE_J_M3 * theta**2 * (1.0 - theta) ** 2 / 4.0
    return barrier + g(theta) * (thermal + elastic)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    theta = [-0.5 + 2.0 * index / 500 for index in range(501)]
    colors = {
        (298, 1): "#dc2626",
        (298, 4): "#f87171",
        (303, 1): "#111827",
        (303, 4): "#6b7280",
        (308, 1): "#2563eb",
        (308, 4): "#60a5fa",
    }
    series = []
    for temperature_k in (298, 303, 308):
        for stretch in (1, 4):
            series.append(
                {
                    "label": f"T={temperature_k} K, lambda={stretch}",
                    "color": colors[(temperature_k, stretch)],
                    "x": theta,
                    "y": [
                        normalized_bulk_energy(value, temperature_k, stretch)
                        for value in theta
                    ],
                }
            )

    write_svg_line_plot(
        args.output,
        series,
        title="Laghmach 2015 Figure 2 cross-check: 2D bulk free energy",
        x_label="phase field theta",
        y_label="f_bulk / f_scale",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
