#!/usr/bin/env bash
#SBATCH --job-name=kobayashi93
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --partition=cn_768_917
#SBATCH --output=slurm.%j.out
#SBATCH --error=slurm.%j.err

set -euo pipefail
case_dir="${CASE_DIR:?submit with CASE_DIR=/absolute/run/directory}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
bash "$case_dir/run_case.sh" "$case_dir"
