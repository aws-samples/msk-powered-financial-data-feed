import aws_cdk as core
import aws_cdk.assertions as assertions

from client_setup.client_setup_stack import ClientSetupStack

# example tests. To run these tests, uncomment this file along with the example
# resource in client_setup/client_setup_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = ClientSetupStack(app, "client-setup")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
