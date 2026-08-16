#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET="${ROOT_DIR}/.backend-deps"

python3 -m pip install --target "${TARGET}" -r "${ROOT_DIR}/requirements-backend.txt"
echo "backend dependencies installed in ${TARGET}"

