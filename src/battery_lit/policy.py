from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .paths import TopicPaths

REQUIRED_KEYS = {
    "schema_version",
    "allowed_direct_writes",
    "cli_only_writes",
    "forbidden_without_explicit_confirmation",
    "destructive_policy",
    "context_policy",
}


def load_policy(root: str | Path) -> dict[str, Any]:
    path = TopicPaths.from_root(root).policy_yml
    if not path.exists():
        raise FileNotFoundError(f"missing policy.yml under {path.parent}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("policy.yml must contain a YAML mapping")
    return data


def check_policy(root: str | Path) -> dict[str, Any]:
    paths = TopicPaths.from_root(root)
    errors: list[str] = []
    if not paths.policy_yml.exists():
        return {"ok": False, "policy": str(paths.policy_yml), "errors": ["missing policy.yml"]}
    try:
        policy = load_policy(root)
    except Exception as exc:
        return {"ok": False, "policy": str(paths.policy_yml), "errors": [str(exc)]}

    missing = sorted(REQUIRED_KEYS - set(policy))
    errors.extend(f"missing key: {key}" for key in missing)

    destructive = policy.get("destructive_policy") or {}
    if not isinstance(destructive, dict):
        errors.append("destructive_policy must be a mapping")
    else:
        if destructive.get("requires_dry_run") is not True:
            errors.append("destructive_policy.requires_dry_run must be true")
        if destructive.get("requires_explicit_user_confirmation") is not True:
            errors.append("destructive_policy.requires_explicit_user_confirmation must be true")

    for key in ["allowed_direct_writes", "cli_only_writes", "forbidden_without_explicit_confirmation"]:
        if key in policy and not isinstance(policy.get(key), list):
            errors.append(f"{key} must be a list")

    return {"ok": not errors, "policy": str(paths.policy_yml), "errors": errors}
