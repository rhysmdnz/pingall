import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
from deps import nixdeps

class Deployer:
    @staticmethod
    def list_locations() -> list[str]:
        return ["us-east-1"]

    def __init__(self):
        # repository = awsx.ecr.Repository("nya")

        # self.image = awsx.ecr.Image("meow",
        #                        repository_url=repository.url,
        #                        env={"DOCKER_DEFAULT_PLATFORM": "linux/amd64"},
        #                        path=nixdeps["aws.wrapperImageBuildDir"])

        self.role = aws.iam.Role("mew", assume_role_policy="""{
          "Version": "2012-10-17",
          "Statement": [
            {
              "Action": "sts:AssumeRole",
              "Principal": {
                "Service": "lambda.amazonaws.com"
              },
              "Effect": "Allow",
              "Sid": ""
            }
          ]
        }
        """)


    def make_function(self, location):
        provider = aws.Provider(f'aws-{location}', region=location)
        opts = pulumi.ResourceOptions(provider=provider)

        lambda_ = aws.lambda_.Function(
            f"awoo-{location}",
            role=self.role.arn,
            runtime="provided.al2",
            handler="thiscanbeanystring",
            code=pulumi.asset.FileArchive(nixdeps["aws.archive"]),
            opts=opts)

        url = aws.lambda_.FunctionUrl(f"woof-{location}", function_name=lambda_.arn, authorization_type="NONE", opts=opts)
        return url.function_url
