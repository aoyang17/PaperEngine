#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "$script_dir/../.." && pwd)"
python_bin="${LAGHMACH_PYTHON_BIN:-python3}"
case_file="$script_dir/case.yml"
output_root="$project_root/tmp/runs/reference"
case_root="$output_root/laghmach2015"
export PYTHONPATH="$project_root/src"

run_reference() {
  "$python_bin" "$script_dir/reference_solver.py" \
    --case "$case_file" \
    --output-root "$output_root" \
    "$@"
}

run_reference --run-id variational_central_topology_on_t150 --topology on --final-time 150 --dt 0.002
run_reference --run-id variational_topology_off_t100 --topology off --final-time 100 --dt 0.002
run_reference --run-id convergence_grid_0p5_t150 --topology on --grid-nm 0.5 --final-time 150 --dt 0.002
run_reference --run-id convergence_dt_0p001_t150 --topology on --final-time 150 --dt 0.001

run_reference --run-id threshold_T298_L2 --temperature-K 298 --stretch 2 --final-time 100
run_reference --run-id threshold_T298_L3 --temperature-K 298 --stretch 3 --final-time 100
run_reference --run-id threshold_T303_L3 --temperature-K 303 --stretch 3 --final-time 100
run_reference --run-id threshold_T308_L4 --temperature-K 308 --stretch 4 --final-time 100
run_reference --run-id threshold_T308_L5 --temperature-K 308 --stretch 5 --final-time 100

run_reference --run-id surface_Rn5_T303_L6 --initial-radius-nm 5 --temperature-K 303 --stretch 6 --final-time 100
run_reference --run-id surface_Rn9_T303_L6 --initial-radius-nm 9 --temperature-K 303 --stretch 6 --final-time 70

"$python_bin" "$script_dir/postprocess_reference.py" \
  --case "$case_file" \
  --baseline-run "$case_root/variational_central_topology_on_t150" \
  --control-run "$case_root/variational_topology_off_t100" \
  --reference-radius "$script_dir/reference_data/figure6b_T303K_lambda4_radius.csv" \
  --fine-grid-run "$case_root/convergence_grid_0p5_t150" \
  --half-timestep-run "$case_root/convergence_dt_0p001_t150" \
  --threshold-run "$case_root/threshold_T298_L2" \
  --threshold-run "$case_root/threshold_T298_L3" \
  --threshold-run "$case_root/threshold_T303_L3" \
  --threshold-run "$case_root/variational_central_topology_on_t150" \
  --threshold-run "$case_root/threshold_T308_L4" \
  --threshold-run "$case_root/threshold_T308_L5" \
  --surface-large-nucleus-run "$case_root/surface_Rn9_T303_L6" \
  --surface-small-nucleus-run "$case_root/surface_Rn5_T303_L6" \
  --output "$case_root/core_metrics_thresholds.json"

set +e
"$python_bin" -m paper_engine.simulation_reproduction validate \
  "$case_file" "$case_root/core_metrics_thresholds.json" \
  --report "$case_root/reference_acceptance_thresholds.md" \
  --json-report "$case_root/reference_acceptance_thresholds.json"
validation_status=$?
set -e
if [[ "$validation_status" -ne 0 && "$validation_status" -ne 2 ]]; then
  exit "$validation_status"
fi

"$python_bin" "$script_dir/make_figures.py" \
  --baseline "$case_root/variational_central_topology_on_t150/raw/radius_history.csv" \
  --control "$case_root/variational_topology_off_t100/raw/radius_history.csv" \
  --reference "$script_dir/reference_data/figure6b_T303K_lambda4_radius.csv" \
  --output "$case_root/radius_comparison.svg"
"$python_bin" "$script_dir/make_free_energy_figure.py" \
  --output "$case_root/free_energy_figure2.svg"
"$python_bin" "$script_dir/make_field_figures.py" \
  --fields "$case_root/variational_central_topology_on_t150/raw/final_fields.npz" \
  --output-directory "$case_root/field_figures"
"$python_bin" "$script_dir/make_surface_figure.py" \
  --rn5 "$case_root/surface_Rn5_T303_L6/raw/radius_history.csv" \
  --rn9 "$case_root/surface_Rn9_T303_L6/raw/radius_history.csv" \
  --output "$case_root/surface_energy_nucleus_comparison.svg"

printf 'reference_suite_validation_exit=%s\n' "$validation_status"
printf 'reference_suite_output=%s\n' "$case_root"
