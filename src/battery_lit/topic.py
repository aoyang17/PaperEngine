from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

import yaml

from .paths import TopicPaths, repo_root
from .util import ensure_dir, slugify_path_component, utc_now


def _format_template(path: Path, **values: str) -> str:
    return path.read_text(encoding="utf-8").format(**values)


def _write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def _copy_tree_contents(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    ensure_dir(dst)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            if not target.exists():
                shutil.copytree(item, target)
        elif not target.exists():
            shutil.copy2(item, target)


def _is_topic_root(paths: TopicPaths) -> bool:
    return paths.topic_yml.exists() and paths.policy_yml.exists() and paths.agents.exists()


def _target_root_is_non_empty(paths: TopicPaths) -> bool:
    return paths.root.exists() and any(paths.root.iterdir())


def init_topic(
    root: str | Path,
    title: str | None = None,
    direction: str | None = None,
    seed_papers: Iterable[str] | None = None,
) -> dict[str, object]:
    paths = TopicPaths.from_root(root)
    if _target_root_is_non_empty(paths) and not _is_topic_root(paths):
        raise ValueError(
            "target topic root already exists and is non-empty but is not a battery topic; "
            "ask the user to enter that topic or choose a new root; do not infer from filesystem"
        )

    ensure_dir(paths.root)
    for directory in [paths.papers, paths.reports, paths.html, paths.skills, paths.schemas]:
        ensure_dir(directory)

    now = utc_now()
    title = title or paths.root.name.replace("_", " ").replace("-", " ").strip() or "Untitled Topic"
    direction = direction or ""
    template_root = repo_root() / "templates" / "topic_repo"

    created: list[str] = []
    for name, target in [
        ("README.md", paths.readme),
        ("AGENTS.md", paths.agents),
        ("topic.yml", paths.topic_yml),
        ("preferences.yml", paths.preferences_yml),
        ("policy.yml", paths.policy_yml),
        ("candidates.jsonl", paths.candidates_jsonl),
        ("library.bib", paths.library_bib),
    ]:
        content = _format_template(template_root / name, title=title, direction=direction, created_at=now)
        if _write_if_missing(target, content):
            created.append(target.name)

    if seed_papers:
        topic_data = load_topic(paths.root)
        existing = list(topic_data.get("seed_papers") or [])
        for paper in seed_papers:
            if paper and paper not in existing:
                existing.append(paper)
        topic_data["seed_papers"] = existing
        topic_data["updated_at"] = now
        paths.topic_yml.write_text(yaml.safe_dump(topic_data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    _copy_tree_contents(repo_root() / "templates" / "skills", paths.skills)
    _copy_tree_contents(repo_root() / "schemas", paths.schemas)

    return {"root": str(paths.root), "created": created, "ok": True}


def root_from_title(base_dir: str | Path, title: str) -> Path:
    return Path(base_dir).expanduser().resolve() / slugify_path_component(title)


def load_topic(root: str | Path) -> dict[str, object]:
    path = TopicPaths.from_root(root).topic_yml
    if not path.exists():
        raise FileNotFoundError(f"missing topic.yml under {path.parent}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_preferences(root: str | Path) -> dict[str, object]:
    path = TopicPaths.from_root(root).preferences_yml
    if not path.exists():
        raise FileNotFoundError(f"missing preferences.yml under {path.parent}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def save_preferences(root: str | Path, data: dict[str, object]) -> None:
    path = TopicPaths.from_root(root).preferences_yml
    data["updated_at"] = utc_now()
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
