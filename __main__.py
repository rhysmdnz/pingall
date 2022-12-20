# pyright: reportShadowedImports=false

from faas import gcp
from faas import azure
from faas import aws
from faas import alicloud
import pulumi

results = {}

for provider in [gcp, azure, aws, alicloud]:
    pulumi.info(f"Running: {provider.__name__}")
    deployer = provider.Deployer()
    locations = deployer.list_locations()

    results[provider.__name__] = {loc: deployer.make_function(loc) for loc in locations}

pulumi.export("urls", results)
