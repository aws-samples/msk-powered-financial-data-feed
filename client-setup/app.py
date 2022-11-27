#!/usr/bin/env python3
import os

import aws_cdk as cdk

from client_setup.client_setup_stack import ClientSetupStack


app_account=os.getenv('CDK_DEFAULT_ACCOUNT')
app_region=os.getenv('CDK_DEFAULT_REGION')

app = cdk.App()
ClientSetupStack(app, "ClientSetupStack",
    env=cdk.Environment(account=app_account, region=app_region),
    )

app.synth()
