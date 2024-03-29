# pyright: reportShadowedImports=false

from faas import gcp
from faas import azure
from faas import aws
from faas import alicloud
import pulumi
import pulumi_docker as docker
import pulumi_gcp as pgcp

results = {}

service_account = pgcp.serviceaccount.Account(
    f"ping-service-account", account_id=f"ping-service-account"
)

for provider in [gcp, azure, aws, alicloud]:
    pulumi.info(f"Running: {provider.__name__}")
    deployer = provider.Deployer(calling_service_account=service_account)
    locations = deployer.list_locations()

    results[provider.__name__] = {loc: deployer.make_function(loc) for loc in locations}
    deployer.finish()

pulumi.export("urls", results)


gcp_config = pulumi.Config("gcp")
project = gcp_config.require("project")

registry = pgcp.artifactregistry.Repository(
    f"ping-service-docker",
    format="DOCKER",
    cleanup_policies=[
        pgcp.artifactregistry.RepositoryCleanupPolicyArgs(
            id="delete untagged",
            action="DELETE",
            condition=pgcp.artifactregistry.RepositoryCleanupPolicyConditionArgs(
                tag_state="UNTAGGED"
            ),
        )
    ],
    location="australia-southeast1",
    project=project,
    repository_id="ping-service",
    mode="STANDARD_REPOSITORY",
)

bucket = pgcp.storage.Bucket(
    "ping-service-config",
    location="australia-southeast1",
)
data = pgcp.storage.BucketObject(
    "ping-service-config-data",
    name="config.json",
    source=pulumi.Output.json_dumps(results).apply(lambda x: pulumi.StringAsset(x)),
    bucket=bucket,
)

# Create a container image for the service.
image = docker.Image(
    "ping-service-image",
    build=docker.DockerBuildArgs(
        context="ping-service",
        dockerfile="ping-service/Dockerfile",
        platform="linux/amd64",
    ),
    image_name=f"australia-southeast1-docker.pkg.dev/{project}/ping-service/ping-service",
    opts=pulumi.ResourceOptions(depends_on=[registry]),
)

data_access = pgcp.storage.BucketIAMBinding(
    f"read-data",
    bucket=bucket,
    members=[service_account.member],
    role="roles/storage.objectViewer",
)

# Create a Cloud Run service definition.
service = pgcp.cloudrunv2.Service(
    f"ping-service",
    name=f"ping-service",
    location="australia-southeast1",
    project=project,
    template=pgcp.cloudrunv2.ServiceTemplateArgs(
        service_account=service_account.email,
        containers=[
            pgcp.cloudrunv2.ServiceTemplateContainerArgs(
                image=image.repo_digest,
                envs=[
                    pgcp.cloudrunv2.ServiceTemplateContainerEnvArgs(
                        name="CONFIG_BUCKET", value=bucket.name
                    )
                ],
                resources=pgcp.cloudrunv2.ServiceTemplateContainerResourcesArgs(
                    limits=dict(
                        memory="1Gi",
                        cpu="1",
                    ),
                ),
                startup_probe=pgcp.cloudrunv2.ServiceTemplateContainerStartupProbeArgs(
                    http_get=pgcp.cloudrunv2.ServiceTemplateContainerStartupProbeHttpGetArgs(
                        path="/readiness_check",
                    ),
                ),
                liveness_probe=pgcp.cloudrunv2.ServiceTemplateContainerLivenessProbeArgs(
                    http_get=pgcp.cloudrunv2.ServiceTemplateContainerLivenessProbeHttpGetArgs(
                        path="/liveness_check",
                    ),
                ),
            ),
        ],
        max_instance_request_concurrency=50,
    ),
    opts=pulumi.ResourceOptions(depends_on=[data, data_access]),
)

# Create an IAM member to make the service publicly accessible.
pgcp.cloudrunv2.ServiceIamBinding(
    f"invoker-ping-service",
    name=service.name,
    location="australia-southeast1",
    members=["allUsers"],
    role="roles/run.invoker",
)


pulumi.export("ping-service-url", service.uri)
