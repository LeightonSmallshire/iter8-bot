FROM debian:bookworm-slim AS builder
RUN apt-get update && apt-get install -y build-essential cmake
WORKDIR /build
COPY . .
RUN cmake -DCMAKE_BUILD_TYPE=Release . && make -j3

FROM gcr.io/distroless/cc-debian12:nonroot AS runner
WORKDIR /app
COPY --chown=nonroot:nonroot --from=builder /build/discord_bot .
ENTRYPOINT ["/app/discord_bot"]
