# DOLI node + CLI, собранные из исходников по тегу (официальный docker/Dockerfile собирает только doli-node).
# Сборка: docker compose build   (версия и коммит — в .env)
FROM rust:1.95-bookworm AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake clang libclang-dev llvm-dev libgmp-dev libmpfr-dev \
      librocksdb-dev libssl-dev pkg-config protobuf-compiler zlib1g-dev m4 git \
    && rm -rf /var/lib/apt/lists/*
ARG DOLI_VERSION
ARG DOLI_COMMIT
RUN git clone --depth 1 --branch "${DOLI_VERSION}" https://github.com/doli-network/doli /build \
    && test "$(git -C /build rev-parse HEAD)" = "${DOLI_COMMIT}"
WORKDIR /build
ENV LIBZ_SYS_STATIC=0
RUN cargo build --release -p doli-node -p doli-cli

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libgmp10 libssl3 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1000 doli && useradd -u 1000 -g 1000 -m doli
COPY --from=builder /build/target/release/doli-node /build/target/release/doli /usr/local/bin/
USER doli
WORKDIR /home/doli
ENTRYPOINT []
