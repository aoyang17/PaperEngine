from pathlib import Path

import pytest

from paper_engine.cli import build_parser
from paper_engine.simulation_reproduction.acceptance import acceptance_summary, evaluate_acceptance
from paper_engine.simulation_reproduction.artifacts import RunArtifacts
from paper_engine.simulation_reproduction.comsol_remote import (
    ComsolRemoteAgent,
    ComsolRemoteConfig,
    ComsolRemoteError,
    RemoteResult,
)
from paper_engine.simulation_reproduction.spec import SpecError, load_case_spec
from paper_engine.simulation_reproduction.timeseries import (
    interpolate,
    mean_normalized_rmse,
    normalized_rmse,
    read_numeric_csv,
    tail_slope,
    time_to_fraction,
)
from paper_engine.simulation_reproduction.plotting import write_svg_heatmap, write_svg_line_plot
from paper_engine.simulation_reproduction.workflow import ReproductionWorkflow, Stage


def test_case_spec_and_acceptance(tmp_path: Path) -> None:
    case = tmp_path / "case.yml"
    case.write_text(
        """case_id: demo
title: Demo
source: {doi: x}
model: {dimension: 2}
parameters: {x: 1}
studies: [{id: baseline}]
acceptance:
  - {id: range, metric: result.radius, operator: between, expected: [22, 25], units: nm}
  - {id: bound, metric: result.error, operator: '<=', expected: 0.001}
""",
        encoding="utf-8",
    )
    spec = load_case_spec(case)
    results = evaluate_acceptance(spec, {"result": {"radius": 23.5, "error": 0.0002}})
    assert acceptance_summary(results)["passed"] is True


def test_missing_required_field(tmp_path: Path) -> None:
    case = tmp_path / "bad.yml"
    case.write_text("case_id: bad\n", encoding="utf-8")
    with pytest.raises(SpecError):
        load_case_spec(case)


def test_artifact_contract(tmp_path: Path) -> None:
    artifacts = RunArtifacts.create(tmp_path, "demo", "fixed")
    path = artifacts.write_json("raw", "metrics.json", {"ok": True})
    assert path == tmp_path / "demo" / "fixed" / "raw" / "metrics.json"
    assert path.is_file()
    manifest = artifacts.write_sha256_manifest(artifacts.root / "manifest.sha256")
    content = manifest.read_text(encoding="utf-8")
    assert "raw/metrics.json" in content
    assert "manifest.sha256" not in content


def test_missing_metrics_fail_closed(tmp_path: Path) -> None:
    case = tmp_path / "case.yml"
    case.write_text(
        """case_id: demo
title: Demo
source: {doi: x}
model: {dimension: 2}
parameters: {x: 1}
studies: [{id: baseline}]
acceptance:
  - {id: required, metric: result.value, operator: '>=', expected: 1}
""",
        encoding="utf-8",
    )
    results = evaluate_acceptance(load_case_spec(case), {})
    assert results[0].passed is False
    assert results[0].message == "metric missing"


def test_comsol_csv_reader_and_tail_slope(tmp_path: Path) -> None:
    data = tmp_path / "global.csv"
    data.write_text("% COMSOL metadata\nTime (s),radius_nm\n0,1\n1,2\n2,3\n", encoding="utf-8")
    rows = read_numeric_csv(data)
    assert rows[-1]["radius_nm"] == 3
    assert tail_slope(rows, "Time (s)", "radius_nm", 1.0) == pytest.approx(1.0)
    assert interpolate(rows, "Time (s)", "radius_nm", 0.5) == pytest.approx(1.5)
    assert normalized_rmse([1, 2, 3], [1, 2, 3]) == 0
    assert mean_normalized_rmse([1, 2, 3], [1, 2, 3]) == 0
    assert time_to_fraction(rows, "Time (s)", "radius_nm", 0.5) == pytest.approx(1.0)


def test_dependency_free_svg_plot(tmp_path: Path) -> None:
    output = write_svg_line_plot(
        tmp_path / "plot.svg",
        [{"label": "curve", "x": [0, 1], "y": [2, 3], "color": "#000000"}],
        title="Title",
        x_label="x",
        y_label="y",
    )
    assert output.read_text(encoding="utf-8").startswith("<svg")


def test_dependency_free_svg_heatmap(tmp_path: Path) -> None:
    output = write_svg_heatmap(
        tmp_path / "heat.svg",
        [[0, 1], [2, 3]],
        title="Heat",
        x_label="x",
        y_label="y",
        value_label="value",
    )
    content = output.read_text(encoding="utf-8")
    assert content.startswith("<svg")
    assert "value" in content


def _write_stage_outputs(workflow: ReproductionWorkflow, stage: Stage, *, review_decision: str = "accepted") -> None:
    directory = workflow.stage_dir(stage)
    if stage is Stage.RESEARCH:
        (directory / "evidence_map.json").write_text(
            '{"claims":[{"page":1,"source_text":"claim"}],"equations":[{"page":1,"source_text":"u=1"}],"figures":[],"ambiguities":[]}',
            encoding="utf-8",
        )
        (directory / "research_report.md").write_text("# Research\n", encoding="utf-8")
    elif stage is Stage.THEORY:
        (directory / "case.yml").write_text(
            """case_id: demo
title: Demo
source: {doi: x}
model: {dimension: 2}
parameters: {x: 1}
studies: [{id: baseline}]
acceptance:
  - {id: value, metric: result.value, operator: '>=', expected: 1}
""",
            encoding="utf-8",
        )
        (directory / "equation_audit.md").write_text("# Equations\n", encoding="utf-8")
    elif stage is Stage.IMPLEMENTATION:
        (directory / "model.java").write_text("class Model {}\n", encoding="utf-8")
        (directory / "implementation_manifest.json").write_text(
            '{"solver":"COMSOL","solver_version":"6.3","equation_mapping":[{"paper":"1","comsol":"gpe"}],"model_files":["model.java"]}',
            encoding="utf-8",
        )
        (directory / "comsol_handoff.md").write_text("# COMSOL\n", encoding="utf-8")
    elif stage is Stage.EXPERIMENT:
        (directory / "run_manifest.json").write_text(
            '{"solver":"COMSOL 6.3","runs":[{"id":"baseline","status":"complete"}]}',
            encoding="utf-8",
        )
        (directory / "metrics.json").write_text('{"result":{"value":1.2}}', encoding="utf-8")
    else:
        review = {"decision": review_decision, "findings": []}
        if review_decision == "rejected":
            review["return_stage"] = "implementation"
        (directory / "review.json").write_text(__import__("json").dumps(review), encoding="utf-8")
        (directory / "review_report.md").write_text("# Review\n", encoding="utf-8")


def test_five_stage_reproduction_workflow_accepts_only_after_review(tmp_path: Path) -> None:
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"%PDF-1.4\n")
    workflow = ReproductionWorkflow.create(tmp_path / "workspace", case_id="demo", title="Demo", paper=paper)

    for stage in Stage:
        prepared = workflow.prepare()
        assert prepared["stage"] == stage.value
        _write_stage_outputs(workflow, stage)
        result = workflow.submit()
        if stage is not Stage.REVIEW:
            assert result["next_stage"] == Stage(list(Stage)[list(Stage).index(stage) + 1]).value

    assert workflow.status()["status"] == "complete"
    assert (workflow.root / "publication.json").is_file()


def test_rejected_review_archives_stale_downstream_outputs(tmp_path: Path) -> None:
    paper = tmp_path / "paper.pdf"
    paper.write_bytes(b"%PDF-1.4\n")
    workflow = ReproductionWorkflow.create(tmp_path / "workspace", case_id="demo", title="Demo", paper=paper)
    for stage in Stage:
        workflow.prepare()
        _write_stage_outputs(workflow, stage, review_decision="rejected" if stage is Stage.REVIEW else "accepted")
        result = workflow.submit()

    assert result["status"] == "rework"
    assert workflow.active_stage is Stage.IMPLEMENTATION
    assert not (workflow.stage_dir(Stage.IMPLEMENTATION) / "model.java").exists()
    assert (workflow.root / "archive" / "cycle_001" / "stages" / "03_implementation" / "model.java").is_file()


def test_primary_cli_exposes_reproduction_controller() -> None:
    args = build_parser().parse_args(
        ["reproduce", "init", "--workspace", "work", "--case-id", "demo", "--title", "Demo", "--paper", "paper.pdf"]
    )
    assert args.command == "reproduce"
    assert args.reproduce_command == "init"


def test_comsol_remote_config_and_secret_permissions(tmp_path: Path) -> None:
    config_path = tmp_path / "remote.json"
    config_path.write_text(
        '{"ssh":{"host":"gateway","port":44322,"user":"researcher","instance_selection":"1"},'
        '"remote":{"environment_script":"~/apps/comsol64_env.sh"}}',
        encoding="utf-8",
    )
    config = ComsolRemoteConfig.load(config_path)
    assert config.port == 44322
    password = tmp_path / "password"
    password.write_text("secret\n", encoding="utf-8")
    password.chmod(0o600)
    agent = ComsolRemoteAgent(config, password)
    assert agent._read_password() == "secret"
    password.chmod(0o644)
    with pytest.raises(ComsolRemoteError, match="group or others"):
        agent._read_password()


def test_comsol_direct_instance_id_is_used_as_ssh_login_user(tmp_path: Path) -> None:
    config_path = tmp_path / "remote.json"
    config_path.write_text(
        '{"ssh":{"host":"gateway","port":44322,"user":"researcher",'
        '"instance_selection":"1","instance_id":"123456"},'
        '"remote":{"environment_script":"~/apps/comsol64_env.sh"}}',
        encoding="utf-8",
    )
    config = ComsolRemoteConfig.load(config_path)
    password = tmp_path / "password"
    password.write_text("secret\n", encoding="utf-8")
    password.chmod(0o600)
    agent = ComsolRemoteAgent(config, password)
    assert agent._login_user() == "researcher::123456"
    assert "User=researcher::123456" in agent._scp_base_args()


def test_primary_cli_exposes_comsol_remote_agent() -> None:
    args = build_parser().parse_args(
        [
            "reproduce",
            "comsol",
            "submit",
            "--config",
            "remote.json",
            "--password-file",
            "password",
            "--remote-workdir",
            "~/case",
            "--script",
            "run.slurm",
        ]
    )
    assert args.reproduce_command == "comsol"
    assert args.comsol_command == "submit"

    upload = build_parser().parse_args(
        [
            "reproduce",
            "comsol",
            "upload",
            "--config",
            "remote.json",
            "--password-file",
            "password",
            "--local-path",
            "local",
            "--remote-path",
            "~/remote",
        ]
    )
    assert upload.comsol_command == "upload"


def test_comsol_verify_requires_completed_slurm_job(tmp_path: Path) -> None:
    class RecordingAgent(ComsolRemoteAgent):
        def run(self, command: str, *, timeout: int = 60) -> RemoteResult:
            return RemoteResult(command, 0, command)

    config = ComsolRemoteConfig("gateway", 22, "user", "1", "~/comsol_env.sh")
    agent = RecordingAgent(config, tmp_path / "unused-password")
    result = agent.verify(
        remote_workdir="~/run",
        job_id="123",
        stdout_pattern="solver.%j.out",
        stderr_pattern="solver.%j.err",
        artifact="solved.mph",
    )
    assert "test \"$job_state\" = 'COMPLETED|0:0'" in result.command
    assert "test -s solved.mph" in result.command
    assert "test -f solver.123.out" in result.command
    assert "*_comsol_batch.log" in result.command
