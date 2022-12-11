FROM rust:1 as builder
WORKDIR /app
COPY . .
ENV CARGO_NET_GIT_FETCH_WITH_CLI=true
RUN cargo install --path .


FROM debian:stable-slim as runner
COPY --from=builder /usr/local/cargo/bin/hello-rocket /usr/local/bin/hello-rocket
ENV ROCKET_ADDRESS=0.0.0.0
EXPOSE 8000
CMD ["hello-rocket"]
