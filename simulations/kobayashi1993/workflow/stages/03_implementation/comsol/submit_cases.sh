#!/usr/bin/env bash
set -euo pipefail

suite_root="${1:?usage: submit_cases.sh REMOTE_SUITE_ROOT PROPERTY_FILE...}"
shift
test "$#" -gt 0
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$suite_root"
suite_root="$(cd "$suite_root" && pwd)"

for property_file in "$@"; do
  if [[ "$property_file" != /* ]]; then
    property_file="$source_dir/$property_file"
  fi
  test -s "$property_file"
  prefix="$(awk -F= '$1 == "prefix" {print $2}' "$property_file" | tail -1)"
  case "$prefix" in
    ''|*[!A-Za-z0-9_.-]*) printf 'invalid prefix in %s\n' "$property_file" >&2; exit 2 ;;
  esac
  run_dir="$suite_root/$prefix"
  mkdir -p "$run_dir"
  cp \
    "$source_dir/Kobayashi1993.java" \
    "$source_dir/run_case.sh" \
    "$source_dir/comsol_case.slurm" \
    "$run_dir/"
  cp "$property_file" "$run_dir/case.properties"
  (
    cd "$run_dir"
    job_id="$(sbatch --parsable --export="ALL,CASE_DIR=$run_dir" comsol_case.slurm)"
    printf '%s=%s\n' "$prefix" "$job_id"
  )
done
