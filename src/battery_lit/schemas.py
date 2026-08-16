from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .paths import repo_root


def schema_path(name: str) -> Path:
    return repo_root() / "schemas" / name


def load_schema(name: str) -> dict[str, Any]:
    return json.loads(schema_path(name).read_text(encoding="utf-8"))


def validate_with_schema(data: dict[str, Any], name: str) -> None:
    Draft202012Validator(load_schema(name)).validate(data)

