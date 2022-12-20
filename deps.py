#!/usr/bin/env python3
import os
import subprocess
import pulumi

depNames = [
    "azure.archive",
    "gcp.image",
    "gcp.wrapperImageBuildDir",
    "aws.archive",
    "alicloud.archive",
]

pulumi.info("Loading nix dependencies...")

drvs = (
    subprocess.run(
        ["nix-build", os.path.dirname(os.path.realpath(__file__))]
        + sum((["-A", x] for x in depNames), []),
        check=True,
        stdout=subprocess.PIPE,
    )
    .stdout.decode()
    .split("\n")
)

nixdeps = {name: drv.strip() for name, drv in zip(depNames, drvs)}

pulumi.info("Loading docker dependencies...")
# drv names are always shell-safe, it's fineeeeeeeeeeeeeeeee
subprocess.run(f"docker load <{nixdeps['gcp.image']}", shell=True)

pulumi.info("Dependencies loaded.")
