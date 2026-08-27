from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping

from .spec import CaseSpec


@dataclass(frozen=True)
class AcceptanceResult:
    criterion_id: str
    metric: str
    actual: Any
    expected: Any
    operator: str
    passed: bool
    required: bool
    units: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _lookup(metrics: Mapping[str, Any], dotted: str) -> Any:
    value: Any = metrics
    for part in dotted.split("."):
        if not isinstance(value, Mapping) or part not in value:
            raise KeyError(dotted)
        value = value[part]
    return value


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "between":
        low, high = expected
        return float(low) <= float(actual) <= float(high)
    if operator == "relative_error_le":
        target, tolerance = expected
        denominator = max(abs(float(target)), 1e-30)
        return abs(float(actual) - float(target)) / denominator <= float(tolerance)
    operations = {
        "<": lambda: actual < expected,
        "<=": lambda: actual <= expected,
        ">": lambda: actual > expected,
        ">=": lambda: actual >= expected,
        "==": lambda: actual == expected,
    }
    return bool(operations[operator]())


def evaluate_acceptance(spec: CaseSpec, metrics: Mapping[str, Any]) -> list[AcceptanceResult]:
    results: list[AcceptanceResult] = []
    for criterion in spec.acceptance:
        try:
            actual = _lookup(metrics, criterion.metric)
            passed = _compare(actual, criterion.operator, criterion.expected)
            if isinstance(actual, float) and not math.isfinite(actual):
                passed = False
            message = "pass" if passed else "value does not satisfy criterion"
        except KeyError:
            actual = None
            passed = False
            message = "metric missing"
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            actual = None
            passed = False
            message = f"invalid metric or criterion: {exc}"
        results.append(
            AcceptanceResult(
                criterion_id=criterion.criterion_id,
                metric=criterion.metric,
                actual=actual,
                expected=criterion.expected,
                operator=criterion.operator,
                passed=passed,
                required=criterion.required,
                units=criterion.units,
                message=message,
            )
        )
    return results


def acceptance_summary(results: list[AcceptanceResult]) -> dict[str, Any]:
    required = [result for result in results if result.required]
    return {
        "passed": all(result.passed for result in required),
        "required_passed": sum(result.passed for result in required),
        "required_total": len(required),
        "optional_passed": sum(result.passed for result in results if not result.required),
        "optional_total": sum(not result.required for result in results),
        "results": [result.as_dict() for result in results],
    }
