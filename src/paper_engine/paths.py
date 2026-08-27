from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TopicPaths:
    root: Path

    @classmethod
    def from_root(cls, root: str | Path | None) -> "TopicPaths":
        return cls(Path(root or ".").expanduser().resolve())

    @property
    def readme(self) -> Path:
        return self.root / "README.md"

    @property
    def agents(self) -> Path:
        return self.root / "AGENTS.md"

    @property
    def topic_yml(self) -> Path:
        return self.root / "topic.yml"

    @property
    def preferences_yml(self) -> Path:
        return self.root / "preferences.yml"

    @property
    def policy_yml(self) -> Path:
        return self.root / "policy.yml"

    @property
    def candidates_jsonl(self) -> Path:
        return self.root / "candidates.jsonl"

    @property
    def library_bib(self) -> Path:
        return self.root / "library.bib"

    @property
    def papers(self) -> Path:
        return self.root / "papers"

    @property
    def incoming(self) -> Path:
        return self.papers / "_incoming"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def html(self) -> Path:
        return self.root / "html"

    @property
    def skills(self) -> Path:
        return self.root / "skills"

    @property
    def schemas(self) -> Path:
        return self.root / "schemas"

    def paper_dir(self, bibkey: str) -> Path:
        return self.papers / bibkey


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
