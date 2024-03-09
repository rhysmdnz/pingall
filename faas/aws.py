import pulumi
import pulumi_aws as aws
from deps import nixdeps
import json


class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        return aws.get_regions().names

    def __init__(self):
        self.account_id = aws.get_caller_identity().account_id
        pass

    def make_function(self, location):
        provider = aws.Provider(f"aws-{location}", region=location)
        opts = pulumi.ResourceOptions(provider=provider)

        role = aws.iam.Role(
            f"pingerLambdaRole-{location}",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Effect": "Allow",
                        }
                    ],
                }
            ),
        )

        lambda_ = aws.lambda_.Function(
            f"pinger-{location}",
            role=role.arn,
            runtime="provided.al2",
            handler="thiscanbeanystring",
            code=pulumi.asset.FileArchive(nixdeps["aws.archive"]),
            opts=opts,
        )

        def lambda_policy(lambda_name: str, account_id: str) -> str:
            return json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "logs:CreateLogGroup",
                            "Resource": f"arn:aws:logs:{location}:{account_id}:*",
                        },
                        {
                            "Action": [
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            "Resource": f"arn:aws:logs:{location}:{account_id}:log-group:/aws/lambda/{lambda_name}:*",
                            "Effect": "Allow",
                        },
                    ],
                }
            )

        lambda_logging = aws.iam.Policy(
            f"lambdaLogging-{location}",
            path="/",
            description="IAM policy for logging from a lambda",
            policy=pulumi.Output.all(lambda_.name, self.account_id).apply(
                lambda args: lambda_policy(*args)
            ),
        )
        aws.iam.RolePolicyAttachment(
            f"lambdaLogs-{location}",
            role=role.name,
            policy_arn=lambda_logging.arn,
        )

        if location in [
            "eu-central-2",
            "ap-southeast-4",
            "eu-south-2",
            "me-central-1",
            "ap-south-2",
            "il-central-1",
            "ca-west-1",
        ]:
            apigw = aws.apigateway.RestApi(
                f"restApiGateway-{location}",
                endpoint_configuration=aws.apigateway.RestApiEndpointConfigurationArgs(
                    types="REGIONAL"
                ),
                opts=opts,
            )
            resource = aws.apigateway.Resource(
                f"resource-{location}",
                rest_api=apigw.id,
                parent_id=apigw.root_resource_id,
                path_part="{proxy+}",
                opts=opts,
            )
            method = aws.apigateway.Method(
                f"method-{location}",
                rest_api=apigw.id,
                resource_id=resource.id,
                http_method="ANY",
                authorization="NONE",
                opts=opts,
            )
            integration = aws.apigateway.Integration(
                f"integration-{location}",
                rest_api=apigw.id,
                resource_id=resource.id,
                http_method=method.http_method,
                type="AWS_PROXY",
                integration_http_method="POST",
                uri=lambda_.invoke_arn,
                opts=opts,
            )
            method_root = aws.apigateway.Method(
                f"method-root-{location}",
                rest_api=apigw.id,
                resource_id=apigw.root_resource_id,
                http_method="ANY",
                authorization="NONE",
                opts=opts,
            )
            integration_root = aws.apigateway.Integration(
                f"integration-root-{location}",
                rest_api=apigw.id,
                resource_id=apigw.root_resource_id,
                http_method=method.http_method,
                type="AWS_PROXY",
                integration_http_method="POST",
                uri=lambda_.invoke_arn,
                opts=opts,
            )
            deployment = aws.apigateway.Deployment(
                f"deployment-{location}",
                rest_api=apigw.id,
                stage_name="test",
                opts=pulumi.ResourceOptions(
                    provider=provider, depends_on=[integration, integration_root]
                ),
            )
            aws.lambda_.Permission(
                f"allowApiGateway-{location}",
                statement_id="AllowAPIGatewayInvoke",
                action="lambda:InvokeFunction",
                function=lambda_.name,
                principal="apigateway.amazonaws.com",
                source_arn=pulumi.Output.format("{0}/*/*", apigw.execution_arn),
                opts=opts,
            )
            url = deployment.invoke_url
        else:
            url = aws.lambda_.FunctionUrl(
                f"woof-{location}",
                function_name=lambda_.arn,
                authorization_type="NONE",
                opts=opts,
            ).function_url
        return url
