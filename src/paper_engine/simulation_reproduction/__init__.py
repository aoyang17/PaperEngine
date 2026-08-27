"""Reusable infrastructure for auditable paper-simulation reproductions."""

from .acceptance import AcceptanceResult, evaluate_acceptance
from .artifacts import RunArtifacts
from .comsol_remote import ComsolRemoteAgent, ComsolRemoteConfig, ComsolRemoteError
from .spec import CaseSpec, load_case_spec
from .workflow import ReproductionWorkflow, Stage, StageValidation

__all__ = [
    "AcceptanceResult",
    "CaseSpec",
    "ComsolRemoteAgent",
    "ComsolRemoteConfig",
    "ComsolRemoteError",
    "RunArtifacts",
    "ReproductionWorkflow",
    "Stage",
    "StageValidation",
    "evaluate_acceptance",
    "load_case_spec",
]
