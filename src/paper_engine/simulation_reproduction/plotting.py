from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Mapping, Sequence


def _rgb_hex(red: int, green: int, blue: int) -> str:
    return f"#{red:02x}{green:02x}{blue:02x}"


def _heat_color(fraction: float) -> str:
    """Compact perceptually ordered blue-cyan-yellow heat-map palette."""
    fraction = min(1.0, max(0.0, fraction))
    stops = ((15, 23, 42), (29, 78, 216), (6, 182, 212), (250, 204, 21))
    position = fraction * (len(stops) - 1)
    index = min(int(position), len(stops) - 2)
    local = position - index
    start, end = stops[index], stops[index + 1]
    return _rgb_hex(*(round(a + local * (b - a)) for a, b in zip(start, end)))


def write_svg_heatmap(
    destination: str | Path,
    values: Sequence[Sequence[float]],
    *,
    title: str,
    x_label: str,
    y_label: str,
    value_label: str,
    extent: tuple[float, float, float, float] | None = None,
    width: int = 680,
    height: int = 620,
) -> Path:
    """Write a dependency-free SVG heat map for a rectangular numeric grid."""
    rows = [[float(value) for value in row] for row in values]
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError("heat-map values must be a non-empty rectangular grid")
    flat = [value for row in rows for value in row]
    if any(not (-float("inf") < value < float("inf")) for value in flat):
        raise ValueError("heat-map values must be finite")
    minimum, maximum = min(flat), max(flat)
    if minimum == maximum:
        raise ValueError("heat-map range must be nonzero")
    xmin, xmax, ymin, ymax = extent or (0.0, float(len(rows[0])), 0.0, float(len(rows)))
    left, top = 82, 58
    plot_size = min(width - left - 94, height - top - 78)
    cell_width = plot_size / len(rows[0])
    cell_height = plot_size / len(rows)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="20">{escape(title)}</text>',
    ]
    for row_index, row in enumerate(reversed(rows)):
        y = top + row_index * cell_height
        for column_index, value in enumerate(row):
            fraction = (value - minimum) / (maximum - minimum)
            x = left + column_index * cell_width
            lines.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell_width+0.05:.2f}" '
                f'height="{cell_height+0.05:.2f}" fill="{_heat_color(fraction)}"/>'
            )
    right, bottom = left + plot_size, top + plot_size
    lines += [
        f'<rect x="{left}" y="{top}" width="{plot_size}" height="{plot_size}" fill="none" stroke="black"/>',
        f'<text x="{left}" y="{bottom+20}" text-anchor="middle" font-family="sans-serif" font-size="12">{xmin:g}</text>',
        f'<text x="{right}" y="{bottom+20}" text-anchor="middle" font-family="sans-serif" font-size="12">{xmax:g}</text>',
        f'<text x="{left-10}" y="{bottom+4}" text-anchor="end" font-family="sans-serif" font-size="12">{ymin:g}</text>',
        f'<text x="{left-10}" y="{top+4}" text-anchor="end" font-family="sans-serif" font-size="12">{ymax:g}</text>',
        f'<text x="{(left+right)/2}" y="{height-18}" text-anchor="middle" font-family="sans-serif">{escape(x_label)}</text>',
        f'<text x="22" y="{(top+bottom)/2}" text-anchor="middle" transform="rotate(-90 22 {(top+bottom)/2})" font-family="sans-serif">{escape(y_label)}</text>',
    ]
    bar_x, bar_y, bar_width, bar_height = right + 28, top, 18, plot_size
    for index in range(100):
        fraction = index / 99
        y = bar_y + (99 - index) * bar_height / 100
        lines.append(
            f'<rect x="{bar_x}" y="{y:.2f}" width="{bar_width}" height="{bar_height/100+0.1:.2f}" fill="{_heat_color(fraction)}"/>'
        )
    lines += [
        f'<text x="{bar_x+bar_width+6}" y="{bar_y+5}" font-family="sans-serif" font-size="12">{maximum:.3g}</text>',
        f'<text x="{bar_x+bar_width+6}" y="{bar_y+bar_height}" font-family="sans-serif" font-size="12">{minimum:.3g}</text>',
        f'<text x="{bar_x+bar_width/2}" y="{bar_y+bar_height+22}" text-anchor="middle" font-family="sans-serif" font-size="11">{escape(value_label)}</text>',
        "</svg>",
    ]
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_svg_line_plot(
    destination: str | Path,
    series: Sequence[Mapping[str, object]],
    *,
    title: str,
    x_label: str,
    y_label: str,
    width: int = 900,
    height: int = 560,
) -> Path:
    """Write a dependency-free SVG comparison plot from named x/y series."""
    normalized = []
    for item in series:
        xs = [float(value) for value in item["x"]]  # type: ignore[index]
        ys = [float(value) for value in item["y"]]  # type: ignore[index]
        if len(xs) != len(ys) or not xs:
            raise ValueError("every plot series needs equally sized non-empty x/y values")
        normalized.append((str(item["label"]), str(item.get("color", "#2563eb")), xs, ys))
    all_x = [value for _, _, xs, _ in normalized for value in xs]
    all_y = [value for _, _, _, ys in normalized for value in ys]
    xmin, xmax = min(all_x), max(all_x)
    ymin, ymax = min(all_y), max(all_y)
    if xmin == xmax or ymin == ymax:
        raise ValueError("plot ranges must be nonzero")
    left, right, top, bottom = 88, width - 28, 58, height - 72

    def sx(value: float) -> float:
        return left + (value - xmin) / (xmax - xmin) * (right - left)

    def sy(value: float) -> float:
        return bottom - (value - ymin) / (ymax - ymin) * (bottom - top)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="20">{escape(title)}</text>',
    ]
    for tick in range(6):
        fraction = tick / 5
        x = left + fraction * (right - left)
        y = bottom - fraction * (bottom - top)
        xv = xmin + fraction * (xmax - xmin)
        yv = ymin + fraction * (ymax - ymin)
        lines += [
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{bottom}" stroke="#e5e7eb"/>',
            f'<line x1="{left}" y1="{y:.2f}" x2="{right}" y2="{y:.2f}" stroke="#e5e7eb"/>',
            f'<text x="{x:.2f}" y="{bottom+24}" text-anchor="middle" font-family="sans-serif" font-size="12">{xv:.1f}</text>',
            f'<text x="{left-10}" y="{y+4:.2f}" text-anchor="end" font-family="sans-serif" font-size="12">{yv:.1f}</text>',
        ]
    lines += [
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="black"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="black"/>',
        f'<text x="{(left+right)/2}" y="{height-20}" text-anchor="middle" font-family="sans-serif">{escape(x_label)}</text>',
        f'<text x="22" y="{(top+bottom)/2}" text-anchor="middle" transform="rotate(-90 22 {(top+bottom)/2})" font-family="sans-serif">{escape(y_label)}</text>',
    ]
    for index, (label, color, xs, ys) in enumerate(normalized):
        points = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y in zip(xs, ys))
        lines.append(f'<polyline points="{points}" fill="none" stroke="{escape(color)}" stroke-width="2.2"/>')
        legend_y = top + 18 * index
        lines.append(f'<line x1="{right-190}" y1="{legend_y}" x2="{right-165}" y2="{legend_y}" stroke="{escape(color)}" stroke-width="3"/>')
        lines.append(f'<text x="{right-158}" y="{legend_y+4}" font-family="sans-serif" font-size="12">{escape(label)}</text>')
    lines.append("</svg>")
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
