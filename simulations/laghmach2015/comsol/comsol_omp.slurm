#!/usr/bin/env bash
#SBATCH --job-name=laghmach2015
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --partition=cn_768_917
#SBATCH --output=comsol_slurm_%j.out
#SBATCH --error=comsol_slurm_%j.err

set -euo pipefail

case_dir="${CASE_DIR:?submit with: sbatch --export=ALL,CASE_DIR=/absolute/case/path comsol_omp.slurm}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
bash "$case_dir/run_remote.sh" "$case_dir"

case_prefix="${CASE_PREFIX:-baseline}"
test -s "$case_dir/${case_prefix}_solved.mph"
test -s "$case_dir/${case_prefix}_radius_and_quality.csv"
