{ lib, runCommand, dockerTools, pinger, name }: 
let buildUncompressedLayeredImage = lib.makeOverridable ({ name, ... }@args:
    let
      stream = dockerTools.streamLayeredImage args;
    in
    runCommand "${baseNameOf name}.tar"
      {
        inherit (stream) imageName;
        passthru = { inherit (stream) imageTag; };
      } "${stream} > $out"
  );
in
buildUncompressedLayeredImage {
  # namespaced to a domain we control, because otherwise dependency confusion on docker hub becomes a concern
  name = name;
  # version the image with the hash of the pinger we're using.
  tag = builtins.head (builtins.split "-" (lib.lists.last (builtins.split "/" pinger.outPath)));
  # if additional contents are added, rethink the above versioning scheme.
  contents = [ pinger ];
  config = {
    Cmd = [ "/bin/pinger" ];
  };
}
