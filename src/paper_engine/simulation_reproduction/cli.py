from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .acceptance import acceptance_summary, evaluate_acceptance
from .artifacts import RunArtifacts
from .comsol_remote import ComsolRemoteAgent, ComsolRemoteConfig, ComsolRemoteError
from .report import write_acceptance_report
from .spec import load_case_spec
from .workflow import ReproductionWorkflow, Stage


def add_parser(subparsers: Any, name: str = "reproduce") -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help="run auditable paper-simulation reproduction workflows")
    commands = parser.add_subparsers(dest="reproduce_command", required=True)

    check = commands.add_parser("check-case", help="validate and summarize a case YAML")
    check.add_argument("case", type=Path)

    init_run = commands.add_parser("init-run", help="create a solver run artifact tree")
    init_run.add_argument("case", type=Path)
    init_run.add_argument("--output-root", type=Path, required=True)
    init_run.add_argument("--run-id")

    validate = commands.add_parser("validate", help="evaluate metrics against a case contract")
    validate.add_argument("case", type=Path)
    validate.add_argument("metrics", type=Path)
    validate.add_argument("--report", type=Path, required=True)
    validate.add_argument("--json-report", type=Path)

    comsol = commands.add_parser("comsol", help="operate a configured remote COMSOL agent")
    comsol_commands = comsol.add_subparsers(dest="comsol_command", required=True)
    for command, help_text in (
        ("probe", "verify SSH, instance selection, COMSOL, and Slurm"),
        ("upload", "upload a local file or directory through the instance gateway"),
        ("download", "download a remote file or directory through the instance gateway"),
        ("submit", "submit a solver script from its remote working directory"),
        ("status", "query a Slurm job"),
        ("verify", "fail-closed check of logs and a solver artifact"),
    ):
        item = comsol_commands.add_parser(command, help=help_text)
        item.add_argument("--config", type=Path, required=True)
        item.add_argument("--password-file", type=Path, required=True)
        if command == "submit":
            item.add_argument("--remote-workdir", required=True)
            item.add_argument("--script", required=True)
        elif command == "upload":
            item.add_argument("--local-path", type=Path, required=True)
            item.add_argument("--remote-path", required=True)
        elif command == "download":
            item.add_argument("--remote-path", required=True)
            item.add_argument("--local-path", type=Path, required=True)
        elif command == "status":
            item.add_argument("--job-id", required=True)
        elif command == "verify":
            item.add_argument("--remote-workdir", required=True)
            item.add_argument("--job-id", required=True)
            item.add_argument("--stdout-pattern", required=True)
            item.add_argument("--stderr-pattern", required=True)
            item.add_argument("--artifact", required=True)

    init = commands.add_parser("init", help="initialize the five-stage agent workflow")
    init.add_argument("--workspace", type=Path, required=True)
    init.add_argument("--case-id", required=True)
    init.add_argument("--title", required=True)
    init.add_argument("--paper", type=Path, required=True)

    for command, help_text in (
        ("status", "show workflow state"),
        ("prepare", "write the active agent task contract"),
        ("check-stage", "validate active stage outputs without advancing"),
        ("submit", "validate and advance the active stage"),
    ):
        item = commands.add_parser(command, help=help_text)
        item.add_argument("--workspace", type=Path, required=True)
        if command != "status":
            item.add_argument("--stage", choices=[stage.value for stage in Stage])
    return parser


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    command = args.reproduce_command
    if command == "check-case":
        spec = load_case_spec(args.case)
        return 0, {
            "ok": True,
            "case_id": spec.case_id,
            "title": spec.title,
            "studies": [study.get("id") for study in spec.studies],
            "acceptance_criteria": len(spec.acceptance),
        }
    if command == "init-run":
        spec = load_case_spec(args.case)
        artifacts = RunArtifacts.create(args.output_root, spec.case_id, args.run_id)
        artifacts.write_json("model", "case_snapshot.json", spec.raw)
        return 0, {"ok": True, "root": str(artifacts.root)}
    if command == "validate":
        spec = load_case_spec(args.case)
        metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
        results = evaluate_acceptance(spec, metrics)
        summary = acceptance_summary(results)
        write_acceptance_report(
            args.report,
            spec,
            metrics,
            results,
            {"case_file": args.case.resolve(), "metrics_file": args.metrics.resolve()},
        )
        if args.json_report:
            args.json_report.parent.mkdir(parents=True, exist_ok=True)
            args.json_report.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return (0 if summary["passed"] else 2), {"ok": bool(summary["passed"]), **summary}
    if command == "comsol":
        try:
            agent = ComsolRemoteAgent(ComsolRemoteConfig.load(args.config), args.password_file)
            if args.comsol_command == "probe":
                result = agent.probe()
            elif args.comsol_command == "upload":
                result = agent.upload(local_path=args.local_path, remote_path=args.remote_path)
            elif args.comsol_command == "download":
                result = agent.download(remote_path=args.remote_path, local_path=args.local_path)
            elif args.comsol_command == "submit":
                result = agent.submit(remote_workdir=args.remote_workdir, script=args.script)
            elif args.comsol_command == "status":
                result = agent.status(args.job_id)
            else:
                result = agent.verify(
                    remote_workdir=args.remote_workdir,
                    job_id=args.job_id,
                    stdout_pattern=args.stdout_pattern,
                    stderr_pattern=args.stderr_pattern,
                    artifact=args.artifact,
                )
        except ComsolRemoteError as exc:
            return 2, {"ok": False, "error": str(exc)}
        payload = result.as_dict()
        return (0 if payload["ok"] else 2), payload
    if command == "init":
        workflow = ReproductionWorkflow.create(
            args.workspace,
            case_id=args.case_id,
            title=args.title,
            paper=args.paper,
        )
        return 0, workflow.status()

    workflow = ReproductionWorkflow(args.workspace)
    if command == "status":
        return 0, workflow.status()
    selected = Stage(args.stage) if args.stage else None
    if command == "prepare":
        return 0, workflow.prepare(selected)
    if command == "check-stage":
        result = workflow.validate(selected).as_dict()
        return (0 if result["ok"] else 2), result
    result = workflow.submit(selected)
    return (0 if result["ok"] else 2), result


def standalone_main() -> int:
    parser = argparse.ArgumentParser(prog="python -m paper_engine.simulation_reproduction")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_parser(subparsers, name="reproduce")
    args = parser.parse_args(["reproduce", *sys.argv[1:]])
    code, payload = run(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return code
