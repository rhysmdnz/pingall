let
  sources = import ./nix/sources.nix;
  pkgs = import sources.nixpkgs { system = "x86_64-linux"; };
  nocargo-lib = pkgs.callPackage "${sources.nocargo}/lib" { };
  toml2json = pkgs.callPackage "${sources.nocargo}/toml2json" { };
  defaultRegistries = {
    "https://github.com/rust-lang/crates.io-index" =
      nocargo-lib.pkg-info.mkIndex pkgs.fetchurl sources.registry-crates-io
        (pkgs.callPackage "${sources.nocargo}/crates-io-override" { });
  };
  mkIndex = nocargo-lib.pkg-info.mkIndex pkgs.fetchurl;
  buildRustCrate = pkgs.callPackage "${sources.nocargo}/build-rust-crate" { inherit toml2json nocargo-lib; };
  mkRustPackageOrWorkspace = pkgs.callPackage nocargo-lib.support.mkRustPackageOrWorkspace {
    inherit defaultRegistries buildRustCrate;
  };
in
(mkRustPackageOrWorkspace
  {
    # The root directory, which contains `Cargo.lock` and top-level `Cargo.toml`
    # (the one containing `[workspace]` for workspace).
    src = (pkgs.nix-gitignore.gitignoreSource [ ] ./app);

    # If you use registries other than crates.io, they should be imported in flake inputs,
    # and specified here. Note that registry should be initialized via `mkIndex`,
    # with an optional override.
    #extraRegistries = {
    # "https://example-registry.org" = nocargo.lib.${system}.mkIndex inputs.example-registry {};
    #};

    # If you use crates from git URLs, they should be imported in flake inputs,
    # and specified here.
    #gitSrcs = {
    # "https://github.com/some/repo" = inputs.example-git-source;
    #};

    # If some crates in your dependency closure require packages from nixpkgs.
    # You can override the argument for `stdenv.mkDerivation` to add them.
    #
    # Popular `-sys` crates overrides are maintained in `./crates-io-override/default.nix`
    # to make them work out-of-box. PRs are welcome.
    #buildCrateOverrides = with nixpkgs.legacyPackages.${system}; {};

    # We use the rustc from nixpkgs by default.
    # But you can override it, for example, with a nightly version from https://github.com/oxalica/rust-overlay
    # rustc = rust-overlay.packages.${system}.rust-nightly_2022-07-01;
  }).release
