import aws_cdk as core
import aws_cdk.assertions as assertions

from nlb_setup.nlb_setup_stack import NlbSetupStack

# example tests. To run these tests, uncomment this file along with the example
# resource in nlb_setup/nlb_setup_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = NlbSetupStack(app, "nlb-setup")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
