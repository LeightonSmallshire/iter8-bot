#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/../.."

MANIFEST_FILE="manifest.txt"
SIGNATURE_FILE="manifest.sig"
KEY_FILE="$(dirname "$0")/private.pem.enc"

# 1. Generate Manifest
# shellcheck disable=SC2094
find . \
  \( -path "./.venv" -prune \) -o \
  \( \
    -type f \
    -path "./AutoDeploy/*" -o \
    -name "docker-compose.yml" -o \
    -name "Dockerfile*" \
  \) \
  ! -name "${MANIFEST_FILE}" \
  ! -name "${SIGNATURE_FILE}" \
  ! -name ".env" \
  -exec sha256sum {} + > "${MANIFEST_FILE}"


echo "Manifest generated"

# 2. Sign Manifest
openssl pkeyutl -sign \
  -inkey "${KEY_FILE}" \
  -in "${MANIFEST_FILE}" \
  -out "${SIGNATURE_FILE}" \
  -rawin

echo "Manifest signed"

#AutoDeploy/crypto/verify.sh
