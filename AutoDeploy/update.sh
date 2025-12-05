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
# 3. Verify manifest - bail on failure
# ==========================

echo "Verifying manifest"
pushd $REPO_DIR
../crypto/verify.sh
popd

# ==========================
# 4. Rebuild and Restart
# ==========================
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
