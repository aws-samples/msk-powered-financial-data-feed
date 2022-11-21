
# Create the VPC endpoint and consumer instance in a new VPC

This stack creates a client EC2 instance and a VPC endpoint in a new client VPC. The Kafka consumer app is pre-installed on the client instance. The stack also creates a Route 53 Private Hosted Zone to alias the MSK broker names to the VPC endpoint's name. This enables the app to reach the remote VPC endpoint service via PrivateLink.

To deploy the resources:
```
cdk synth
cdk deploy
```

