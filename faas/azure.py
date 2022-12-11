import pulumi
import pulumi_azure_native as azure_native


class Azure:
    @staticmethod
    def list_locations() -> list[str]:
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

    def __init__(self):
        self.resource_group = azure_native.resources.ResourceGroup("pingall")

        storage_account = azure_native.storage.StorageAccount(
            "pingallsa",
            resource_group_name=self.resource_group.name,
            sku=azure_native.storage.SkuArgs(
                name=azure_native.storage.SkuName.STANDARD_LRS,
            ),
            kind=azure_native.storage.Kind.STORAGE_V2,
        )

        code_container = azure_native.storage.BlobContainer(
            "zips",
            resource_group_name=self.resource_group.name,
            account_name=storage_account.name,
        )

        code_blob = azure_native.storage.Blob(
            "zip",
            resource_group_name=self.resource_group.name,
            account_name=storage_account.name,
            container_name=code_container.name,
            source=pulumi.asset.FileArchive("./azure-function"),
        )

        storage_account_keys = azure_native.storage.list_storage_account_keys_output(
            resource_group_name=self.resource_group.name,
            account_name=storage_account.name,
        )
        primary_storage_key = storage_account_keys.keys[0].value

        self.storage_connection_string = pulumi.Output.format(
            "DefaultEndpointsProtocol=https;AccountName={0};AccountKey={1}",
            storage_account.name,
            primary_storage_key,
        )

        blobSAS = azure_native.storage.list_storage_account_service_sas_output(
            account_name=storage_account.name,
            permissions=azure_native.storage.Permissions.R,
            resource_group_name=self.resource_group.name,
            resource=azure_native.storage.SignedResource.C,
            shared_access_expiry_time="2030-01-01",
            protocols=azure_native.storage.HttpProtocol.HTTPS,
            canonicalized_resource=pulumi.Output.format(
                "/blob/{0}/{1}", storage_account.name, code_container.name
            ),
        )

        self.code_blob_url = pulumi.Output.format(
            "https://{0}.blob.core.windows.net/{1}/{2}?{3}",
            storage_account.name,
            code_container.name,
            code_blob.name,
            blobSAS.service_sas_token,
        )

    def make_function(self, location: str) -> pulumi.Output[str]:
        plan = azure_native.web.AppServicePlan(
            f"plan{location}",
            resource_group_name=self.resource_group.name,
            sku=azure_native.web.SkuDescriptionArgs(
                name="Y1",
                tier="Dynamic",
            ),
            reserved=True,
            location=location,
        )

        app = azure_native.web.WebApp(
            f"ping-{location}",
            location=location,
            resource_group_name=self.resource_group.name,
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
                        name="AzureWebJobsStorage", value=self.storage_connection_string
                    ),
                    azure_native.web.NameValuePairArgs(
                        name="WEBSITE_RUN_FROM_PACKAGE", value=self.code_blob_url
                    ),
                ],
                http20_enabled=True,
                ftps_state=azure_native.web.FtpsState.DISABLED,
            ),
        )
        return app.default_host_name
