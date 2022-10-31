## Publish a real-time financial data feed to a Kafka client using Amazon MSK 

This application demonstrates how to publish a real-time financial data feed as a service on AWS. It contains the code for a data provider to send streaming data to its clients via an Amazon MSK cluster. Clients can consume the data using a Kafka client SDK. If the client application is in another AWS account, it can connect to the provider's feed directly through AWS PrivateLink. The client can subscribe to a Kafka topic (e.g., "stock-quotes") to consume the data that is of interest. The client and provider authenticate each other using mutual TLS.

## Pre-requisites
You will need an existing Amazon Linux EC2  instance to deploy the cluster and run the Kafka client application. This client instance should have git, Python 3.7, and the AWS CLI installed. You should run **aws configure** to specify the AWS access key and secret access key of an IAM user who has sufficient privileges (e.g., an admin) to create a new VPC, launch an MSK cluster and launch EC2 instances. The cluster will be deployed to your default region using AWS CDK. To install CDK on the client instance, see [Getting started with the AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html). 

## Deployment steps
### Creating a Private Certificate Authority 
The Kafka provider and client will authenticate each other using mutual TLS (mTLS), so you  need to use AWS Certificate Manager to create a Private Certificate Authority and root certificate as follows. 

1. Log in to your [AWS Certificate Manager](https://console.aws.amazon.com/acm) console and click on **AWS Private CA**. 
2. Click  **Create a Private CA** , select CA type **Root** and fill in your organization details. Leave the other options as default and click **Create CA**. 
3. Once the CA becomes active, select **Actions -> Install CA certificate** on the CA's details page to install the root certificate. 


### Deploying the MSK Cluster and  Provider EC2 Instance
These steps will create a new VPC, and launch the MSK cluster there, along with a new EC2 instance to run the provider app. 

1. Log in to your client EC2 instance using ssh and clone this repo. 
```
git clone git@github.com:aws-samples/msk-powered-financial-data-feed.git
cd msk-powered-financial-data-feed
``` 
2. Edit the ```env-vars.sh``` shell script file and update the environment variables there. For the **ACM_PCA_ARN** variable, you can paste in the ARN of your Private CA from
the CA details page. Then run the shell script: ``` source env-vars.sh``` 

3. Deploy the required infrastructure using the following cdk commands. 
```
cdk synth
cdk deploy
```
4. After the ```cdk deploy``` command finishes, ssh into the newly created provider EC2 instance as ec2-user. You should see a directory named ```kafka``` in your home directory. Then run the following commands.

```
git clone git@github.com:aws-samples/msk-powered-financial-data-feed.git
cp -r msk-powered-financial-data-feed/bin $HOME/bin 
export PATH=$PATH:$HOME/bin 
cd kafka
```
5. Generate a certificate signing request (CSR) for the client cert.  The command below will prompt you to enter a password for your keystore and your organization details. 
```
    makecsr
```
You now have a CSR file named ```client-cert.csr```

6. Run the following command to sign and issue the client cert. 
```
      issuecert client-cert.csr > client-cert.json 
```
7. Copy the certificate strings from the ```client-cert.json``` file to a new file named ```client-cert.pem``` as described in Step 10 at [Mutual TLS authentication](https://docs.aws.amazon.com/msk/latest/developerguide/msk-authentication.html) 

8. Run the following command to add this certificate to your keystore so you can present it when you talk to the MSK brokers.
```
    importcert client-cert.pem
```
   Type ```yes``` when asked if you want to install the reply. You now have a new file named ```client.properties``` which will be used by your Kafka application. 

9. Test that you can create a  topic and run the Kafka producer and consumer console client applications as described in the section **To produce and consume messages using authentication** at [Mutual TLS authentication](https://docs.aws.amazon.com/msk/latest/developerguide/msk-authentication.html)  
 
## Contributors

[Diego Soares](https://www.linkedin.com/in/diegogsoares/)

[Rana Dutt](https://www.linkedin.com/in/ranadutt/)

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
