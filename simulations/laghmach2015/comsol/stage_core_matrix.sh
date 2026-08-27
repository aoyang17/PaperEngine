#!/usr/bin/env bash
set -euo pipefail

matrix_root="${1:?usage: stage_core_matrix.sh REMOTE_MATRIX_ROOT}"
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$matrix_root"

submit_case() {
  local label="$1"
  local topo="$2"
  local mesh="$3"
  local max_step="$4"
  local run_dir="$matrix_root/$label"
  mkdir -p "$run_dir"
  cp "$source_dir/Laghmach2015.java" "$source_dir/run_remote.sh" "$source_dir/comsol_omp.slurm" "$run_dir/"
  (
    cd "$run_dir"
    sbatch --parsable \
      --export="ALL,CASE_DIR=$run_dir,CASE_PREFIX=$label,CASE_TOPO_ON=$topo,CASE_HMESH=$mesh,CASE_MAX_STEP=$max_step" \
      comsol_omp.slurm
  )
}

printf 'baseline_job=%s\n' "$(submit_case baseline 1 '1[nm]' '0.01[s]')"
printf 'control_job=%s\n' "$(submit_case control 0 '1[nm]' '0.01[s]')"
printf 'fine_grid_job=%s\n' "$(submit_case fine_grid 1 '0.5[nm]' '0.01[s]')"
printf 'half_timestep_job=%s\n' "$(submit_case half_timestep 1 '1[nm]' '0.005[s]')"
