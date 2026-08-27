from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .acceptance import AcceptanceResult, acceptance_summary
from .spec import CaseSpec


def write_acceptance_report(
    destination: str | Path,
    spec: CaseSpec,
    metrics: Mapping[str, Any],
    results: list[AcceptanceResult],
    provenance: Mapping[str, Any] | None = None,
) -> Path:
    summary = acceptance_summary(results)
    lines = [
        f"# Acceptance report: {spec.title}",
        "",
        f"- Case: `{spec.case_id}`",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Required criteria: {summary['required_passed']}/{summary['required_total']}",
        f"- Overall: **{'PASS' if summary['passed'] else 'FAIL'}**",
        "",
        "| Criterion | Metric | Actual | Rule | Required | Result |",
        "|---|---|---:|---|---|---|",
    ]
    for item in results:
        lines.append(
            f"| {item.criterion_id} | `{item.metric}` | {item.actual} {item.units} | "
            f"{item.operator} {item.expected} | {'yes' if item.required else 'no'} | "
            f"{'PASS' if item.passed else 'FAIL'} |"
        )
    if provenance:
        lines += ["", "## Provenance", ""]
        lines.extend(f"- {key}: `{value}`" for key, value in provenance.items())
    lines += ["", "## Raw metrics", ""]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(metrics.items()))
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
