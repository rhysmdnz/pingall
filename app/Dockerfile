FROM rust:1 as builder
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true
ENV SCCACHE_DIR=/var/cache/sccache
RUN --mount=type=cache,target=/usr/local/cargo/registry cargo install sccache
ENV RUSTC_WRAPPER=sccache
WORKDIR /app
COPY . .
RUN --mount=type=cache,target=/usr/local/cargo/registry --mount=type=cache,target=/var/cache/sccache cargo install --path .


FROM debian:stable-slim as runner
COPY --from=builder /usr/local/cargo/bin/pinger /usr/local/bin/pinger
ENV ROCKET_ADDRESS=0.0.0.0
EXPOSE 8000
CMD ["pinger"]
