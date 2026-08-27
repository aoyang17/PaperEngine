#!/usr/bin/env python3
"""Create auditable final-field maps from a reduced-reference NPZ artifact."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from paper_engine.simulation_reproduction.plotting import write_svg_heatmap
from reference_solver import State, _topological_energy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fields", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--grid-nm", type=float, default=1.0)
    parser.add_argument("--lambda-topo-pa", type=float, default=0.611e6)
    parser.add_argument("--mu-topo-pa", type=float, default=0.15275e6)
    parser.add_argument("--stride", type=int, default=2)
    args = parser.parse_args()
    if args.stride < 1:
        raise ValueError("stride must be positive")

    data = np.load(args.fields)
    state = State(theta=data["theta"], utx=data["utx"], uty=data["uty"])
    energy = _topological_energy(
        state,
        args.grid_nm,
        args.lambda_topo_pa,
        args.mu_topo_pa,
    )
    # Log scaling exposes the full interfacial belt without hiding lower-energy
    # parts of the ring behind its few peak cells.
    log_energy = np.log10(np.maximum(energy, 1.0))
    extent = (-100.0, 100.0, -100.0, 100.0)
    args.output_directory.mkdir(parents=True, exist_ok=True)
    theta_path = write_svg_heatmap(
        args.output_directory / "final_theta.svg",
        state.theta[:: args.stride, :: args.stride].tolist(),
        title="Reduced reference: final phase field",
        x_label="x (nm)",
        y_label="y (nm)",
        value_label="theta",
        extent=extent,
    )
    energy_path = write_svg_heatmap(
        args.output_directory / "final_topological_energy.svg",
        log_energy[:: args.stride, :: args.stride].tolist(),
        title="Reduced reference: interfacial topological-energy belt",
        x_label="x (nm)",
        y_label="y (nm)",
        value_label="log10(J/m3)",
        extent=extent,
    )
    print(theta_path)
    print(energy_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
