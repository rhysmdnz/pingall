import pulumi
import pulumi_docker as docker
from pulumi_gcp import cloudrun
import pulumi_google_native as google_native
from deps import nixdeps


class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        return cloudrun.get_locations().locations

    def __init__(self):
        # Import the program's configuration settings.
        config = pulumi.Config()
        image_name = config.get("imageName", "my-app")

        # Import the provider's configuration settings.
        gcp_config = pulumi.Config("google-native")
        self.project = gcp_config.require("project")

        # Create a container image for the service.
        self.image = docker.Image(
            "image",
            image_name=f"gcr.io/{self.project}/{image_name}",
            build=docker.DockerBuild(
                context=nixdeps["gcp.wrapperImageBuildDir"],
                env={"DOCKER_DEFAULT_PLATFORM": "linux/amd64"},
            ),
        )

    def make_function(self, location: str) -> pulumi.Output[str]:
        service_account = google_native.iam.v1.ServiceAccount(
            f"ping-{location}", account_id=f"ping-{location}"
        )
        # Create a Cloud Run service definition.
        service = google_native.run.v2.Service(
            f"ping-{location}",
            service_id=f"ping-{location}",
            location=location,
            project=self.project,
            template=google_native.run.v2.GoogleCloudRunV2RevisionTemplateArgs(
                service_account=service_account.email,
                containers=[
                    google_native.run.v2.GoogleCloudRunV2ContainerArgs(
                        image=self.image.image_name,
                        resources=google_native.run.v2.GoogleCloudRunV2ResourceRequirementsArgs(
                            limits=dict(
                                memory="1Gi",
                                cpu="1",
                            ),
                        ),
                    ),
                ],
                max_instance_request_concurrency=50,
            ),
        )

        # Create an IAM member to make the service publicly accessible.
        google_native.run.v2.ServiceIamPolicy(
            f"invoker-{location}",
            service_id=service.service_id,
            location=location,
            bindings=[
                google_native.run.v2.GoogleIamV1BindingArgs(
                    members=["allUsers"], role="roles/run.invoker"
                ),
            ],
        )
        return service.uri
