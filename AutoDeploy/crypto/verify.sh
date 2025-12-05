#!/usr/bin/env bash

set -euo pipefail
set -x # debug

#cd "$(dirname "$0")/../repo"

MANIFEST_FILE="manifest.txt"
SIGNATURE_FILE="manifest.sig"
KEY_FILE="$(dirname "$0")/public.pem"

## 1. Generate Manifest
## shellcheck disable=SC2094
#find . \
#  \( -path "./.venv" -prune \) -o \
#  \( \
#    -type f \
#    -path "./AutoDeploy/*" -o \
#    -name "docker-compose.yml" -o \
#    -name "Dockerfile*" \
#  \) \
#  ! -name "${MANIFEST_FILE}" \
#  ! -name "${SIGNATURE_FILE}" \
#  ! -name ".env" \
#  -exec sha256sum {} + > "${MANIFEST_FILE}"
## todo fail if different instead of writing to it
#
## 2. Verify cryptographic signature
#openssl pkeyutl -verify \
#  -pubin \
#  -inkey "${KEY_FILE}" \
#  -in "${MANIFEST_FILE}" \
#  -sigfile "${SIGNATURE_FILE}" \
#  -rawin
