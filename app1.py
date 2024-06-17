

import aws_cdk as cdk
import os
from aws_cdk import (
    Aws
)

from dataFeedMsk.dataFeedMsk import dataFeedMsk
from dataFeedMsk import parameters
from dataFeedMsk.dataFeedMskCrossAccount import dataFeedMskCrossAccount

                                                        
app = cdk.App()

aws_env = cdk.Environment(account=os.environ["CDK_DEFAULT_ACCOUNT"], region=os.environ["CDK_DEFAULT_REGION"])
dataFeedMsk(app, f"{parameters.project}-{parameters.env}-{parameters.app}-dataFeedMskAwsBlogStack", env=aws_env)

app.synth()