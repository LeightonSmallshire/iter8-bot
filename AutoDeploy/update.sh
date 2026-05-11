#!/usr/bin/env bash
set -euo pipefail
set -x # debugging only

# =====================================
# Configuration Variables
# =====================================
REPO_URL="https://github.com/LeightonSmallshire/iter8-bot.git"
REPO_DIR="./repo"
BRANCH_NAME="main"
TRUSTED_KEYS="FINGERPRINT_1|FINGERPRINT_2"

# =====================================
# 1. Clone repo if missing
# =====================================
if [ ! -d "$REPO_DIR/.git" ]; then
    echo "Repository not found. Cloning..."
    git clone --recurse-submodules "$REPO_URL" "$REPO_DIR"
fi

# =====================================
# 2. Pull latest + hard reset
# =====================================
# echo "=== Fetching and resetting to branch: $BRANCH_NAME"


echo "=== Forcing origin url"
git -C "$REPO_DIR" remote set-url origin "$REPO_URL"
echo "=== Fetching repo and submodules"
git -C "$REPO_DIR" fetch --all --recurse-submodules --tags
#echo "=== Verifying commit with pinned fingerprint"
#git -C "$REPO_DIR" verify-commit "origin/$BRANCH_NAME" --raw 2>&1 | grep -Eq "VALIDSIG ($TRUSTED_KEYS)" || exit 1
echo "=== Resetting working tree"
git -C "$REPO_DIR" reset --hard "origin/${BRANCH_NAME}"
echo "=== Updating submodules"
git -C "$REPO_DIR" submodule update --init --recursive

# =====================================
# 4. Rebuild and Restart
# =====================================
echo "=== Rebuilding..."

docker compose \
  -f $REPO_DIR/docker-compose.yml \
  --env-file ./.env \
  up \
  --build \
  --always-recreate-deps \
  --renew-anon-volumes \
  --remove-orphans \
  --force-recreate \
  -d
