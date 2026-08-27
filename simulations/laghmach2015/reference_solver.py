#!/usr/bin/env python3
"""Transparent finite-difference cross-check for Laghmach et al. Eqs. 20/27.

This solver deliberately does not claim to reproduce Eq. 18. It keeps the
far-field incompressible Green strain fixed and is used to catch sign, unit,
transport, and initialization errors before the coupled COMSOL run.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time

import numpy as np

from paper_engine.simulation_reproduction.artifacts import RunArtifacts
from paper_engine.simulation_reproduction.spec import load_case_spec


@dataclass
class State:
    theta: np.ndarray
    utx: np.ndarray
    uty: np.ndarray


def _grad(a: np.ndarray, dx: float) -> tuple[np.ndarray, np.ndarray]:
    return (
        (np.roll(a, -1, axis=1) - np.roll(a, 1, axis=1)) / (2.0 * dx),
        (np.roll(a, -1, axis=0) - np.roll(a, 1, axis=0)) / (2.0 * dx),
    )


def _laplacian(a: np.ndarray, dx: float) -> np.ndarray:
    return (
        np.roll(a, -1, axis=0)
        + np.roll(a, 1, axis=0)
        + np.roll(a, -1, axis=1)
        + np.roll(a, 1, axis=1)
        - 4.0 * a
    ) / dx**2


def _upwind_advection(a: np.ndarray, vx: np.ndarray, vy: np.ndarray, dx: float) -> np.ndarray:
    """First-order monotone advection used only for the topology transport."""
    backward_x = (a - np.roll(a, 1, axis=1)) / dx
    forward_x = (np.roll(a, -1, axis=1) - a) / dx
    backward_y = (a - np.roll(a, 1, axis=0)) / dx
    forward_y = (np.roll(a, -1, axis=0) - a) / dx
    derivative_x = np.where(vx >= 0.0, backward_x, forward_x)
    derivative_y = np.where(vy >= 0.0, backward_y, forward_y)
    return vx * derivative_x + vy * derivative_y


def _topological_energy(state: State, dx: float, lam: float, mu: float) -> np.ndarray:
    dux_dx, dux_dy = _grad(state.utx, dx)
    duy_dx, duy_dy = _grad(state.uty, dx)
    exx = dux_dx
    eyy = duy_dy
    exy = 0.5 * (dux_dy + duy_dx)
    trace = exx + eyy
    return 0.5 * lam * trace**2 + mu * (exx**2 + eyy**2 + 2.0 * exy**2)


def _effective_radius(theta: np.ndarray, dx: float) -> float:
    area = float(np.sum(theta)) * dx**2
    return math.sqrt(area / math.pi)


def _plateau_slope(history: list[dict[str, float]]) -> float:
    tail = history[max(0, min(len(history) - 2, int(len(history) * 0.8))) :]
    if len(tail) < 2:
        return float("nan")
    t = np.asarray([row["time_tau1"] for row in tail])
    r = np.asarray([row["effective_radius_nm"] for row in tail])
    return float(np.polyfit(t, r, 1)[0])


def initialize(size_nm: float, dx_nm: float, radius_nm: float, width_nm: float) -> State:
    points = int(round(size_nm / dx_nm))
    if points < 8 or not math.isclose(points * dx_nm, size_nm, rel_tol=0, abs_tol=1e-9):
        raise ValueError("domain size must be an integer multiple of grid spacing")
    coordinates = (np.arange(points) + 0.5) * dx_nm - size_nm / 2.0
    xx, yy = np.meshgrid(coordinates, coordinates)
    radius = np.sqrt(xx**2 + yy**2)
    # Paper's diffuse circular nucleus; theta=1 inside and 0 outside.
    theta = 0.5 * (1.0 - np.tanh((radius - radius_nm) / (2.0 * math.sqrt(2.0) * width_nm)))
    theta[[0, -1], :] = 0.0
    theta[:, [0, -1]] = 0.0
    zeros = np.zeros_like(theta)
    return State(theta=theta, utx=zeros.copy(), uty=zeros.copy())


def run(
    parameters: dict,
    numerics: dict,
    *,
    topology: bool,
    grid_nm: float | None = None,
    final_time: float | None = None,
    transport_scheme: str | None = None,
    dt_tau1: float | None = None,
    progress=None,
) -> tuple[State, list[dict[str, float]], dict[str, float]]:
    width = float(parameters["interface_width_nm"])
    size_nm = 200.0
    dx_nm = float(grid_nm or numerics["baseline_grid_nm"])
    dx = dx_nm / width
    dt = float(dt_tau1 if dt_tau1 is not None else numerics["reference_dt_tau1"])
    scheme = str(transport_scheme or numerics.get("reference_transport_scheme", "isotropic_second_order"))
    if scheme not in {"isotropic_second_order", "upwind_stable"}:
        raise ValueError(f"unknown topology transport scheme: {scheme}")
    stop = float(final_time if final_time is not None else numerics["final_time_tau1"])
    output_every = max(1, round(float(numerics["output_interval_tau1"]) / dt))
    steps = math.ceil(stop / dt)
    state = initialize(size_nm, dx_nm, float(parameters["initial_radius_nm"]), width)

    temperature = float(parameters["temperature_K"])
    melting_temperature = float(parameters["Tm0_K"])
    stretch = float(parameters["stretch_lambda"])
    n_segments = float(parameters["n_segments"])
    hm = float(parameters["melting_enthalpy_J_mol"])
    gas_constant = float(parameters["gas_constant_J_mol_K"])
    fscale = float(parameters["free_energy_scale_J_m3"])
    gamma_barrier = float(parameters["Gamma_J_m3"]) / fscale
    barrier_coefficient = float(parameters["barrier_coefficient"])
    lam_topo = float(parameters["topological_lambda_Pa"])
    mu_topo = float(parameters["topological_mu_Pa"])
    alpha_cut = float(parameters["alpha_cut"])
    threshold = float(parameters["theta_threshold"])

    # Homogeneous incompressible 2-D deformation, F=diag(lambda, 1/lambda).
    trace_green = 0.5 * (stretch**2 + stretch ** -2 - 2.0)
    flory_drive = (
        hm / (gas_constant * melting_temperature) * (melting_temperature - temperature) / melting_temperature
        + temperature / (n_segments * melting_temperature) * trace_green
    )
    history: list[dict[str, float]] = []
    raw_min = float(state.theta.min())
    raw_max = float(state.theta.max())
    termination_reason = "final_time"
    completed_step = 0

    for step in range(steps + 1):
        completed_step = step
        if step % output_every == 0 or step == steps:
            energy = _topological_energy(state, dx, lam_topo, mu_topo)
            radius_nm = _effective_radius(state.theta, dx_nm)
            g_field = 1.0 - state.theta**2 * (3.0 - 2.0 * state.theta)
            total_topological_energy_J_m = float(np.sum(g_field * energy)) * (dx_nm * 1e-9) ** 2
            elastic_gamma = total_topological_energy_J_m / max(2.0 * math.pi * radius_nm * 1e-9, 1e-30)
            row = {
                "time_tau1": step * dt,
                "effective_radius_nm": radius_nm,
                "crystal_fraction": float(np.mean(state.theta >= threshold)),
                "mean_theta": float(state.theta.mean()),
                "max_topological_energy_J_m3": float(energy.max()),
                "total_topological_energy_J_m": total_topological_energy_J_m,
                "elastic_surface_tension_J_m2": elastic_gamma,
            }
            history.append(row)
            if progress is not None:
                progress(step, steps, row)
            if step > 0 and (not math.isfinite(radius_nm) or radius_nm < width):
                termination_reason = "crystal_melted"
                break
        if step == steps:
            break

        theta_x, theta_y = _grad(state.theta, dx)
        topo_energy = _topological_energy(state, dx, lam_topo, mu_topo) if topology else 0.0
        g_prime = 6.0 * state.theta * (state.theta - 1.0)
        theta_rate = gamma_barrier * (
            _laplacian(state.theta, dx)
            + barrier_coefficient * state.theta * (1.0 - state.theta) * (1.0 - 2.0 * state.theta)
        ) - g_prime * (flory_drive - topo_energy / fscale)

        next_theta = state.theta + dt * theta_rate
        raw_min = min(raw_min, float(next_theta.min()))
        raw_max = max(raw_max, float(next_theta.max()))
        # Tiny explicit-Euler overshoots are projected onto the physical field
        # interval, while raw extrema remain part of the quality metrics.
        state.theta = np.clip(next_theta, 0.0, 1.0)
        state.theta[[0, -1], :] = 0.0
        state.theta[:, [0, -1]] = 0.0

        if topology:
            denominator = theta_x**2 + theta_y**2 + alpha_cut
            vx = -theta_rate * theta_x / denominator
            vy = -theta_rate * theta_y / denominator
            if scheme == "isotropic_second_order":
                utx_x, utx_y = _grad(state.utx, dx)
                uty_x, uty_y = _grad(state.uty, dx)
                state.utx += dt * (vx - vx * utx_x - vy * utx_y)
                state.uty += dt * (vy - vx * uty_x - vy * uty_y)
            else:
                courant = float(np.max(np.abs(vx) + np.abs(vy))) * dt / dx
                substeps = max(1, math.ceil(courant / 0.45))
                transport_dt = dt / substeps
                for _ in range(substeps):
                    state.utx += transport_dt * (vx - _upwind_advection(state.utx, vx, vy, dx))
                    state.uty += transport_dt * (vy - _upwind_advection(state.uty, vx, vy, dx))
            state.utx[[0, -1], :] = 0.0
            state.utx[:, [0, -1]] = 0.0
            state.uty[[0, -1], :] = 0.0
            state.uty[:, [0, -1]] = 0.0

    diagnostics = {
        "raw_theta_min": raw_min,
        "raw_theta_max": raw_max,
        "final_effective_radius_nm": history[-1]["effective_radius_nm"],
        "final_radius_slope_nm_per_tau1": _plateau_slope(history),
        "flory_drive": flory_drive,
        "trace_green_strain": trace_green,
        "temperature_K": temperature,
        "stretch_lambda": stretch,
        "barrier_coefficient": barrier_coefficient,
        "grid_nm": dx_nm,
        "dt_tau1": dt,
        "steps_requested": steps,
        "steps_completed": completed_step,
        "termination_reason": termination_reason,
        "transport_scheme": scheme,
    }
    return state, history, diagnostics


def _write_history(path: Path, rows: list[dict[str, float]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--grid-nm", type=float)
    parser.add_argument("--final-time", type=float)
    parser.add_argument("--dt", type=float, dest="dt_tau1")
    parser.add_argument("--topology", choices=("on", "off"), default="on")
    parser.add_argument("--transport-scheme", choices=("isotropic_second_order", "upwind_stable"))
    parser.add_argument("--temperature-K", type=float)
    parser.add_argument("--stretch", type=float)
    parser.add_argument("--initial-radius-nm", type=float)
    args = parser.parse_args()

    spec = load_case_spec(args.case)
    numerics = dict(spec.raw["numerics"])
    artifacts = RunArtifacts.create(args.output_root, spec.case_id, args.run_id)
    started = time.time()

    def progress(step, steps, row):
        print(
            f"step={step}/{steps} t={row['time_tau1']:.3f} "
            f"R={row['effective_radius_nm']:.4f} nm",
            flush=True,
        )

    parameters = dict(spec.parameters)
    if args.temperature_K is not None:
        parameters["temperature_K"] = args.temperature_K
    if args.stretch is not None:
        parameters["stretch_lambda"] = args.stretch
    if args.initial_radius_nm is not None:
        parameters["initial_radius_nm"] = args.initial_radius_nm
    state, history, diagnostics = run(
        parameters,
        numerics,
        topology=args.topology == "on",
        grid_nm=args.grid_nm,
        final_time=args.final_time,
        transport_scheme=args.transport_scheme,
        dt_tau1=args.dt_tau1,
        progress=progress,
    )
    _write_history(artifacts.path("raw", "radius_history.csv"), history)
    np.savez_compressed(
        artifacts.path("raw", "final_fields.npz"),
        theta=state.theta,
        utx=state.utx,
        uty=state.uty,
    )
    case_hash = hashlib.sha256(args.case.read_bytes()).hexdigest()
    simulation_input = {
        "source": spec.raw["source"],
        "model": spec.raw["model"],
        "parameters": parameters,
        "numerics": numerics,
    }
    simulation_input_hash = hashlib.sha256(
        json.dumps(simulation_input, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    result = {
        "scope": "reference cross-check; prescribed far-field strain; not Eq. 18 acceptance authority",
        "topology": args.topology,
        "diagnostics": diagnostics,
        "provenance": {
            "case_sha256": case_hash,
            "simulation_input_sha256": simulation_input_hash,
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "elapsed_seconds": time.time() - started,
        },
    }
    artifacts.write_json("raw", "result.json", result)
    print(json.dumps({"run_directory": str(artifacts.root), **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
