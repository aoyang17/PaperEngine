#!/usr/bin/env bash
set -euo pipefail

matrix_root="${1:?usage: stage_threshold_matrix.sh REMOTE_MATRIX_ROOT}"
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$matrix_root"

submit_case() {
  local label="$1"
  local temperature="$2"
  local stretch="$3"
  local run_dir="$matrix_root/$label"
  mkdir -p "$run_dir"
  cp "$source_dir/Laghmach2015.java" "$source_dir/run_remote.sh" "$source_dir/comsol_omp.slurm" "$run_dir/"
  (
    cd "$run_dir"
    sbatch --parsable \
      --export="ALL,CASE_DIR=$run_dir,CASE_PREFIX=$label,CASE_T=$temperature,CASE_STRETCH=$stretch,CASE_TOPO_ON=1,CASE_TFINAL=150[s]" \
      comsol_omp.slurm
  )
}

printf 'T298_L2_job=%s\n' "$(submit_case T298_L2 '298[K]' 2)"
printf 'T298_L3_job=%s\n' "$(submit_case T298_L3 '298[K]' 3)"
printf 'T303_L3_job=%s\n' "$(submit_case T303_L3 '303[K]' 3)"
printf 'T303_L4_job=%s\n' "$(submit_case T303_L4 '303[K]' 4)"
printf 'T308_L4_job=%s\n' "$(submit_case T308_L4 '308[K]' 4)"
printf 'T308_L5_job=%s\n' "$(submit_case T308_L5 '308[K]' 5)"
