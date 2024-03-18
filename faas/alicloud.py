import pulumi
import pulumi_alicloud as alicloud
import pulumi_alicloud_fc_url as alicloud_fc_url
from deps import nixdeps
import json


class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        # Returns regions that we can't use for whatever reason.
        # return alicloud.get_regions().ids
        return [
            # "cn-qingdao",
            "cn-beijing",
            "cn-huhehaote",
            "cn-zhangjiakou",
            # "cn-shanghai",
            "cn-hongkong",
            "cn-hangzhou",
            "ap-southeast-1",
            "cn-chengdu",
            # "cn-shenzhen",
            "us-west-1",
            "ap-northeast-1",
            "ap-northeast-2",
            "eu-central-1",
            "ap-south-1",
            "ap-southeast-3",
            "us-east-1",
            "ap-southeast-2",
            "ap-southeast-5",
            "ap-southeast-7",
            "eu-west-1",
        ]

    def __init__(self):
        # self.account_id = alicloud.get_caller_identity().account_id
        pass

    def make_function(self, location):
        provider = alicloud.Provider(f"alicloud-{location}", region=location)
        provider_url = alicloud_fc_url.Provider(
            f"alicloud-url-{location}", region=location
        )

        opts = pulumi.ResourceOptions(provider=provider)
        opts_url = pulumi.InvokeOptions(provider=provider_url)

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

        function_service = alicloud.fc.Service(
            f"fs-pinger-{location}",
            role=role.arn,
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

        trigger_http = trigger.id.apply(
            lambda trigger_name: alicloud_fc_url.get_trigger_url(
                service_name=function_service.name,
                function_name=function_.name,
                trigger_name=trigger.name,
                opts=opts_url,
            )
        )

        return trigger_http.url_internet
