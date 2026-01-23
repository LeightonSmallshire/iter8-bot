#!/bin/bash

set -e

pushd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." > /dev/null

GITHUB_USER=LeightonSmallshire

# 1. Load variables from .env
export $(grep -v '^#' ./build_scripts/.env | xargs)

# 2. Login to GitHub Container Registry
echo "$GITHUB_PAT" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin

# 3. Define the image name (Must be lowercase)
# Format: ghcr.io/OWNER/REPO-NAME
# Using 'iter8-bot' as the package name to match your repo
IMAGE_NAME="ghcr.io/${GITHUB_USER,,}/iter8-bot"

# 4. Build and Push with the SOURCE label
# This label is what links the package to your repository UI
echo "Building and pushing $IMAGE_NAME..."

docker run --privileged --rm tonistiigi/binfmt --install all

docker buildx build \
  --platform linux/arm64,linux/amd64 \
  -f Dockerfile2 \
  -t "$IMAGE_NAME:latest" \
  --label "org.opencontainers.image.source=https://github.com/$GITHUB_USER/iter8-bot" \
  --push .

echo "Upload complete! Check https://github.com/$GITHUB_USER/iter8-bot/packages"
