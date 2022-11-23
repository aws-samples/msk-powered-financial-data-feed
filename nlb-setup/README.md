
# Create the NLB and Endpoint Service

This stack runs in the MSK cluster's VPC after the cluster is created. It creates the Private NLB which targets the cluster, and also creates a VPC Endpoint Service for access to the cluster. 

To deploy the resources:
```
cdk synth
cdk deploy
```

