#!/usr/bin/env bash
#SBATCH --job-name=distributedECM
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --partition=cn_768_917
#SBATCH --output=slurm.%j.out
#SBATCH --error=slurm.%j.err

set -euo pipefail
suite_dir="${SLURM_SUBMIT_DIR:?Slurm did not provide its submission directory}"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
bash "$suite_dir/run_suite.sh" "$suite_dir" "cases/uniform.properties cases/heterogeneous.properties"
