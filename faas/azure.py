import pulumi
import pulumi_azure_native as azure_native
from deps import nixdeps


class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        # TODO: Get This from the API
        return [
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
            # westus2 tragically had to shut down because they were couldn't compete with catalyst cloud :((
            "westus3",
        ]

    def __init__(self):
        self.resource_group = azure_native.resources.ResourceGroup("pingall")

        self.storage_account = azure_native.storage.StorageAccount(
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
            account_name=self.storage_account.name,
        )

        self.code_blob = azure_native.storage.Blob(
            "zip",
            resource_group_name=self.resource_group.name,
            account_name=self.storage_account.name,
            container_name=code_container.name,
            source=pulumi.asset.FileArchive(nixdeps["azure.archive"]),
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
            identity=azure_native.web.ManagedServiceIdentityArgs(
                type=azure_native.web.ManagedServiceIdentityType.SYSTEM_ASSIGNED
            ),
            site_config=azure_native.web.SiteConfigArgs(
                app_settings=[
                    azure_native.web.NameValuePairArgs(
                        name="FUNCTIONS_EXTENSION_VERSION", value="~4"
                    ),
                    azure_native.web.NameValuePairArgs(
                        name="FUNCTIONS_WORKER_RUNTIME", value="custom"
                    ),
                    azure_native.web.NameValuePairArgs(
                        name="AzureWebJobsStorage__accountName",
                        value=self.storage_account.name,
                    ),
                    azure_native.web.NameValuePairArgs(
                        name="WEBSITE_RUN_FROM_PACKAGE", value=self.code_blob.url
                    ),
                ],
                http20_enabled=True,
                ftps_state=azure_native.web.FtpsState.DISABLED,
            ),
        )
        azure_native.authorization.RoleAssignment(
            f"codeAccessAssignment{location}",
            principal_id=app.identity.principal_id,
            principal_type="ServicePrincipal",
            role_definition_id="/subscriptions/2917da89-7d5e-48a5-aa1e-01f15223e9e8/providers/Microsoft.Authorization/roleDefinitions/2a2b9908-6ea1-4ae2-8e65-a410df84e7d1",
            scope=pulumi.Output.format(
                "subscriptions/2917da89-7d5e-48a5-aa1e-01f15223e9e8/resourceGroups/{0}/providers/Microsoft.Storage/storageAccounts/{1}",
                self.resource_group.name,
                self.storage_account.name,
            ),
        )
        azure_native.authorization.RoleAssignment(
            f"storageOwnerAssignment{location}",
            principal_id=app.identity.principal_id,
            principal_type="ServicePrincipal",
            role_definition_id="/subscriptions/2917da89-7d5e-48a5-aa1e-01f15223e9e8/providers/Microsoft.Authorization/roleDefinitions/b7e6dc6d-f1e8-4753-8033-0f276bb0955b",
            scope=pulumi.Output.format(
                "subscriptions/2917da89-7d5e-48a5-aa1e-01f15223e9e8/resourceGroups/{0}/providers/Microsoft.Storage/storageAccounts/{1}",
                self.resource_group.name,
                self.storage_account.name,
            ),
        )
        return app.default_host_name.apply(lambda host: f"https://{host}/api/pinger")
