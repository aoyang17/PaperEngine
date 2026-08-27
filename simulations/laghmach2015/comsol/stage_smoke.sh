#!/usr/bin/env bash
set -euo pipefail

smoke_dir="${1:?usage: stage_smoke.sh REMOTE_SMOKE_DIR}"
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$smoke_dir"
cp "$source_dir/Laghmach2015.java" "$source_dir/run_remote.sh" "$smoke_dir/"
cd "$smoke_dir"
env \
  CASE_PREFIX=smoke \
  CASE_TFINAL='1[s]' \
  CASE_MAX_STEP='0.02[s]' \
  CASE_HMESH='2[nm]' \
  bash run_remote.sh "$smoke_dir"
