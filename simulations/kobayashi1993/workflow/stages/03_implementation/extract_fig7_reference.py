#!/usr/bin/env python3
"""Extract reproducible binary crystal masks from the 15 panels of paper Fig. 7."""

from __future__ import annotations

from collections import deque
import hashlib
import json
from pathlib import Path

from PIL import Image


PDF_PAGE_INDEX = 7
RENDER_SCALE = 2.5
DELTAS = ("000", "005", "010", "020", "050")
TIMES = ("0.2", "0.8", "1.4")

# Normalized panel interiors, measured once against the immutable PDF page.
COLUMNS = ((0.2748, 0.4141), (0.4444, 0.5785), (0.6126, 0.7474))
ROWS = (
    (0.1259, 0.2228),
    (0.2762, 0.3741),
    (0.4201, 0.5180),
    (0.5651, 0.6624),
    (0.7153, 0.8127),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _render(pdf: Path) -> Image.Image:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # type: ignore[no-redef]
    with fitz.open(pdf) as document:
        pixmap = document[PDF_PAGE_INDEX].get_pixmap(
            matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE), alpha=False
        )
    return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def _dilate(mask: list[list[bool]]) -> list[list[bool]]:
    height = len(mask)
    width = len(mask[0])
    result = [[False] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            result[y][x] = any(
                mask[yy][xx]
                for yy in range(max(0, y - 1), min(height, y + 2))
                for xx in range(max(0, x - 1), min(width, x + 2))
            )
    return result


def _groups(indices: list[int]) -> list[tuple[int, int]]:
    if not indices:
        return []
    groups = []
    start = previous = indices[0]
    for value in indices[1:]:
        if value > previous + 1:
            groups.append((start, previous))
            start = value
        previous = value
    groups.append((start, previous))
    return groups


def _close_boundary_contacts(wall: list[list[bool]], margin: int) -> None:
    height = len(wall)
    width = len(wall[0])
    top_groups = _groups([x for x in range(width) if wall[margin][x]])
    for first, second in zip(top_groups[0::2], top_groups[1::2]):
        for x in range((first[0] + first[1]) // 2, (second[0] + second[1]) // 2 + 1):
            wall[0][x] = True
    for boundary_x, probe_x in ((0, margin), (width - 1, width - margin - 1)):
        side_groups = _groups([y for y in range(height) if wall[y][probe_x]])
        for first, second in zip(side_groups[0::2], side_groups[1::2]):
            for y in range((first[0] + first[1]) // 2, (second[0] + second[1]) // 2 + 1):
                wall[y][boundary_x] = True


def _filled_crystal(panel: Image.Image) -> Image.Image:
    gray = panel.convert("L")
    width, height = gray.size
    pixels = gray.load()
    wall = [[pixels[x, y] < 175 for x in range(width)] for y in range(height)]
    # Remove the printed square frame; it is not a phase contour.
    margin = max(4, round(min(width, height) * 0.025))
    for y in range(height):
        for x in range(width):
            if x < margin or x >= width - margin or y < margin or y >= height - margin:
                wall[y][x] = False
    wall = _dilate(wall)
    _close_boundary_contacts(wall, margin)
    # The crystal is rooted at the adiabatic bottom wall; close only that edge.
    for x in range(width):
        wall[height - 1][x] = True

    outside = [[False] * width for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        if not wall[0][x]:
            queue.append((x, 0))
    for y in range(height - 1):
        for x in (0, width - 1):
            if not wall[y][x]:
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        if outside[y][x] or wall[y][x]:
            continue
        outside[y][x] = True
        for xx, yy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= xx < width and 0 <= yy < height and not outside[yy][xx] and not wall[yy][xx]:
                queue.append((xx, yy))

    output = Image.new("L", (width, height), 0)
    out = output.load()
    for y in range(height):
        for x in range(width):
            out[x, y] = 255 if wall[y][x] or not outside[y][x] else 0
    return output.resize((192, 192), Image.Resampling.NEAREST)


def extract(pdf_path: Path, output_dir: Path) -> dict[str, object]:
    pdf = pdf_path.expanduser().resolve()
    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    page = _render(pdf)
    width, height = page.size
    panels = []
    for row, delta in enumerate(DELTAS):
        y0, y1 = ROWS[row]
        for column, time_value in enumerate(TIMES):
            x0, x1 = COLUMNS[column]
            box = (
                round(x0 * width),
                round(y0 * height),
                round(x1 * width),
                round(y1 * height),
            )
            panel = page.crop(box)
            stem = f"delta{delta}_t{time_value.replace('.', 'p')}"
            panel_path = output / f"{stem}_source.png"
            mask_path = output / f"{stem}_mask.png"
            panel.save(panel_path)
            mask = _filled_crystal(panel)
            mask.save(mask_path)
            panels.append(
                {
                    "delta": float(f"0.{delta}"),
                    "time": float(time_value),
                    "crop_normalized": [x0, y0, x1, y1],
                    "source": panel_path.name,
                    "mask": mask_path.name,
                    "mask_solid_fraction": mask.histogram()[255] / (192 * 192),
                }
            )
    manifest = {
        "source_pdf": str(pdf),
        "source_pdf_sha256": _sha256(pdf),
        "pdf_page": PDF_PAGE_INDEX + 1,
        "render_scale": RENDER_SCALE,
        "mask_size": [192, 192],
        "method": "strip printed frame, threshold<175, one-pixel dilation, close crystal contacts, bottom closure, exterior flood fill",
        "panels": panels,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[5]
    extract(root / "paper" / "kobayashi1993.pdf", Path(__file__).with_name("reference_data") / "fig7")
