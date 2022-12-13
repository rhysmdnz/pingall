import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
from deps import nixdeps
import json

ACCOUNT_ID = "596309961293"


class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        return aws.get_regions().names

    def __init__(self):
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

        def lambda_policy(lambda_name: str) -> str:
            return json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": "logs:CreateLogGroup",
                            "Resource": f"arn:aws:logs:{location}:{ACCOUNT_ID}:*",
                        },
                        {
                            "Action": [
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            "Resource": f"arn:aws:logs:{location}:{ACCOUNT_ID}:log-group:/aws/lambda/{lambda_name}:*",
                            "Effect": "Allow",
                        },
                    ],
                }
            )

        lambda_logging = aws.iam.Policy(
            f"lambdaLogging-{location}",
            path="/",
            description="IAM policy for logging from a lambda",
            policy=lambda_.name.apply(lambda_policy),
        )
        aws.iam.RolePolicyAttachment(
            f"lambdaLogs-{location}",
            role=role.name,
            policy_arn=lambda_logging.arn,
        )

        url = aws.lambda_.FunctionUrl(
            f"woof-{location}",
            function_name=lambda_.arn,
            authorization_type="NONE",
            opts=opts,
        )
        return url.function_url
