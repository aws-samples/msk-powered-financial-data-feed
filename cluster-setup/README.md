
# Create the MSK cluster 

This stack creates the Amazon MSK cluster in a new VPC, along with an EC2 provider instance, and all required security groups. The provider instance is pre-configured with the Kafka tools required to administer topics and issue client certificates, It also has a sample Python provider app that publishes a data feed to the cluster. The cluster can be accessed privately through AWS PrivateLink or publicly.

To deploy the resources:
```
cdk synth
cdk deploy
```

