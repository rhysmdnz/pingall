# pyright: reportShadowedImports=false
import pulumi
import pulumi_docker as docker
from pulumi_gcp import cloudrun, config as gcp_config
import pulumi_azure_native as azure_native

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


resource_group = azure_native.resources.ResourceGroup("pingall")

storage_account = azure_native.storage.StorageAccount(
    "pingallsa",
    resource_group_name=resource_group.name,
    sku=azure_native.storage.SkuArgs(
        name=azure_native.storage.SkuName.STANDARD_LRS,
    ),
    kind=azure_native.storage.Kind.STORAGE_V2,
)

code_container = azure_native.storage.BlobContainer(
    "zips",
    resource_group_name=resource_group.name,
    account_name=storage_account.name,
)

code_blob = azure_native.storage.Blob(
    "zip",
    resource_group_name=resource_group.name,
    account_name=storage_account.name,
    container_name=code_container.name,
    source=pulumi.asset.FileArchive("./azure-function"),
)

storage_account_keys = azure_native.storage.list_storage_account_keys_output(
    resource_group_name=resource_group.name, account_name=storage_account.name
)
primary_storage_key = storage_account_keys.keys[0].value

storage_connection_string = pulumi.Output.format(
    "DefaultEndpointsProtocol=https;AccountName={0};AccountKey={1}",
    storage_account.name,
    primary_storage_key,
)

blobSAS = azure_native.storage.list_storage_account_service_sas_output(
    account_name=storage_account.name,
    permissions=azure_native.storage.Permissions.R,
    resource_group_name=resource_group.name,
    resource=azure_native.storage.SignedResource.C,
    shared_access_expiry_time="2030-01-01",
    protocols=azure_native.storage.HttpProtocol.HTTPS,
    canonicalized_resource=pulumi.Output.format(
        "/blob/{0}/{1}", storage_account.name, code_container.name
    ),
)

code_blob_url = pulumi.Output.format(
    "https://{0}.blob.core.windows.net/{1}/{2}?{3}",
    storage_account.name,
    code_container.name,
    code_blob.name,
    blobSAS.service_sas_token,
)

# TODO: Get This from the API
azure_regions = [
    "australiaeast",
    "australiasoutheast",
    "brazilsouth",
    "canadacentral",
    "canadaeast",
    "centralindia",
    "centralus",
    "eastasia",
    "eastus",
    "eastus2",
    "francecentral",
    "japaneast",
    "koreacentral",
    "northcentralus",
    "northeurope",
    "norwayeast",
    "southafricanorth",
    "southcentralus",
    "southeastasia",
    "swedencentral",
    "switzerlandnorth",
    "uaenorth",
    "uksouth",
    "ukwest",
    "westcentralus",
    "westeurope",
    "westindia",
    "westus",
    "westus3",
]


def make_azure_function_app(region):
    plan = azure_native.web.AppServicePlan(
        f"plan{region}",
        resource_group_name=resource_group.name,
        sku=azure_native.web.SkuDescriptionArgs(
            name="Y1",
            tier="Dynamic",
        ),
        reserved=True,
        location=region,
    )

    app = azure_native.web.WebApp(
        f"ping-{region}",
        location=region,
        resource_group_name=resource_group.name,
        server_farm_id=plan.id,
        kind="functionapp,linux",
        https_only=True,
        site_config=azure_native.web.SiteConfigArgs(
            app_settings=[
                azure_native.web.NameValuePairArgs(
                    name="FUNCTIONS_EXTENSION_VERSION", value="~4"
                ),
                azure_native.web.NameValuePairArgs(
                    name="FUNCTIONS_WORKER_RUNTIME", value="custom"
                ),
                azure_native.web.NameValuePairArgs(
                    name="AzureWebJobsStorage", value=storage_connection_string
                ),
                azure_native.web.NameValuePairArgs(
                    name="WEBSITE_RUN_FROM_PACKAGE", value=code_blob_url
                ),
            ],
            http20_enabled=True,
            ftps_state=azure_native.web.FtpsState.DISABLED,
        ),
    )
    return app.default_host_name


azure_urls = {region: make_azure_function_app(region) for region in azure_regions}
pulumi.export("azure_url", azure_urls)
