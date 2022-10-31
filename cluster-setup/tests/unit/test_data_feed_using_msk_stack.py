import aws_cdk as core
import aws_cdk.assertions as assertions

from data_feed_using_msk.data_feed_using_msk_stack import DataFeedUsingMskStack

# example tests. To run these tests, uncomment this file along with the example
# resource in data_feed_using_msk/data_feed_using_msk_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = DataFeedUsingMskStack(app, "data-feed-using-msk")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
