# --- Stage 1: Builder ---
FROM gcc:latest AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential cmake git libssl-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . .

# 1. Configure with CMAKE_INSTALL_PREFIX to point to a temporary export folder
# 2. Build the project
# 3. Run 'cmake --install' to move the exe, data/, and libs into /export
RUN cmake -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/export \
    -DBUILD_VOICE_SUPPORT=OFF . \
    && cmake --build build -j3 \
    && cmake --install build

# --- Stage 2: Runner ---
# Using the specific nonroot tag for Debian 12
FROM gcr.io/distroless/cc-debian12:nonroot AS runner
WORKDIR /app

# Copy EVERYTHING from the builder's export directory
# This includes the exe and the 'data' folder
COPY --from=builder --chown=nonroot:nonroot /export .

ENTRYPOINT ["/app/discord_bot"]
