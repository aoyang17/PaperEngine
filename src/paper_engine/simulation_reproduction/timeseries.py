from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable
import math


def read_numeric_csv(path: str | Path, comment_prefix: str = "%") -> list[dict[str, float]]:
    """Read COMSOL/plain CSV while ignoring metadata comments and blank lines."""
    raw_lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    lines = [line for line in raw_lines if line.strip() and not line.lstrip().startswith(comment_prefix)]
    # COMSOL writes the DictReader header as a commented line (usually the
    # one containing ``Time``), followed by uncommented numeric rows.  Retain
    # that header instead of treating the first data row as column names.
    if lines and not any(token in lines[0].lower() for token in ("time", "radius", "theta", "x")):
        for line in raw_lines:
            stripped = line.lstrip()
            if stripped.startswith(comment_prefix) and "time" in stripped.lower() and "," in stripped:
                lines.insert(0, stripped[1:].lstrip())
                break
    if not lines:
        raise ValueError(f"no tabular data in {path}")
    reader = csv.DictReader(lines)
    if not reader.fieldnames:
        raise ValueError(f"missing CSV header in {path}")
    rows: list[dict[str, float]] = []
    for row_number, row in enumerate(reader, start=2):
        try:
            rows.append({str(key).strip(): float(value) for key, value in row.items() if key is not None and value is not None})
        except ValueError as exc:
            raise ValueError(f"non-numeric value in {path}, row {row_number}: {exc}") from exc
    if not rows:
        raise ValueError(f"no data rows in {path}")
    return rows


def least_squares_slope(x: Iterable[float], y: Iterable[float]) -> float:
    xs = list(x)
    ys = list(y)
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("slope requires equally sized sequences with at least two values")
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator == 0:
        raise ValueError("slope x values must not all be equal")
    return sum((a - mean_x) * (b - mean_y) for a, b in zip(xs, ys)) / denominator


def tail_slope(rows: list[dict[str, float]], x: str, y: str, fraction: float = 0.2) -> float:
    if not 0 < fraction <= 1:
        raise ValueError("tail fraction must be in (0, 1]")
    count = max(2, round(len(rows) * fraction))
    tail = rows[-count:]
    return least_squares_slope((row[x] for row in tail), (row[y] for row in tail))


def interpolate(rows: list[dict[str, float]], x: str, y: str, at: float) -> float:
    ordered = sorted(rows, key=lambda row: row[x])
    if at < ordered[0][x] or at > ordered[-1][x]:
        raise ValueError(f"interpolation point {at} is outside [{ordered[0][x]}, {ordered[-1][x]}]")
    for left, right in zip(ordered, ordered[1:]):
        if left[x] <= at <= right[x]:
            if right[x] == left[x]:
                return right[y]
            weight = (at - left[x]) / (right[x] - left[x])
            return left[y] + weight * (right[y] - left[y])
    return ordered[-1][y]


def normalized_rmse(actual: Iterable[float], expected: Iterable[float]) -> float:
    actual_values = list(actual)
    expected_values = list(expected)
    if len(actual_values) != len(expected_values) or not actual_values:
        raise ValueError("NRMSE requires equally sized non-empty sequences")
    scale = max(expected_values) - min(expected_values)
    if scale <= 0:
        scale = max(abs(value) for value in expected_values)
    if scale <= 0:
        raise ValueError("NRMSE normalization scale is zero")
    mse = sum((a - e) ** 2 for a, e in zip(actual_values, expected_values)) / len(actual_values)
    return math.sqrt(mse) / scale


def mean_normalized_rmse(actual: Iterable[float], expected: Iterable[float]) -> float:
    """RMSE normalized by mean absolute reference magnitude.

    This is preferable to range normalization for nearly flat observables such
    as a stress-relaxation curve whose small dynamic range is comparable to its
    figure-digitization uncertainty.
    """
    actual_values = list(actual)
    expected_values = list(expected)
    if len(actual_values) != len(expected_values) or not actual_values:
        raise ValueError("NRMSE requires equally sized non-empty sequences")
    scale = sum(abs(value) for value in expected_values) / len(expected_values)
    if scale <= 0:
        raise ValueError("NRMSE normalization scale is zero")
    mse = sum((a - e) ** 2 for a, e in zip(actual_values, expected_values)) / len(actual_values)
    return math.sqrt(mse) / scale


def time_to_fraction(rows: list[dict[str, float]], time: str, value: str, fraction: float = 0.95) -> float:
    if not 0 < fraction < 1:
        raise ValueError("fraction must be in (0, 1)")
    ordered = sorted(rows, key=lambda row: row[time])
    target = ordered[0][value] + fraction * (ordered[-1][value] - ordered[0][value])
    increasing = ordered[-1][value] >= ordered[0][value]
    for left, right in zip(ordered, ordered[1:]):
        crossed = left[value] <= target <= right[value] if increasing else left[value] >= target >= right[value]
        if crossed:
            if right[value] == left[value]:
                return right[time]
            weight = (target - left[value]) / (right[value] - left[value])
            return left[time] + weight * (right[time] - left[time])
    raise ValueError("curve does not cross requested fraction")
