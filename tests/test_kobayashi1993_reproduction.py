from pathlib import Path
import importlib.util
import json

import yaml


ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT / "simulations" / "kobayashi1993" / "workflow"
IMPLEMENTATION = CASE_ROOT / "stages" / "03_implementation"


def test_kobayashi_case_freezes_paper_parameters_and_required_studies() -> None:
    case = yaml.safe_load((CASE_ROOT / "stages" / "02_theory" / "case.yml").read_text(encoding="utf-8"))
    parameters = case["parameters"]
    assert parameters["epsilon_bar"] == 0.01
    assert parameters["tau"] == 0.0003
    assert parameters["latent_heat_K"] == 2.0
    assert parameters["anisotropy_delta_sweep"] == [0.0, 0.005, 0.01, 0.02, 0.05]
    studies = {study["id"] for study in case["studies"]}
    assert {"delta_sweep", "deterministic_negative_control", "grid_convergence", "timestep_convergence", "seed_sensitivity"} <= studies


def test_kobayashi_java_contains_exact_general_form_mapping() -> None:
    source = (IMPLEMENTATION / "comsol" / "Kobayashi1993.java").read_text(encoding="utf-8")
    assert 'create("gp", "GeneralFormPDE"' in source
    assert 'new String[]{"GammaPx", "GammaPy"}' in source
    assert 'setIndex("da", "tau", 0)' in source
    assert 'setIndex("f", "phaseSource", 0)' in source
    assert 'create("gT", "GeneralFormPDE"' in source
    assert 'new String[]{"-D*Tx", "-D*Ty"}' in source
    assert 'setIndex("f", "Klatent*d(p,t)", 0)' in source
    assert 'atan2(-py,-px)' in source
    assert 'set("location", "regulargrid")' in source
    assert 'set("separator", ",")' in source
    assert 'set("innerinput", "interp")' in source
    assert 'comparisonTimes(model.param().evaluate("tfinal"))' in source
    assert 'model.result().export("data1").run()' in source
    assert '_solved.mph' in source
    assert "new File(" not in source
    assert "FileInputStream" not in source
    assert "loadCase(args)" in source


def test_kobayashi_slurm_runner_is_fail_closed() -> None:
    runner = (IMPLEMENTATION / "comsol" / "run_case.sh").read_text(encoding="utf-8")
    assert 'test -s "${prefix}_solved.mph"' in runner
    assert 'test -s "${prefix}_global.csv"' in runner
    assert 'test -s "${prefix}_fields.csv"' in runner
    assert "test -s Kobayashi1993.class" in runner
    assert "Kobayashi1993.class.status" in runner
    assert '-prodargs "${case_args[@]}"' in runner
    assert "unsupported case key" in runner
    assert "grep -Eiq '(Error|Exception|FileNotFound)'" in runner
    assert "sha256sum" in runner


def test_every_declared_comsol_model_file_exists() -> None:
    manifest = json.loads((IMPLEMENTATION / "implementation_manifest.json").read_text(encoding="utf-8"))
    for relative in manifest["model_files"]:
        path = IMPLEMENTATION / relative
        assert path.is_file() and path.stat().st_size > 0


def test_kobayashi_postprocessor_requires_jobs_and_solver_artifacts(tmp_path: Path) -> None:
    module_path = IMPLEMENTATION / "postprocess_suite.py"
    spec = importlib.util.spec_from_file_location("kobayashi_postprocess", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    suite = tmp_path / "suite"
    statuses = {}
    for case in module.REQUIRED_CASES:
        case_dir = suite / case
        case_dir.mkdir(parents=True)
        tip_scale = 1.3 if case == "delta050" else 1.0
        (case_dir / f"{case}_global.csv").write_text(
            "Time (s),enthalpyInvariant (m^2),tipY (m),halfWidth (m),pMin,pMax\n"
            f"0,-0.1,0.1,0.1,0,1\n0.8,-0.1002,{0.8 * tip_scale},0.5,0,1\n"
            f"1.4,-0.1001,{1.4 * tip_scale},0.8,0,1\n",
            encoding="utf-8",
        )
        (case_dir / f"{case}_solved.mph").write_bytes(b"mph" * 400000)
        (case_dir / f"{case}_fields.csv").write_text("x,y,p,T\n0,0,1,0\n", encoding="utf-8")
        (case_dir / f"{case}_comsol_batch.log").write_text("COMSOL complete\n", encoding="utf-8")
        statuses[case] = {"state": "COMPLETED", "exit_code": "0:0"}
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps(statuses), encoding="utf-8")
    figure_path = tmp_path / "figure.json"
    figure_path.write_text('{"mean_iou":0.5,"normalized_chamfer":0.04}', encoding="utf-8")

    metrics = module.build_metrics(suite, status_path, figure_path)
    assert metrics["artifacts"]["final_mph_bytes"] > 1_000_000
    assert metrics["quality"]["comsol_error_count"] == 0
    assert metrics["paper_trend"]["delta050_to_delta000_tip_ratio"] == 1.3

    statuses["delta020"]["state"] = "RUNNING"
    status_path.write_text(json.dumps(statuses), encoding="utf-8")
    import pytest

    with pytest.raises(ValueError, match="did not complete cleanly"):
        module.build_metrics(suite, status_path, figure_path)


def test_fig7_mask_comparator_is_exact_for_identical_masks() -> None:
    module_path = IMPLEMENTATION / "compare_fig7_masks.py"
    spec = importlib.util.spec_from_file_location("kobayashi_compare", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    mask = IMPLEMENTATION / "reference_data" / "fig7" / "delta020_t0p8_mask.png"
    result = module.compare(mask, mask)
    assert result["iou"] == 1.0
    assert result["normalized_chamfer"] == 0.0


def test_field_export_to_mask_is_time_explicit_and_oriented(tmp_path: Path) -> None:
    module_path = IMPLEMENTATION / "fields_to_masks.py"
    spec = importlib.util.spec_from_file_location("kobayashi_fields", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    export = tmp_path / "fields.csv"
    export.write_text(
        "% Model: synthetic\n"
        "% x,y,p (1) @ t=0.2,T (1) @ t=0.2,p (1) @ t=0.8,T (1) @ t=0.8\n"
        "0,0,1,0,0,0\n1,0,0,0,0,0\n0,1,0,0,1,0\n1,1,0,0,0,0\n",
        encoding="utf-8",
    )
    output = tmp_path / "masks"
    module.export_masks(export, [(0.2, "early.png"), (0.8, "late.png")], output)
    from PIL import Image

    early = Image.open(output / "early.png").convert("L")
    late = Image.open(output / "late.png").convert("L")
    assert early.getpixel((0, 191)) == 255
    assert late.getpixel((0, 0)) == 255

    import pytest

    with pytest.raises(ValueError, match="missing phase field"):
        module.export_masks(export, [(1.4, "missing.png")], output)
