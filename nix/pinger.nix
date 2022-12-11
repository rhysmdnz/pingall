{ lib, mkRustPackageOrWorkspace, nix-gitignore, cloud ? null }:
((mkRustPackageOrWorkspace { src = (nix-gitignore.gitignoreSource [ ] ../app); }).release.pinger.override { features = lib.optional (cloud != null) cloud; }).bin
