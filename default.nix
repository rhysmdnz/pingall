let
  sources = import ./nix/sources.nix;

  fenix = import sources.fenix { pkgs = pkgs-x86_64-linux; };

  nativePkgs = import sources.nixpkgs nixpkgsOpts;
  pkgs-x86_64-linux = import sources.nixpkgs (nixpkgsOpts // { system = "x86_64-linux"; });

  toolchain = with fenix;
    combine [
      minimal.rustc
      minimal.cargo
      targets.x86_64-unknown-linux-musl.latest.rust-std
    ];

  naersk = pkgs-x86_64-linux.callPackage sources.naersk {
    cargo = toolchain;
    rustc = toolchain;
  };

  nixpkgsOpts = { overlays = [
    (self: super: { writeJsonChecked = super.callPackage ./nix/json-schema.nix { inherit (sources) schemastore; }; })
  ]; };

  # lib is arch-independent; it speeds up pulumi-driven evals to do it this way since now they never need to evalulate the nativePkgs thunk
  lib = import "${sources.nixpkgs}/lib";

  cloud = {
    gcp.pkgs = pkgs-x86_64-linux;
    azure.pkgs = pkgs-x86_64-linux;
  };
in
{
  gcp = let pkgs = pkgs-x86_64-linux; in lib.recurseIntoAttrs rec {
    pinger = pkgs.callPackage nix/pinger.nix { cloud = "gcp"; inherit naersk; };
    image = pkgs.callPackage nix/image.nix { name = "memes.nz/pinger-gcp"; inherit pinger; };
    wrapperImageBuildDir = pkgs.writeTextDir "Dockerfile" "FROM ${image.imageName}:${image.imageTag}";
  };

  aws = let pkgs = pkgs-x86_64-linux; in lib.recurseIntoAttrs rec {
    pinger = pkgs.callPackage nix/pinger.nix { cloud = "aws"; inherit naersk; };
    archive = pkgs.runCommandLocal "aws-pinger-archive.zip" {} ''
    mkdir build
    cd build
    cp ${pinger}/bin/pinger ./bootstrap

    ${pkgs.zip}/bin/zip -r $out *
    '';
  };


  azure = let pkgs = pkgs-x86_64-linux; in lib.recurseIntoAttrs rec {
    pinger = pkgs.callPackage nix/pinger.nix { cloud = "azure"; inherit naersk; };

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
          defaultExecutablePath = "pinger/pinger";
          workingDirectory = "";
          arguments = [];
        };
        enableForwardingHttpRequest = true;
      };
    }; };

    archive = pkgs.runCommandLocal "azure-pinger-archive.zip" {} ''
    mkdir build
    cd build
    cp ${hostJson} host.json
    mkdir pinger
    cp ${functionJson} pinger/function.json

    cp ${pinger}/bin/pinger ./pinger/pinger

    ${pkgs.zip}/bin/zip -r $out *
    '';
  };

}
