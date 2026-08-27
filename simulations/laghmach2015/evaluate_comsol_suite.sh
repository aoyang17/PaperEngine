#!/usr/bin/env bash
set -euo pipefail

suite_root="${1:?usage: evaluate_comsol_suite.sh COMSOL_SUITE_ROOT OUTPUT_DIR}"
output_dir="${2:?usage: evaluate_comsol_suite.sh COMSOL_SUITE_ROOT OUTPUT_DIR}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/../.." && pwd)"
python_bin="${LAGHMACH_PYTHON_BIN:-python3}"
export PYTHONPATH="$project_root/src"
mkdir -p "$output_dir"

baseline="$suite_root/core/baseline/baseline_radius_and_quality.csv"
control="$suite_root/core/control/control_radius_and_quality.csv"
fine_grid="$suite_root/core/fine_grid/fine_grid_radius_and_quality.csv"
half_timestep="$suite_root/core/half_timestep/half_timestep_radius_and_quality.csv"
surface_rn5="$suite_root/surface/Rn5/Rn5_radius_and_quality.csv"
surface_rn9="$suite_root/surface/Rn9/Rn9_radius_and_quality.csv"

"$python_bin" "$script_dir/postprocess_comsol.py" \
  --baseline "$baseline" \
  --control "$control" \
  --fine-grid "$fine_grid" \
  --half-timestep "$half_timestep" \
  --surface-large-nucleus "$surface_rn9" \
  --surface-small-nucleus "$surface_rn5" \
  --reference-radius "$script_dir/reference_data/figure6b_T303K_lambda4_radius.csv" \
  --reference-stress "$script_dir/reference_data/figure6b_T303K_lambda4_stress.csv" \
  --threshold-run "$suite_root/threshold/T298_L2/T298_L2_radius_and_quality.csv" \
  --threshold-run "$suite_root/threshold/T298_L3/T298_L3_radius_and_quality.csv" \
  --threshold-run "$suite_root/threshold/T303_L3/T303_L3_radius_and_quality.csv" \
  --threshold-run "$suite_root/threshold/T303_L4/T303_L4_radius_and_quality.csv" \
  --threshold-run "$suite_root/threshold/T308_L4/T308_L4_radius_and_quality.csv" \
  --threshold-run "$suite_root/threshold/T308_L5/T308_L5_radius_and_quality.csv" \
  --output "$output_dir/comsol_metrics.json"

"$python_bin" -m paper_engine.simulation_reproduction validate \
  "$script_dir/case.yml" "$output_dir/comsol_metrics.json" \
  --report "$output_dir/comsol_acceptance.md" \
  --json-report "$output_dir/comsol_acceptance.json"
