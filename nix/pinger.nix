{ lib, pkgsStatic, naersk, nix-gitignore, cloud ? null }:
# ((mkRustPackageOrWorkspace { src = (nix-gitignore.gitignoreSource [ ] ../app); }).release.pinger.override { features = lib.optional (cloud != null) cloud; }).bin
naersk.buildPackage {
  src = (nix-gitignore.gitignoreSource [ ] ../app);

  nativeBuildInputs = [ pkgsStatic.stdenv.cc ];

  cargoBuildOptions = x: x ++ [ "--features ${cloud}" ];

  # Tells Cargo that we're building for musl.
  # (https://doc.rust-lang.org/cargo/reference/config.html#buildtarget)
  CARGO_BUILD_TARGET = "x86_64-unknown-linux-musl";

  # Tells Cargo to enable static compilation.
  # (https://doc.rust-lang.org/cargo/reference/config.html#buildrustflags)
  #
  # Note that the resulting binary might still be considered dynamically
  # linked by ldd, but that's just because the binary might have
  # position-independent-execution enabled.
  # (see: https://github.com/rust-lang/rust/issues/79624#issuecomment-737415388)
  CARGO_BUILD_RUSTFLAGS = "-C target-feature=+crt-static";
}
