#!/usr/bin/env bash

t=`mktemp` && (nix-instantiate . > $t && <$t xargs nix-copy-closure --to "$1" && <$t ssh "$1" xargs nix-build --keep-going | xargs nix-copy-closure --from "$1"); rm "$t"
