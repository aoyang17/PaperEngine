#!/usr/bin/env bash
set -euo pipefail

suite_dir="${1:?usage: run_suite.sh SUITE_DIR}"
suite_dir="$(cd "$suite_dir" && pwd)"
cd "$suite_dir"
test -s distributeECM.java

remote_home="$(getent passwd "$(id -un)" | cut -d: -f6)"
test -n "$remote_home"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
source "$remote_home/yeesuan/envs/comsol64_env.sh"
comsol_bin="$remote_home/yeesuan/apps/comsol64/multiphysics/bin/comsol"
test -x "$comsol_bin"

"$comsol_bin" compile distributeECM.java
test -s distributeECM.class
if [[ -s distributeECM.class.status ]]; then
  ! grep -Eiq '(fail|error)' distributeECM.class.status
fi

suite_log="$suite_dir/distributed_ecm_comsol_batch.log"
: > "$suite_log"
case_pattern="${2:-cases/*.properties}"
for case_file in $case_pattern; do
  case_name="$(basename "$case_file" .properties)"
  case_dir="$suite_dir/results/$case_name"
  mkdir -p "$case_dir"
  cp "$case_file" "$case_dir/case.properties"

  case_args=()
  while IFS='=' read -r key value; do
    [[ -n "$key" ]] || continue
    case "$key" in
      prefix|C_rate|hetero_amp|dt_out|t_final|max_step|ramp_time|SOC0) ;;
      *) printf 'unsupported case key: %s\n' "$key" >&2; exit 2 ;;
    esac
    case "$value" in
      ''|*[!A-Za-z0-9_.+\-\[\]]*) printf 'unsafe value for %s\n' "$key" >&2; exit 2 ;;
    esac
    case_args+=("$key=$value")
  done < "$case_file"

  cd "$case_dir"
  "$comsol_bin" batch \
    -inputfile "$suite_dir/distributeECM.class" \
    -nosave \
    -batchlog "${case_name}_comsol_batch.log" \
    -prodargs "${case_args[@]}"

  prefix="$(awk -F= '$1 == "prefix" {print $2}' case.properties | tail -1)"
  test -s "${prefix}_built.mph"
  test -s "${prefix}_solved.mph"
  test -s "${prefix}_global.csv"
  test -s "${prefix}_fields.csv"
  ! grep -Eiq '(Error|Exception|FileNotFound)' "${case_name}_comsol_batch.log"
  printf '===== %s =====\n' "$case_name" >> "$suite_log"
  sed -n '1,$p' "${case_name}_comsol_batch.log" >> "$suite_log"
  sha256sum \
    "$suite_dir/distributeECM.java" case.properties \
    "${prefix}_built.mph" "${prefix}_solved.mph" \
    "${prefix}_global.csv" "${prefix}_fields.csv" \
    > "${prefix}_manifest.sha256"
  cd "$suite_dir"
done

test -s "$suite_log"
! grep -Eiq '(Error|Exception|FileNotFound)' "$suite_log"

find results -type f -name '*_manifest.sha256' -print0 \
  | sort -z \
  | xargs -0 sha256sum > suite_manifest.sha256
