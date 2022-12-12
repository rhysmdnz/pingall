let
  sources = import ./nix/sources.nix;

  nixpkgsOpts = { overlays = [
    (import ./nix/nocargo.nix sources)
    (self: super: { talloc =
                      if super.targetPlatform.isStatic then
                        super.talloc.overrideAttrs (x: {wafConfigureFlags = x.wafConfigureFlags ++ ["--disable-python"];})
                      else super.talloc;
                  } )
    (self: super: { proot =
                      if super.targetPlatform.isStatic then
                        # proot's makefile uses an unprefixed pkg-config, help it along:
                        (super.proot.override (_: { enablePython = false; })).overrideAttrs (x: {LDFLAGS = ["-ltalloc"];})
                      else super.proot;
                  } )
    (self: super: { writeJsonChecked = super.callPackage ./nix/json-schema.nix { inherit (sources) schemastore; }; })
  ]; };

  nativePkgs = import sources.nixpkgs nixpkgsOpts;
  # lib is arch-independent; it speeds up pulumi-driven evals to do it this way since now they never need to evalulate the nativePkgs thunk
  lib = import "${sources.nixpkgs}/lib";

  pkgs-x86_64-linux = import sources.nixpkgs (nixpkgsOpts // { system = "x86_64-linux"; });

  cloud = {
    gcp.pkgs = pkgs-x86_64-linux;
    azure.pkgs = pkgs-x86_64-linux;
  };
in
{
  pinger = nativePkgs.callPackage nix/pinger.nix {};

  gcp = let pkgs = pkgs-x86_64-linux; in lib.recurseIntoAttrs rec {
    pinger = pkgs.callPackage nix/pinger.nix { cloud = "gcp"; };
    image = pkgs.callPackage nix/image.nix { name = "memes.nz/pinger-gcp"; inherit pinger; };
    wrapperImageBuildDir = pkgs.writeTextDir "Dockerfile" "FROM ${image.imageName}:${image.imageTag}";
  };

  aws = let pkgs = pkgs-x86_64-linux; in lib.recurseIntoAttrs rec {
    pinger = pkgs.callPackage nix/pinger.nix { cloud = "aws"; };
    staticProot = pkgs.pkgsStatic.proot;

    bootstrap = pkgs.writeScript "bootstrap" ''#!/bin/sh
    ./proot -b nix:/nix ${pinger}/bin/pinger'';

    archive = pkgs.runCommandLocal "aws-pinger-archive.zip" {} ''
    mkdir build
    cd build
    cp ${staticProot}/bin/proot ./proot
    cp ${bootstrap} ./bootstrap

    mkdir -p nix/store

    <${pkgs.closureInfo {rootPaths = [ pinger ];}}/store-paths xargs -I{} cp -r {} ./nix/store

    ${pkgs.zip}/bin/zip -r $out *
    '';
  };


  azure = let pkgs = pkgs-x86_64-linux; in lib.recurseIntoAttrs rec {
    pinger = pkgs.callPackage nix/pinger.nix { cloud = "azure"; };
    staticProot = pkgs.pkgsStatic.proot;

    functionJson = pkgs.writeJsonChecked { name = "function.json"; content = {
      bindings = [
        {
          authLevel = "anonymous";
          type = "httpTrigger";
          direction = "in";
          name = "req";
          methods = [
            "get"
            "post"
          ];
        }
        {
          type = "http";
          direction = "out";
          name = "res";
        }
      ];
    }; };

    hostJson = pkgs.writeJsonChecked { name = "host.json"; content = {
      version = "2.0";
      logging = {
        logLevel = {
          default = "Trace";
        };
        applicationInsights = {
          samplingSettings = {
            isEnabled = true;
            excludedTypes = "Request";
          };
        };
      };
      extensionBundle = {
        id = "Microsoft.Azure.Functions.ExtensionBundle";
        version = "[3.*, 4.0.0)";
      };
      customHandler = {
        description = {
          defaultExecutablePath = "proot";
          workingDirectory = "";
          arguments = ["-b" "nix:/nix" "${pinger}/bin/pinger"];
        };
        enableForwardingHttpRequest = true;
      };
    }; };

    archive = pkgs.runCommandLocal "azure-pinger-archive.zip" {} ''
    mkdir build
    cd build
    cp ${staticProot}/bin/proot ./proot
    cp ${hostJson} host.json
    mkdir pinger
    cp ${functionJson} pinger/function.json

    mkdir -p nix/store

    <${pkgs.closureInfo {rootPaths = [ pinger ];}}/store-paths xargs -I{} cp -r {} ./nix/store

    ${pkgs.zip}/bin/zip -r $out *
    '';
  };

}
