#!/usr/bin/env bash
#SBATCH --job-name=laghmach-mph
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=comsol_mph_%j.out
#SBATCH --error=comsol_mph_%j.err

set -euo pipefail

case_dir="${CASE_DIR:?submit with CASE_DIR}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
bash "$case_dir/run_mph_remote.sh" "$case_dir"
