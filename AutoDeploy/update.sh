#!/usr/bin/env bash
set -euo pipefail

# ==========================
# Configuration Variables
# ==========================
REPO_URL="https://github.com/LeightonSmallshire/iter8-bot.git"
REPO_DIR="./repo"
BRANCH_NAME="${BRANCH_NAME:-main}"
TAG_NAME="${TAG_NAME:-iter8-runner:latest}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"
CONTAINER_NAME="${CONTAINER_NAME:-iter8-runner}"

# ==========================
# 1. Clone repo if missing
# ==========================
if [ ! -d "$REPO_DIR/.git" ]; then
    echo "Repository not found. Cloning..."
    git clone "$REPO_URL" "$REPO_DIR"
fi

# ==========================
# 2. Pull latest + hard reset
# ==========================
echo "Fetching and resetting to branch: $BRANCH_NAME"
git --git-dir=$REPO_DIR/.git --work-tree=$REPO_DIR fetch --all
git --git-dir=$REPO_DIR/.git --work-tree=$REPO_DIR reset --hard "origin/${BRANCH_NAME}"

# ==========================
# Verify dockerfile signature - bail on failure
# ==========================
echo "Verifying dockerfile signature"
openssl pkeyutl -verify -pubin -inkey "./crypto/public.pem" -sigfile "$REPO_DIR/Dockerfile.sig" -in "$REPO_DIR/Dockerfile"

echo "Verifying docker-compose signature"
openssl pkeyutl -verify -pubin -inkey "./crypto/public.pem" -sigfile "$REPO_DIR/docker-compose.yml.sig" -in "$REPO_DIR/docker-compose.yml"

# todo; single signature for hazmat files?

echo "Accepted."
echo "Rebuilding..."

docker compose \
  -f $REPO_DIR/docker-compose.yml \
  -p autorun-iter8-bot \
  --env-file ./.env \
  up \
  --build \
  --always-recreate-deps \
  --renew-anon-volumes \
  --remove-orphans \
  --force-recreate \
  -d

## ==========================
## 3. Docker build
## ==========================
#echo "Building Docker image: $TAG_NAME"
#docker build -t "$TAG_NAME" -f "Dockerfile" .
#
## ==========================
## 4. Remove old container (ignore errors)
## ==========================
#echo "Removing existing container (if any): $CONTAINER_NAME"
#docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
#
## ==========================
## 5. Run new container
## ==========================
#echo "Starting container: $CONTAINER_NAME"
#docker run -d \
#    --name "$CONTAINER_NAME" \
#    --restart unless-stopped \
#    --read-only \
#    --env-file "../.env" \
#    -v "iter8-bot-data:/app/data" \
#    --tmpfs "/home/nonroot/.cache:rw,noexec,size=256m,uid=0,gid=0,mode=1777" \
#    "$TAG_NAME"
#
#echo "Done."
