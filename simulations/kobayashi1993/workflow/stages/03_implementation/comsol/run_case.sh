#!/usr/bin/env bash
set -euo pipefail

case_dir="${1:?usage: run_case.sh CASE_DIR}"
case_dir="$(cd "$case_dir" && pwd)"
cd "$case_dir"
test -s Kobayashi1993.java
test -s case.properties

remote_home="$(getent passwd "$(id -un)" | cut -d: -f6)"
test -n "$remote_home"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
source "$remote_home/yeesuan/envs/comsol64_env.sh"
comsol_bin="$remote_home/yeesuan/apps/comsol64/multiphysics/bin/comsol"
test -x "$comsol_bin"

prefix="$(awk -F= '$1 == "prefix" {print $2}' case.properties | tail -1)"
case "$prefix" in
  ''|*[!A-Za-z0-9_.-]*) printf 'invalid prefix\n' >&2; exit 2 ;;
esac

case_args=()
while IFS='=' read -r key value; do
  [[ -n "$key" ]] || continue
  case "$key" in
    prefix|delta|noiseAmp|noiseSeed|R0|hmesh|maxStep|dtout|tfinal) ;;
    *) printf 'unsupported case key: %s\n' "$key" >&2; exit 2 ;;
  esac
  case "$value" in
    ''|*[!A-Za-z0-9_.+\-\[\]]*) printf 'unsafe value for %s\n' "$key" >&2; exit 2 ;;
  esac
  case_args+=("$key=$value")
done < case.properties

"$comsol_bin" compile Kobayashi1993.java
test -s Kobayashi1993.class
if [[ -s Kobayashi1993.class.status ]]; then
  ! grep -Eiq '(fail|error)' Kobayashi1993.class.status
fi
"$comsol_bin" batch \
  -inputfile Kobayashi1993.class \
  -nosave \
  -batchlog "${prefix}_comsol_batch.log" \
  -prodargs "${case_args[@]}"

test -s "${prefix}_built.mph"
test -s "${prefix}_solved.mph"
test -s "${prefix}_global.csv"
test -s "${prefix}_fields.csv"
! grep -Eiq '(Error|Exception|FileNotFound)' "${prefix}_comsol_batch.log"
sha256sum \
  Kobayashi1993.java case.properties \
  "${prefix}_built.mph" "${prefix}_solved.mph" \
  "${prefix}_global.csv" "${prefix}_fields.csv" \
  > "${prefix}_manifest.sha256"
