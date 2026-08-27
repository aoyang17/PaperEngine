from pathlib import Path

import pytest

from simulations.laghmach2015.postprocess_comsol import (
    _parameter_column,
    compare_stress_curve,
    compare_surface_curves,
    extract_history,
)


def test_comsol_history_uses_maximum_incompressibility_error(tmp_path: Path) -> None:
    csv_path = tmp_path / "result.csv"
    csv_path.write_text(
        "Time (s),effectiveRadius (nm),incompL2,incompMax,maxop1(theta),minop1(theta),"
        "sigmaAmorph (MPa),beltInterfaceOverlap,elasticGamma (J/m^2)\n"
        "0,9,0.001,0.004,1,0,2,0.6,0.001\n"
        "100,23,0.002,0.007,1,0,1.8,0.7,0.002\n",
        encoding="utf-8",
    )
    result, fit = extract_history(csv_path)
    assert result["l2_detF_minus_one"] == pytest.approx(0.002)
    assert result["max_abs_detF_minus_one"] == pytest.approx(0.007)
    assert result["stress_drop_fraction"] == pytest.approx(0.1)
    assert fit["r_squared"] != fit["r_squared"]  # fail-closed NaN for fewer than 3 points

    reference = tmp_path / "stress.csv"
    reference.write_text(
        "time_tau1,sigma_xx_MPa\n0,2\n50,1.9\n100,1.8\n",
        encoding="utf-8",
    )
    comparison = compare_stress_curve(csv_path, reference)
    assert comparison["stress_nrmse"] == pytest.approx(0.0)
    assert compare_surface_curves(csv_path, csv_path) == pytest.approx(0.0)
    assert _parameter_column({"T (K)": 303.0}, "temperature") == "T (K)"


def test_comsol_source_preserves_phase_time_units_and_strong_constraint() -> None:
    source = Path("simulations/laghmach2015/comsol/Laghmach2015.java").read_text(encoding="utf-8")
    assert "Aphase*w^2/tau1" in source
    assert "Aphase*barrierCoeff/tau1" in source
    assert "gp*drive/tau1" in source
    assert 'set("incompMax", "maxop1(abs(detF-1))")' in source
    assert "detF-1+pressureGauge*P" in source
