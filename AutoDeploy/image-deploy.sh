#!/bin/bash

# Configuration
IMAGE_NAME="ghcr.io/your-username/your-repo:latest"
COMPOSE_FILE="/home/pi/app/docker-compose.yml"
COSIGN_PUBLIC_KEY="/home/pi/cosign.pub"

echo "Step 1: Pulling latest image..."
docker pull $IMAGE_NAME

echo "Step 2: Verifying Image Signature..."
# Cosign verifies that the image hasn't been tampered with
if cosign verify --key $COSIGN_PUBLIC_KEY $IMAGE_NAME; then
    echo "Signature valid. Proceeding with deployment."
else
    echo "CRITICAL: Signature verification failed! Image may be compromised."
    exit 1
fi

echo "Step 3: Recreating containers..."
# --remove-orphans ensures old service definitions are cleared
docker-compose -f $COMPOSE_FILE up -d --remove-orphans

echo "Deployment successful."
