import pulumi
import pulumi_docker as docker
from pulumi_gcp import cloudrun, config as gcp_config, serviceaccount
import aiohttp
from deps import nixdeps


class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        return cloudrun.get_locations().locations

    def __init__(self):
        # Import the program's configuration settings.
        config = pulumi.Config()
        app_path = config.get("appPath", "./app")
        image_name = config.get("imageName", "my-app")

        # Import the provider's configuration settings.
        gcp_config = pulumi.Config("gcp")
        location = gcp_config.require("region")
        project = gcp_config.require("project")

        # Create a container image for the service.
        self.image = docker.Image(
            "image",
            image_name=f"gcr.io/{project}/{image_name}",
            build=docker.DockerBuild(
                context=nixdeps["gcp.wrapperImageBuildDir"],
                env={"DOCKER_DEFAULT_PLATFORM": "linux/amd64"},
            ),
        )

    def make_function(self, location: str) -> pulumi.Output[str]:
        # Create a Cloud Run service definition.
        service = cloudrun.Service(
            f"ping-{location}",
            cloudrun.ServiceArgs(
                location=location,
                template=cloudrun.ServiceTemplateArgs(
                    spec=cloudrun.ServiceTemplateSpecArgs(
                        containers=[
                            cloudrun.ServiceTemplateSpecContainerArgs(
                                image=self.image.image_name,
                                resources=cloudrun.ServiceTemplateSpecContainerResourcesArgs(
                                    limits=dict(
                                        memory="1Gi",
                                        cpu=1,
                                    ),
                                ),
                            ),
                        ],
                        container_concurrency=50,
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


class Invoker:
    def __init__(self):
        self.token = serviceaccount.get_account_id_token()

    async def invoke(self, url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers={"Authorization": f"Bearer {self.token}"}
            ) as response:
                response.raise_for_status()
                return await response.text()
