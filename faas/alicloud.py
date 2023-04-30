import pulumi
import pulumi_alicloud as alicloud
from deps import nixdeps
import json


class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        # Returns regions that we can't use for whatever reason.
        # return alicloud.get_regions().ids
        return [
            "cn-qingdao",
            "cn-beijing",
            "cn-huhehaote",
            "cn-zhangjiakou",
            "cn-shanghai",
            "cn-hongkong",
            "cn-hangzhou",
            "ap-southeast-1",
            "cn-chengdu",
            "cn-shenzhen",
            "us-west-1",
            "ap-northeast-1",
            "eu-central-1",
            "ap-south-1",
            "ap-southeast-3",
            "us-east-1",
            "ap-southeast-2",
            "ap-southeast-5",
            "eu-west-1",
        ]

    def __init__(self):
        self.account_id = alicloud.get_caller_identity().account_id
        pass

    def make_function(self, location):
        provider = alicloud.Provider(f"alicloud-{location}", region=location)
        opts = pulumi.ResourceOptions(provider=provider)

        role = alicloud.ram.Role(
            f"pingerFunctionRole-{location}",
            document=json.dumps(
                {
                    "Version": "1",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": ["fc.aliyuncs.com"]},
                            "Effect": "Allow",
                        }
                    ],
                }
            ),
        )

        #        project = alicloud.log.Project(f"log-project-{location}", opts=opts)

        #        logstore = alicloud.log.Store(
        #            f"pinger-store-{location}",
        #            project=project.name,
        #            name="pinger-store",
        #            opts=opts,
        #        )

        #        alicloud.log.StoreIndex(
        #            f"pinger-store-index-{location}",
        #            logstore=logstore.name,
        #            project=project.name,
        #            full_text=alicloud.log.StoreIndexFullTextArgs(
        #                case_sensitive=False,
        #                include_chinese=False,
        #                token=", '\";=()[]{}?@&<>/:\\n\\t\\r",
        #            ),
        #            opts=opts,
        #        )

        function_service = alicloud.fc.Service(
            f"fs-pinger-{location}",
            role=role.arn,
            #           log_config=alicloud.fc.ServiceLogConfigArgs(
            #               logstore=logstore.name, project=project.name
            #           ),
            opts=opts,
        )

        function_ = alicloud.fc.Function(
            f"pinger-{location}",
            handler="thiscanbeanystring",
            runtime="custom",
            service=function_service.name,
            filename=nixdeps["alicloud.archive"],
            ca_port=9000,
            opts=opts,
        )

        trigger = alicloud.fc.Trigger(
            f"pinger-trigger-{location}",
            function=function_.name,
            service=function_service.name,
            type="http",
            config=json.dumps(
                {
                    "authType": "anonymous",
                    "disableURLInternet": False,
                    "methods": ["GET"],
                }
            ),
            opts=opts,
        )

        def function_policy(project_name: str, account_id: str) -> str:
            return json.dumps(
                {
                    "Version": "1",
                    "Statement": [
                        {
                            "Action": ["log:PostLogStoreLogs"],
                            "Resource": f"acs:log:{location}:{account_id}:project/{project_name}/logstore/pinger-store",
                            "Effect": "Allow",
                        },
                    ],
                }
            )

        # function_logging = alicloud.ram.Policy(
        #    f"functionLogging-{location}",
        #    policy_name=f"functionLogging-{location}",
        #    description="RAM policy for logging from a function",
        #    policy_document=pulumi.Output.all(project.name, self.account_id).apply(
        #        lambda args: function_policy(*args)
        #    ),
        # )
        # alicloud.ram.RolePolicyAttachment(
        #    f"functionLogs-{location}",
        #    policy_name=function_logging.name,
        #    role_name=role.name,
        #    policy_type=function_logging.type,
        # )

        return trigger.url_internet
