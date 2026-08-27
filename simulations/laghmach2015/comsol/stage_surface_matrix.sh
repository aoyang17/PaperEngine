#!/usr/bin/env bash
set -euo pipefail

matrix_root="${1:?usage: stage_surface_matrix.sh REMOTE_MATRIX_ROOT}"
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$matrix_root"

submit_case() {
  local label="$1"
  local radius="$2"
  local run_dir="$matrix_root/$label"
  mkdir -p "$run_dir"
  cp "$source_dir/Laghmach2015.java" "$source_dir/run_remote.sh" "$source_dir/comsol_omp.slurm" "$run_dir/"
  (
    cd "$run_dir"
    sbatch --parsable \
      --export="ALL,CASE_DIR=$run_dir,CASE_PREFIX=$label,CASE_RN=$radius,CASE_T=303[K],CASE_STRETCH=6,CASE_TOPO_ON=1,CASE_MAX_STEP=0.001[s],CASE_TFINAL=150[s]" \
      comsol_omp.slurm
  )
}

printf 'Rn5_job=%s\n' "$(submit_case Rn5 '5[nm]')"
printf 'Rn9_job=%s\n' "$(submit_case Rn9 '9[nm]')"
