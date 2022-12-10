# pyright: reportShadowedImports=false
import pulumi
import pulumi_docker as docker
from pulumi_gcp import cloudrun, config as gcp_config

# Import the program's configuration settings.
config = pulumi.Config()
app_path = config.get("appPath", "./app")
image_name = config.get("imageName", "my-app")
container_port = config.get_int("containerPort", 8080)
cpu = config.get_int("cpu", 1)
memory = config.get("memory", "1Gi")
concurrency = config.get_float("concurrency", 50)

# Import the provider's configuration settings.
gcp_config = pulumi.Config("gcp")
location = gcp_config.require("region")
project = gcp_config.require("project")

# Create a container image for the service.
image = docker.Image(
    "image",
    image_name=f"gcr.io/{project}/{image_name}",
    build=docker.DockerBuild(
        context=app_path, env={"DOCKER_DEFAULT_PLATFORM": "linux/amd64"}
    ),
)


def make_service(location):

    # Create a Cloud Run service definition.
    service = cloudrun.Service(
        f"ping-{location}",
        cloudrun.ServiceArgs(
            location=location,
            template=cloudrun.ServiceTemplateArgs(
                spec=cloudrun.ServiceTemplateSpecArgs(
                    containers=[
                        cloudrun.ServiceTemplateSpecContainerArgs(
                            image=image.image_name,
                            resources=cloudrun.ServiceTemplateSpecContainerResourcesArgs(
                                limits=dict(
                                    memory=memory,
                                    cpu=cpu,
                                ),
                            ),
                            ports=[
                                cloudrun.ServiceTemplateSpecContainerPortArgs(
                                    container_port=container_port,
                                ),
                            ],
                            envs=[
                                cloudrun.ServiceTemplateSpecContainerEnvArgs(
                                    name="FLASK_RUN_PORT",
                                    value=container_port,
                                ),
                            ],
                        ),
                    ],
                    container_concurrency=concurrency,
                ),
            ),
        ),
    )

    # Create an IAM member to make the service publicly accessible.
    invoker = cloudrun.IamMember(
        f"invoker-{location}",
        cloudrun.IamMemberArgs(
            location=location,
            service=service.name,
            role="roles/run.invoker",
            member="allUsers",
        ),
    )

    return service.statuses.apply(lambda statuses: statuses[0].url)


urls = {
    location: make_service(location) for location in cloudrun.get_locations().locations
}

# Export the URL of the service.
pulumi.export("url", urls)
