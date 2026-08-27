from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


class SpecError(ValueError):
    """Raised when a simulation case specification is incomplete or inconsistent."""


@dataclass(frozen=True)
class AcceptanceCriterion:
    criterion_id: str
    metric: str
    operator: str
    expected: Any
    units: str = ""
    required: bool = True
    description: str = ""


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    title: str
    source: Mapping[str, Any]
    model: Mapping[str, Any]
    parameters: Mapping[str, Any]
    studies: tuple[Mapping[str, Any], ...]
    acceptance: tuple[AcceptanceCriterion, ...]
    raw: Mapping[str, Any]


_OPERATORS = {"between", "<", "<=", ">", ">=", "==", "relative_error_le"}


def load_case_spec(path: str | Path) -> CaseSpec:
    source_path = Path(path)
    data = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SpecError("case specification must be a YAML mapping")

    missing = [key for key in ("case_id", "title", "source", "model", "parameters", "studies", "acceptance") if key not in data]
    if missing:
        raise SpecError(f"missing required fields: {', '.join(missing)}")
    if not isinstance(data["studies"], list) or not data["studies"]:
        raise SpecError("studies must be a non-empty list")
    if not isinstance(data["acceptance"], list) or not data["acceptance"]:
        raise SpecError("acceptance must be a non-empty list")

    criteria: list[AcceptanceCriterion] = []
    seen: set[str] = set()
    for index, item in enumerate(data["acceptance"]):
        if not isinstance(item, dict):
            raise SpecError(f"acceptance[{index}] must be a mapping")
        for field in ("id", "metric", "operator", "expected"):
            if field not in item:
                raise SpecError(f"acceptance[{index}] is missing {field}")
        criterion_id = str(item["id"])
        if criterion_id in seen:
            raise SpecError(f"duplicate acceptance id: {criterion_id}")
        seen.add(criterion_id)
        operator = str(item["operator"])
        if operator not in _OPERATORS:
            raise SpecError(f"unsupported acceptance operator: {operator}")
        criteria.append(
            AcceptanceCriterion(
                criterion_id=criterion_id,
                metric=str(item["metric"]),
                operator=operator,
                expected=item["expected"],
                units=str(item.get("units", "")),
                required=bool(item.get("required", True)),
                description=str(item.get("description", "")),
            )
        )

    return CaseSpec(
        case_id=str(data["case_id"]),
        title=str(data["title"]),
        source=data["source"],
        model=data["model"],
        parameters=data["parameters"],
        studies=tuple(data["studies"]),
        acceptance=tuple(criteria),
        raw=data,
    )
