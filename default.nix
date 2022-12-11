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
    src = (pkgs.nix-gitignore.gitignoreSource [ ] ./app);
  }).release.pinger.bin
