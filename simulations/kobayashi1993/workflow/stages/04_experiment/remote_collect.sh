#!/usr/bin/env bash
set -euo pipefail

suite="${1:?usage: remote_collect.sh SUITE_DIR ARCHIVE_PATH}"
archive="${2:?usage: remote_collect.sh SUITE_DIR ARCHIVE_PATH}"
cases=(
  delta000 delta005 delta010 delta020 delta050
  control_delta000 control_delta020 mesh_fine timestep_fine seed_small seed_large
)
declare -A jobs=(
  [delta000]=37198 [delta005]=37199 [delta010]=37200 [delta020]=37201 [delta050]=37202
  [control_delta000]=37203 [control_delta020]=37204 [mesh_fine]=37205
  [timestep_fine]=37206 [seed_small]=37207 [seed_large]=37208
)

for case_id in "${cases[@]}"; do
  job_id="${jobs[$case_id]}"
  state="$(sacct -X -j "$job_id" --format=State,ExitCode -n -P | awk 'NF {print; exit}')"
  [[ "$state" == "COMPLETED|0:0" ]]
  case_dir="$suite/$case_id"
  test -s "$case_dir/${case_id}_solved.mph"
  test -s "$case_dir/${case_id}_global.csv"
  test -s "$case_dir/${case_id}_fields.csv"
  test -s "$case_dir/${case_id}_comsol_batch.log"
  test -f "$case_dir/slurm.${job_id}.out"
  test -f "$case_dir/slurm.${job_id}.err"
  ! grep -Eiq '(Error|Exception|FileNotFound|Cannot open display)' \
    "$case_dir/${case_id}_comsol_batch.log" \
    "$case_dir/slurm.${job_id}.out" \
    "$case_dir/slurm.${job_id}.err"
  (cd "$case_dir" && sha256sum -c "${case_id}_manifest.sha256")
done

tar -czf "$archive" \
  --exclude='*.mph' --exclude='*.class' --exclude='*.java' \
  -C "$suite" "${cases[@]}"
sha256sum "$archive" > "${archive}.sha256"
stat -c 'archive=%n bytes=%s modified=%y' "$archive"
