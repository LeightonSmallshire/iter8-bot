# syntax=docker/dockerfile:1

FROM debian:13-slim AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libssl-dev \
    liblzma-dev \
    zlib1g-dev \
    libxml2-dev \
    ca-certificates \
    curl \
    libsodium-dev \
    libopus-dev \
    && rm -rf /var/lib/apt/lists/*
