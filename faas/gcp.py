import pulumi
from pulumi_gcp import cloudrun
import pulumi_google_native as google_native
from deps import nixdeps
import pulumi_containerregistry as containerregistry


class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        return filter(lambda l: l != "me-central2", cloudrun.get_locations().locations) 

    def __init__(self):
        # Import the program's configuration settings.
        config = pulumi.Config()
        self.image_name = config.get("imageName", "my-app")

        # Import the provider's configuration settings.
        gcp_config = pulumi.Config("google-native")
        self.project = gcp_config.require("project")

    def make_function(self, location: str) -> pulumi.Output[str]:
        registry = google_native.artifactregistry.v1.Repository(
            f"ping-{location}-docker",
            format=google_native.artifactregistry.v1.RepositoryFormat.DOCKER,
            location=location,
            project=self.project,
            repository_id="pinger",
            mode=google_native.artifactregistry.v1.RepositoryMode.STANDARD_REPOSITORY,
        )
        # Create a container image for the service.
        image = containerregistry.Resource(
            f"image-{location}",
            image=pulumi.FileAsset(nixdeps["gcp.image"]),
            remote_tag=f"{location}-docker.pkg.dev/{self.project}/pinger/{self.image_name}",
            opts=pulumi.ResourceOptions(depends_on=[registry])
        )
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
                        image=image.remote_tag,
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
