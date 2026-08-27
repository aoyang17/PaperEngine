#!/usr/bin/env python3
"""Compare COMSOL p>=0.5 masks with source-derived Kobayashi Fig. 7 masks."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image


def _mask(path: Path) -> list[list[bool]]:
    image = Image.open(path).convert("L").resize((192, 192), Image.Resampling.NEAREST)
    pixels = image.load()
    return [[pixels[x, y] >= 128 for x in range(192)] for y in range(192)]


def _contour(mask: list[list[bool]]) -> list[tuple[int, int]]:
    height = len(mask)
    width = len(mask[0])
    result = []
    for y in range(height):
        for x in range(width):
            if not mask[y][x]:
                continue
            if any(
                xx < 0 or yy < 0 or xx >= width or yy >= height or not mask[yy][xx]
                for xx, yy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            ):
                result.append((x, y))
    return result


def _distance_map(points: list[tuple[int, int]], width: int, height: int) -> list[list[float]]:
    distance = [[float("inf")] * width for _ in range(height)]
    for x, y in points:
        distance[y][x] = 0.0
    diagonal = math.sqrt(2.0)
    for y in range(height):
        for x in range(width):
            value = distance[y][x]
            if x:
                value = min(value, distance[y][x - 1] + 1.0)
            if y:
                value = min(value, distance[y - 1][x] + 1.0)
                if x:
                    value = min(value, distance[y - 1][x - 1] + diagonal)
                if x + 1 < width:
                    value = min(value, distance[y - 1][x + 1] + diagonal)
            distance[y][x] = value
    for y in range(height - 1, -1, -1):
        for x in range(width - 1, -1, -1):
            value = distance[y][x]
            if x + 1 < width:
                value = min(value, distance[y][x + 1] + 1.0)
            if y + 1 < height:
                value = min(value, distance[y + 1][x] + 1.0)
                if x:
                    value = min(value, distance[y + 1][x - 1] + diagonal)
                if x + 1 < width:
                    value = min(value, distance[y + 1][x + 1] + diagonal)
            distance[y][x] = value
    return distance


def compare(reference_path: Path, simulation_path: Path) -> dict[str, float]:
    reference = _mask(reference_path)
    simulation = _mask(simulation_path)
    intersection = sum(
        reference[y][x] and simulation[y][x] for y in range(192) for x in range(192)
    )
    union = sum(reference[y][x] or simulation[y][x] for y in range(192) for x in range(192))
    if union == 0:
        raise ValueError("both masks are empty")
    ref_contour = _contour(reference)
    sim_contour = _contour(simulation)
    if not ref_contour or not sim_contour:
        raise ValueError("mask contour is empty")
    ref_distance = _distance_map(ref_contour, 192, 192)
    sim_distance = _distance_map(sim_contour, 192, 192)
    chamfer_pixels = 0.5 * (
        sum(ref_distance[y][x] for x, y in sim_contour) / len(sim_contour)
        + sum(sim_distance[y][x] for x, y in ref_contour) / len(ref_contour)
    )
    return {"iou": intersection / union, "normalized_chamfer": chamfer_pixels / 192.0}


def compare_suite(reference_dir: Path, simulation_dir: Path) -> dict[str, object]:
    manifest = json.loads((reference_dir / "manifest.json").read_text(encoding="utf-8"))
    panels = []
    for item in manifest["panels"]:
        name = str(item["mask"])
        result = compare(reference_dir / name, simulation_dir / name)
        panels.append({"delta": item["delta"], "time": item["time"], **result})
    return {
        "mean_iou": sum(item["iou"] for item in panels) / len(panels),
        "normalized_chamfer": sum(item["normalized_chamfer"] for item in panels) / len(panels),
        "panels": panels,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--simulation-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare_suite(args.reference_dir, args.simulation_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
