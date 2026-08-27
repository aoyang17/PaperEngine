#!/usr/bin/env bash
set -euo pipefail

case_dir="${1:?usage: run_remote.sh CASE_DIR}"
mkdir -p "$case_dir"
case_dir="$(cd "$case_dir" && pwd)"
remote_user_home="$(getent passwd "$(id -un)" | cut -d: -f6)"
test -n "$remote_user_home"
# The cluster-provided COMSOL environment appends to LD_LIBRARY_PATH without
# guarding against an unset variable.  Define it before sourcing so this
# launcher remains compatible with `set -u` batch shells.
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
source "$remote_user_home/yeesuan/envs/comsol64_env.sh"
comsol_bin="$remote_user_home/yeesuan/apps/comsol64/multiphysics/bin/comsol"
case_prefix="${CASE_PREFIX:-baseline}"
cd "$case_dir"
"$comsol_bin" compile "Laghmach2015.java"
case_args=("prefix=${CASE_PREFIX:-smoke}")
for pair in \
  "T=${CASE_T:-303[K]}" \
  "lamStretch=${CASE_STRETCH:-4}" \
  "topoOn=${CASE_TOPO_ON:-1}" \
  "relaxOn=${CASE_RELAX_ON:-1}" \
  "anisOn=${CASE_ANIS_ON:-0}" \
  "anisMode=${CASE_ANIS_MODE:-2}" \
  "anisDelta=${CASE_ANIS_DELTA:-0.33}" \
  "Rn=${CASE_RN:-9[nm]}" \
  "hmesh=${CASE_HMESH:-2[nm]}" \
  "maxStep=${CASE_MAX_STEP:-0.001[s]}" \
  "tfinal=${CASE_TFINAL:-0.1[s]}" \
  "dtout=${CASE_DTOUT:-0.01[s]}"; do
  case_args+=("$pair")
done
"$comsol_bin" batch \
  -inputfile "Laghmach2015.class" \
  -nosave \
  -batchlog "${case_prefix}_comsol_batch.log" \
  -prodargs "${case_args[@]}"

test -s "${case_prefix}_solved.mph"
test -s "${case_prefix}_radius_and_quality.csv"
