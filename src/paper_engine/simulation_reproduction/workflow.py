from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from .acceptance import acceptance_summary, evaluate_acceptance
from .spec import SpecError, load_case_spec


WORKFLOW_SCHEMA_VERSION = 1


class WorkflowError(RuntimeError):
    """Raised when a reproduction workflow transition is invalid."""


class Stage(str, Enum):
    RESEARCH = "research"
    THEORY = "theory"
    IMPLEMENTATION = "implementation"
    EXPERIMENT = "experiment"
    REVIEW = "review"


STAGE_ORDER = tuple(Stage)
STAGE_DIRECTORIES = {
    Stage.RESEARCH: "01_research",
    Stage.THEORY: "02_theory",
    Stage.IMPLEMENTATION: "03_implementation",
    Stage.EXPERIMENT: "04_experiment",
    Stage.REVIEW: "05_review",
}
STAGE_OUTPUTS = {
    Stage.RESEARCH: ("evidence_map.json", "research_report.md"),
    Stage.THEORY: ("case.yml", "equation_audit.md"),
    Stage.IMPLEMENTATION: ("implementation_manifest.json", "comsol_handoff.md"),
    Stage.EXPERIMENT: ("run_manifest.json", "metrics.json"),
    Stage.REVIEW: ("review.json", "review_report.md"),
}


@dataclass(frozen=True)
class StageValidation:
    stage: Stage
    ok: bool
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"stage": self.stage.value, "ok": self.ok, "errors": list(self.errors)}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"invalid JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"JSON artifact must be an object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class ReproductionWorkflow:
    """Single-controller state machine for a five-agent paper reproduction."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.state_path = self.root / "workflow.json"
        if not self.state_path.is_file():
            raise WorkflowError(f"missing reproduction workflow: {self.state_path}")
        self.state = _read_json(self.state_path)
        if self.state.get("schema_version") != WORKFLOW_SCHEMA_VERSION:
            raise WorkflowError("unsupported reproduction workflow schema")

    @classmethod
    def create(
        cls,
        root: str | Path,
        *,
        case_id: str,
        title: str,
        paper: str | Path,
    ) -> "ReproductionWorkflow":
        destination = Path(root).expanduser().resolve()
        paper_path = Path(paper).expanduser().resolve()
        if not paper_path.is_file() or paper_path.suffix.lower() != ".pdf":
            raise WorkflowError(f"paper PDF not found: {paper_path}")
        if destination.exists() and any(destination.iterdir()):
            raise WorkflowError(f"reproduction workspace is not empty: {destination}")
        destination.mkdir(parents=True, exist_ok=True)
        source_dir = destination / "source"
        source_dir.mkdir()
        snapshot = source_dir / "paper.pdf"
        shutil.copy2(paper_path, snapshot)
        for stage in STAGE_ORDER:
            (destination / "stages" / STAGE_DIRECTORIES[stage]).mkdir(parents=True)
        now = _utc_now()
        state = {
            "schema_version": WORKFLOW_SCHEMA_VERSION,
            "case_id": case_id,
            "title": title,
            "status": "active",
            "active_stage": Stage.RESEARCH.value,
            "cycle": 1,
            "created_at": now,
            "updated_at": now,
            "source": {
                "paper": "source/paper.pdf",
                "original_path": str(paper_path),
                "sha256": _sha256(snapshot),
            },
            "stages": {
                stage.value: {
                    "status": "ready" if stage is Stage.RESEARCH else "pending",
                    "attempts": 0,
                    "validation": None,
                    "completed_at": None,
                }
                for stage in STAGE_ORDER
            },
            "history": [{"at": now, "event": "workflow_created", "stage": Stage.RESEARCH.value}],
        }
        _write_json(destination / "workflow.json", state)
        return cls(destination)

    @property
    def active_stage(self) -> Stage | None:
        value = self.state.get("active_stage")
        return Stage(str(value)) if value else None

    def stage_dir(self, stage: Stage) -> Path:
        return self.root / "stages" / STAGE_DIRECTORIES[stage]

    def status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "root": str(self.root),
            "case_id": self.state["case_id"],
            "title": self.state["title"],
            "status": self.state["status"],
            "active_stage": self.state.get("active_stage"),
            "cycle": self.state["cycle"],
            "stages": self.state["stages"],
        }

    def prepare(self, stage: Stage | None = None) -> dict[str, Any]:
        selected = stage or self.active_stage
        if selected is None:
            raise WorkflowError("workflow is already complete")
        if selected is not self.active_stage:
            raise WorkflowError(f"only active stage can be prepared: {self.active_stage}")
        record = self.state["stages"][selected.value]
        if record["status"] not in {"ready", "in_progress"}:
            raise WorkflowError(f"stage {selected.value} is not ready")
        task_path = self.stage_dir(selected) / "task.md"
        task_path.write_text(self._task_text(selected), encoding="utf-8")
        if record["status"] == "ready":
            record["attempts"] += 1
        record["status"] = "in_progress"
        record["task"] = str(task_path.relative_to(self.root))
        self._history("stage_prepared", selected)
        self._save()
        return {
            "ok": True,
            "stage": selected.value,
            "task": str(task_path),
            "outputs": [str(self.stage_dir(selected) / name) for name in STAGE_OUTPUTS[selected]],
        }

    def validate(self, stage: Stage | None = None) -> StageValidation:
        selected = stage or self.active_stage
        if selected is None:
            raise WorkflowError("workflow is already complete")
        errors: list[str] = []
        directory = self.stage_dir(selected)
        for name in STAGE_OUTPUTS[selected]:
            path = directory / name
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(f"missing required output: {name}")
        if errors:
            return StageValidation(selected, False, tuple(errors))
        try:
            if selected is Stage.RESEARCH:
                self._validate_research(directory, errors)
            elif selected is Stage.THEORY:
                self._validate_theory(directory, errors)
            elif selected is Stage.IMPLEMENTATION:
                self._validate_implementation(directory, errors)
            elif selected is Stage.EXPERIMENT:
                self._validate_experiment(directory, errors)
            else:
                self._validate_review(directory, errors)
        except (WorkflowError, SpecError, ValueError) as exc:
            errors.append(str(exc))
        return StageValidation(selected, not errors, tuple(errors))

    def submit(self, stage: Stage | None = None) -> dict[str, Any]:
        selected = stage or self.active_stage
        if selected is None:
            raise WorkflowError("workflow is already complete")
        if selected is not self.active_stage:
            raise WorkflowError(f"only active stage can be submitted: {self.active_stage}")
        validation = self.validate(selected)
        record = self.state["stages"][selected.value]
        record["validation"] = validation.as_dict()
        if not validation.ok:
            record["status"] = "in_progress"
            self._history("stage_validation_failed", selected, {"errors": list(validation.errors)})
            self._save()
            return {"ok": False, **validation.as_dict()}
        record["status"] = "complete"
        record["completed_at"] = _utc_now()
        record["outputs"] = self._output_manifest(selected)
        if selected is Stage.REVIEW:
            result = self._finish_review()
        else:
            next_stage = STAGE_ORDER[STAGE_ORDER.index(selected) + 1]
            self.state["active_stage"] = next_stage.value
            self.state["stages"][next_stage.value]["status"] = "ready"
            self._history("stage_completed", selected)
            result = {"ok": True, "stage": selected.value, "next_stage": next_stage.value}
        self._save()
        return result

    def _finish_review(self) -> dict[str, Any]:
        review = _read_json(self.stage_dir(Stage.REVIEW) / "review.json")
        decision = str(review.get("decision") or "").lower()
        if decision == "accepted":
            self.state["status"] = "complete"
            self.state["active_stage"] = None
            publication = {
                "schema_version": 1,
                "case_id": self.state["case_id"],
                "completed_at": _utc_now(),
                "cycle": self.state["cycle"],
                "source_sha256": self.state["source"]["sha256"],
                "stage_outputs": {
                    stage.value: self.state["stages"][stage.value].get("outputs", [])
                    for stage in STAGE_ORDER
                },
            }
            _write_json(self.root / "publication.json", publication)
            self._history("workflow_accepted", Stage.REVIEW)
            return {"ok": True, "stage": Stage.REVIEW.value, "status": "complete", "publication": str(self.root / "publication.json")}
        return_stage = Stage(str(review.get("return_stage") or ""))
        if return_stage is Stage.REVIEW:
            raise WorkflowError("review return_stage must precede review")
        start = STAGE_ORDER.index(return_stage)
        archive_root = self._archive_rework_stages(STAGE_ORDER[start:])
        self.state["cycle"] += 1
        for stage in STAGE_ORDER[start:]:
            stage_record = self.state["stages"][stage.value]
            stage_record["status"] = "ready" if stage is return_stage else "pending"
            stage_record["validation"] = None
            stage_record["completed_at"] = None
            stage_record.pop("task", None)
            stage_record.pop("outputs", None)
        self.state["active_stage"] = return_stage.value
        self._history(
            "workflow_rejected",
            Stage.REVIEW,
            {"return_stage": return_stage.value, "archive": str(archive_root.relative_to(self.root))},
        )
        return {
            "ok": True,
            "stage": Stage.REVIEW.value,
            "status": "rework",
            "next_stage": return_stage.value,
            "archive": str(archive_root),
        }

    def _archive_rework_stages(self, stages: tuple[Stage, ...]) -> Path:
        archive_root = self.root / "archive" / f"cycle_{self.state['cycle']:03d}"
        if archive_root.exists():
            raise WorkflowError(f"rework archive already exists: {archive_root}")
        for stage in stages:
            source = self.stage_dir(stage)
            destination = archive_root / "stages" / STAGE_DIRECTORIES[stage]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            source.mkdir(parents=True)
        return archive_root

    def _validate_research(self, directory: Path, errors: list[str]) -> None:
        evidence = _read_json(directory / "evidence_map.json")
        for field in ("claims", "equations", "figures", "ambiguities"):
            if not isinstance(evidence.get(field), list):
                errors.append(f"evidence_map.json field must be a list: {field}")
        refs = [item for field in ("claims", "equations", "figures") for item in evidence.get(field, []) if isinstance(item, dict)]
        for index, item in enumerate(refs):
            if not item.get("page") or not item.get("source_text"):
                errors.append(f"evidence item {index} needs page and source_text")

    def _validate_theory(self, directory: Path, errors: list[str]) -> None:
        try:
            load_case_spec(directory / "case.yml")
        except SpecError as exc:
            errors.append(f"invalid case.yml: {exc}")

    def _validate_implementation(self, directory: Path, errors: list[str]) -> None:
        manifest = _read_json(directory / "implementation_manifest.json")
        if not str(manifest.get("solver") or "").strip():
            errors.append("implementation manifest needs solver")
        mappings = manifest.get("equation_mapping")
        if not isinstance(mappings, list) or not mappings:
            errors.append("implementation manifest needs equation_mapping")
        model_files = manifest.get("model_files")
        if not isinstance(model_files, list) or not model_files:
            errors.append("implementation manifest needs model_files")
        else:
            for value in model_files:
                candidate = (directory / str(value)).resolve()
                try:
                    candidate.relative_to(directory.resolve())
                except ValueError:
                    errors.append(f"model file escapes implementation directory: {value}")
                    continue
                if not candidate.is_file() or candidate.stat().st_size == 0:
                    errors.append(f"model file is missing: {value}")

    def _validate_experiment(self, directory: Path, errors: list[str]) -> None:
        manifest = _read_json(directory / "run_manifest.json")
        metrics = _read_json(directory / "metrics.json")
        if not isinstance(manifest.get("runs"), list) or not manifest["runs"]:
            errors.append("run manifest needs at least one run")
        if not metrics:
            errors.append("metrics.json must not be empty")

    def _validate_review(self, directory: Path, errors: list[str]) -> None:
        review = _read_json(directory / "review.json")
        decision = str(review.get("decision") or "").lower()
        if decision not in {"accepted", "rejected"}:
            errors.append("review decision must be accepted or rejected")
            return
        if not isinstance(review.get("findings"), list):
            errors.append("review findings must be a list")
        if decision == "rejected":
            try:
                return_stage = Stage(str(review.get("return_stage") or ""))
            except ValueError:
                errors.append("rejected review needs a valid return_stage")
            else:
                if return_stage is Stage.REVIEW:
                    errors.append("rejected review must return to an earlier stage")
            return
        spec = load_case_spec(self.stage_dir(Stage.THEORY) / "case.yml")
        metrics = _read_json(self.stage_dir(Stage.EXPERIMENT) / "metrics.json")
        summary = acceptance_summary(evaluate_acceptance(spec, metrics))
        if not summary["passed"]:
            errors.append("review cannot accept because required case criteria failed")

    def _output_manifest(self, stage: Stage) -> list[dict[str, Any]]:
        directory = self.stage_dir(stage)
        outputs = []
        for name in STAGE_OUTPUTS[stage]:
            path = directory / name
            outputs.append({"path": str(path.relative_to(self.root)), "sha256": _sha256(path), "bytes": path.stat().st_size})
        if stage is Stage.IMPLEMENTATION:
            manifest = _read_json(directory / "implementation_manifest.json")
            for value in manifest.get("model_files") or []:
                path = directory / str(value)
                outputs.append({"path": str(path.relative_to(self.root)), "sha256": _sha256(path), "bytes": path.stat().st_size})
        return outputs

    def _task_text(self, stage: Stage) -> str:
        source = self.root / self.state["source"]["paper"]
        common = f"""# {stage.value.title()} Agent Task

You are the {stage.value} agent in a controlled paper-reproduction workflow.

## Invariants

- Paper snapshot: `{source}` (SHA256 `{self.state['source']['sha256']}`)
- Read only the listed inputs and write only in `{self.stage_dir(stage)}`.
- Do not edit outputs from earlier stages.
- Record uncertainty instead of inventing missing equations, parameters, units, or solver settings.
- Write exactly the required outputs before asking the controller to validate this stage.
"""
        contracts = {
            Stage.RESEARCH: """
## Role

Extract source-traceable claims, equations, figures, parameters, and unresolved ambiguities. Do not design the numerical model.

## Outputs

- `evidence_map.json`: arrays `claims`, `equations`, `figures`, and `ambiguities`; each evidence item needs `page` and `source_text`.
- `research_report.md`: concise paper scope, decisive evidence, and missing information.
""",
            Stage.THEORY: f"""
## Inputs

- `{self.stage_dir(Stage.RESEARCH) / 'evidence_map.json'}`
- `{self.stage_dir(Stage.RESEARCH) / 'research_report.md'}`

## Role

Freeze the mathematical model: fields, governing equations, constitutive laws, units, initial/boundary conditions, studies, negative controls, and quantitative acceptance criteria. Resolve every change against paper evidence.

## Outputs

- `case.yml`: valid PaperEngine simulation case contract.
- `equation_audit.md`: paper equation → cleaned equation → assumption → implementation requirement.
""",
            Stage.IMPLEMENTATION: f"""
## Inputs

- `{self.stage_dir(Stage.THEORY) / 'case.yml'}`
- `{self.stage_dir(Stage.THEORY) / 'equation_audit.md'}`

## Role

Translate the frozen theory into a solver-native implementation. Do not reinterpret or silently repair the physics. For COMSOL, state the exact interface, dependent-variable ordering, `ea`, `da`, flux `Γ`, source `f`, boundary `g/q/r`, variables, units, solver version, mesh, time stepping, studies, exports, and Java/API expressions.

## Outputs

- `implementation_manifest.json`: `solver`, `solver_version`, nonempty `equation_mapping`, and relative `model_files`.
- `comsol_handoff.md`: exact build/run/export instructions and declared limitations.
- Every file listed by `model_files`, such as Java/API source and/or an MPH model.
""",
            Stage.EXPERIMENT: f"""
## Inputs

- `{self.stage_dir(Stage.THEORY) / 'case.yml'}`
- `{self.stage_dir(Stage.IMPLEMENTATION) / 'implementation_manifest.json'}`
- `{self.stage_dir(Stage.IMPLEMENTATION) / 'comsol_handoff.md'}`

## Role

Run only the frozen implementation. Preserve raw solver output and logs. Execute baseline, negative controls, parameter sweeps, mesh convergence, and time-step convergence required by `case.yml`. Do not tune parameters after seeing the target result unless the run is explicitly labeled exploratory.

## Outputs

- `run_manifest.json`: solver identity, model hash, and nonempty `runs` with parameters, status, raw outputs, and logs.
- `metrics.json`: machine-readable metrics named exactly as required by `case.yml`.
""",
            Stage.REVIEW: f"""
## Inputs

- Original paper snapshot.
- `{self.stage_dir(Stage.RESEARCH) / 'evidence_map.json'}`
- `{self.stage_dir(Stage.THEORY) / 'case.yml'}`
- `{self.stage_dir(Stage.THEORY) / 'equation_audit.md'}`
- `{self.stage_dir(Stage.IMPLEMENTATION) / 'implementation_manifest.json'}`
- `{self.stage_dir(Stage.EXPERIMENT) / 'run_manifest.json'}`
- `{self.stage_dir(Stage.EXPERIMENT) / 'metrics.json'}`

## Role

Independently audit fidelity, COMSOL translation, numerical health, negative controls, convergence, and paper agreement. Do not accept a run when required case criteria fail. Attribute each failure to the earliest responsible stage.

## Outputs

- `review.json`: `decision` (`accepted` or `rejected`), `findings`; rejected reviews also require `return_stage` (`research`, `theory`, `implementation`, or `experiment`).
- `review_report.md`: evidence-backed verdict and exact rework request.
""",
        }
        return common + contracts[stage]

    def _history(self, event: str, stage: Stage, extra: dict[str, Any] | None = None) -> None:
        self.state["history"].append({"at": _utc_now(), "event": event, "stage": stage.value, **(extra or {})})

    def _save(self) -> None:
        self.state["updated_at"] = _utc_now()
        _write_json(self.state_path, self.state)
