#!/usr/bin/env bash
set -euo pipefail

case_dir="${1:?usage: run_mph_remote.sh CASE_DIR}"
input_mph="${CASE_INPUT_MPH:?set CASE_INPUT_MPH to a built MPH file}"
case_prefix="${CASE_PREFIX:?set CASE_PREFIX}"
parameter_names="${CASE_PARAMETER_NAMES:-}"
parameter_values="${CASE_PARAMETER_VALUES:-}"
parameter_file="${CASE_PARAMETER_FILE:-}"

remote_user_home="$(getent passwd "$(id -un)" | cut -d: -f6)"
test -n "$remote_user_home"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
source "$remote_user_home/yeesuan/envs/comsol64_env.sh"
comsol_bin="$remote_user_home/yeesuan/apps/comsol64/multiphysics/bin/comsol"

mkdir -p "$case_dir"
case_dir="$(cd "$case_dir" && pwd)"
test -s "$input_mph"

batch_args=(
  batch
  -inputfile "$input_mph"
  -outputfile "$case_dir/${case_prefix}_solved.mph"
  -study std1
  -batchlog "$case_dir/${case_prefix}_comsol_batch.log"
)
if [[ -n "$parameter_file" ]]; then
  test -s "$parameter_file"
  batch_args+=( -paramfile "$parameter_file" )
elif [[ -n "$parameter_names" || -n "$parameter_values" ]]; then
  test -n "$parameter_names"
  test -n "$parameter_values"
  batch_args+=( -pname "$parameter_names" -plist "$parameter_values" )
fi

"$comsol_bin" "${batch_args[@]}"
test -s "$case_dir/${case_prefix}_solved.mph"
