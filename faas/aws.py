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
        ]:
            url = ""
        else:
            url = aws.lambda_.FunctionUrl(
                f"woof-{location}",
                function_name=lambda_.arn,
                authorization_type="NONE",
                opts=opts,
            ).function_url
        return url
