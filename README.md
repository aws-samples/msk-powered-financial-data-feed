## Publish a real-time financial data feed to a Kafka client using Amazon MSK 

This application demonstrates how to publish a real-time financial data feed as a service on AWS. It contains the code for a data provider to send streaming data to its clients via an Amazon MSK cluster. Clients can consume the data using a Kafka client SDK. If the client application is in another AWS account, it can connect to the provider's feed directly through AWS PrivateLink. The client can subscribe to a Kafka topic (e.g., "stock-quotes") to consume the data that is of interest. The client and provider authenticate each other using mutual TLS.

## Pre-requisites
You will need an existing Amazon Linux EC2  instance to deploy the cluster. This deployment instance should have git, jq, Python 3.7, and the AWS CLI **v2** installed. To install AWS CLI v2, see [Installing the latest version of the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) You should run ```aws configure``` to specify the AWS access key and secret access key of an IAM user who has sufficient privileges (e.g., an admin) to create a new VPC, launch an MSK cluster and launch EC2 instances. The cluster will be deployed to your default region using AWS CDK. To install CDK on the deployment instance, see [Getting started with the AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html). 

## Deployment steps
### Creating a Private Certificate Authority 
The Kafka provider and client will authenticate each other using mutual TLS (mTLS), so you  need to use AWS Certificate Manager to create a Private Certificate Authority and root certificate as follows. 

1. Log in to your [AWS Certificate Manager](https://console.aws.amazon.com/acm) console and click on **AWS Private CA**. 
2. Click  **Create a Private CA** , select CA type **Root** and fill in your organization details. Leave the other options as default and click **Create CA**. 
3. Once the CA becomes active, select **Actions -> Install CA certificate** on the CA's details page to install the root certificate. 


### Deploying the MSK Cluster and Provider EC2 Instance
These steps will create a new Kafka provider VPC, and launch the Amazon MSK cluster there, along with a new EC2 instance to run the provider app. 

1. Log in to your deployment EC2 instance using ssh, and clone this repo. 
```
git clone git@github.com:aws-samples/msk-powered-financial-data-feed.git msk-feed
cd msk-feed
export PATH=-$PATH:$HOME/msk-feed/bin
``` 
2. Add the following shell environment variables to your .bashrc file
```
echo "export CDK_DEFAULT_ACCOUNT=123456789012" >> ~/.bashrc
echo "export CDK_DEFAULT_REGION="us-east-1" >> ~/.bashrc
echo "export EC2_KEY_PAIR='Your EC2 keypair'" >> env-vars.sh >> ~/.bashrc
echo "export ACM_PCA_ARN='ARN of your ACM Private Hosted CA'" >> ~/.bashrc
```
Then update the above variables with your AWS account number, region you are deploying to, and EC2 keypair name for that region. For the **ACM_PCA_ARN** variable, you can paste in the ARN of your Private CA from the CA details page. Then run : ``` source ~/.bashrc``` 

3. Deploy the MSK cluster and other required infrastructure using the following cdk commands. 
```
cd cluster-setup
cdk bootstrap
cdk synth
cdk deploy
```

4. Select your [MSK cluster](https://console.aws.com/msk) in the AWS console after it bceomes Active and copy its ARN to your clipboard. Then enable both public and private access by running
```
    msk-public-access <your MSK ARN>
```

### Setting up the provider instance
1. After the above command finishes, ssh into the newly created provider EC2 instance as **ec2-user**. The name of the instance will end in **msk-provider**. In your home directory there, run the following commands.

```
git clone git@github.com:aws-samples/msk-powered-financial-data-feed.git msk-feed
export PATH=$PATH:$HOME/msk-feed/bin 
```

2. Run ```aws configure``` and enter the AWS credentials of a user with admin privileges. Make sure to specify the same region that your MSK cluster got deployed. 

3. Set up some environment variables in your .bashrc file. 
```
echo "export TLSBROKERS='Your Bootstrap servers string'" >> ~/.bashrc
echo "export ZKNODES='Your Zookeeper connection string'" >> ~/.bashrc 
```
You can find the values for your Bootstrap servers string and Zookeeper connections string by clicking on **View client information**  on your MSK cluster details page. Use the **Plaintext** Zookeeper connection string. For TLSBROKERS, use the **Private endpoint**. Then  run ```source ~/.bashrc```

4. In your ```kafka``` directory, create a private key and certificate signing request (CSR) file for the MSK broker's certificate. Make sure you type the **-k** option on the **makecsr** command below.
```
    cd kafka
    makecsr -k
```
Enter your orgranization's domain name when asked for first and last name and enter additional organization details when prompted. Then make up a password for the your keystore when prompted. You will now have a CSR file called client_cert.csr.

5. Sign the CSR and issue the certificate by running
```
    issuecert client_cert.csr
```
This uses your ACM Private Certificate Authority to sign the CSR and generate the certificate file, called ```client_cert.pem```. 

6. Import the certificate into your keystore
```
    importcert client_cert.pem
```

7. Update the advertised listener ports on the MSK cluster
```
    kfeed -u
```
The above command updates the advertised listeners on the MSK cluster to allow the private NLB to send a message to a specific broker at a specific port (e.g., port 8441 for broker b-1). If prompted to confirm removing the temporary ACL, type yes.

### Deploying the NLB 
The steps below will create a private NLB plus a VPC endpoint service that allows the cluster to be accessed via PrivateLink. It also sets up a Route 53 Private Hosted Zone that aliases the Kafka broker DNS names to the NLB.


1. Go back to your deployment instance and add the following environment variable to your .bashrc file.
```
   echo "export TLSBROKERS='Your Bootstrap servers string'" >> ~/.bashrc
   echo "export ZKNODES='Your Zookeeper connection string'" >> ~/.bashrc 
   echo "export MSK_VPC_ID='The VPC ID of the MSK cluster'" >> ~/.bashrc
```
Make sure you use the MSK cluster's **private endpoint** for the TLSBROKERS string, not the public one. Again, use the **Plaintext** Zookeeper connection string for ZKNODES. You can find both these strings when you click the **View client information** button in your MSK cluster details page. You can find the ID of the VPC where the MSK cluster was deployed in your AWS VPC console.  Then run ```source ~/.bashrc```

2.  Type the following commands to deploy the NLB CDK stack.
```
cd ../nlb-setup
cdk synth
cdk deploy
```

### Deploying the Kafka client instance
The steps below will create a client EC2 instance in a new VPC to run the Kafka consumer application. These steps will also create a VPC endpoint that connects to the MSK cluster via PrivateLink, and a Route 53 Private Hosted Zone that aliases the broker names to the VPC endpoint's DNS name.

1. Go to your deployment instance and add the following environment variable to your .bashrc file.
```
    echo "export MSK_VPC_ENDPOINT_SERVICE=com.amazonaws.vpce.<region>.vpce-svc-<your-endpoint-service-ID>" >> ~/.bashrc
```
You can find the name of your VPC endpoint service by clicking on **Endpoint services** in your AWS VPC console, and selecting the service, and looking in the service details section. The name begins with com.amazonaws.

2. Then create the client infrastructure in a new client VPC by typing the following.
```
    cd ../client-setup
    cdk synth
    cdk deploy
```

3. You should now see a new client instance in your EC2 dashboard. Ssh to it and set up the following environment variable in your .bashrc file. 
```
echo "export TLSBROKERS='Your Bootstrap servers string'" >> ~/.bashrc
```
Run ```source ~/.bashrc``` after updating the value.

### Deploying the financial data feed provider and consumer 
The steps below will deploy the data feed producer and consumer apps on the provider and client EC2 instances respectively. 


1. Go to your provider instance, and create a private key and certificate signing request (CSR) file for the provider application. 
```
    cd msk-feed/data-feed-examples 
    makecsr
```
Enter your organization details for the CSR. Then make up a password for the destination keystore when prompted. Enter that same password when prompted for the Import password. You will now have the following files: 
* private_key.pem - Private key for mutual TLS
* client_cert.csr - Certificate signing request file
* truststore.pem - Store of external certificates that are trusted

2. Sign and issue the certificate file by running
```
    issuecert client_cert.csr
```
This uses your ACM Private Certificate Authority to sign and generate the certificate file, called ```client_cert.pem```. You can use this same ```issuecert``` tool to sign and issue certificates for your clients who will consume the data feed.

3, In a separate terminal window, ssh to your client instance and enter the following.
```
    git clone git@github.com:aws-samples/msk-powered-financial-data-feed.git msk-feed
    export PATH=$PATH:$HOME/msk-feed/bin 
    cd msk-feed/data-feed-examples
    makecsr
```
Enter the organization details for the client when prompted.

4, Copy the client_cert.csr file to the provider instance, and run the ```issuecert``` command on it to generate the SSL cert for the client application. (In a real-world scenario, the client wopuld upload the CSR file to the provider's Website for signing.)
```
    issuecert client_cert.csr
```
Copy the generated client_cert.pem file back to the client instance, and put it in the ```data-feed-examples``` folder. In your provider instance, you can rename this to consumer_cert,pem and put it in a separate folder.

4. On your provider instance, create a test Kafka topic named topic1 using the **kfeed** command.
```
    kfeed --create-topic topic1
```
The above can be shortened to ```kfeed -c topic1```

5. In the provider instance, add an ACL to allow the producer to write to the topic. 
```
    kfeed --allow client_cert.pem producer topic1
```
The above can be abbreviated as ```kfeed -a client_cert.pem p topic1``` Note that **client_cert.pem** is the certificate you generated earlier for the producer.

6. Find the cert that you generated for the consumer, and add an ACL for the consumer application to consume from the topic, as follows.
```
    kfeed --allow consumer_cert.pem consumer topic1
```
The above can be abbreviated as ```kfeed -a consumer_cert.pem c topic1``` 


7. In both the client and provider instances, install the required Python modules by running the following commands. 
```
    cd data-feed-examples
    alias python=python3
    python -m pip install -r requirements.txt
```

7. In your client instance, run the test consumer application. 
```
    python consumer.py
```

7. In your provider instance, run the test producer application.
```
    python producer.py 
```

8. **alpaca-producer.py** is an example of a Kafka producer that ingests data from a market data provider called [Alpaca Markets](https://alpaca.markets/) and feeds the data to your MSK Cluster. Alpaca offers a [free tier](https://alpaca.markets/data) API that is a good example of real world data, since it is live market data. There are a few steps that you need to perform to make it work correctly.

9. Sign up for the Alpaca free tier API.

10. Generate an **API KEY ID** and a **Secret Key**

11. Export them to the following environment variables.

    ```
    export APCA_API_KEY_ID="<API KEY ID>"
    export APCA_API_SECRET_KEY="<Secret Key>"
    ```

12. Log in using ssh to the provider instance and create the following topics. 
```
    kfeed -c trade 
    kfeed -c quote
    kfeed -c crypto_quote
    kfeed -l 
``` 

13. Add the necessary ACLs to give the producer and consumer access to the topics. 
```
    kfeed -a client_cert.pem p trade
    kfeed -a client_cert.pem p quote
    kfeed -a client_cert.pem p crypto_quote
    kfeed -a consumer_cert.pem c trade
    kfeed -a consumer_cert.pem c quote
    kfeed -a consumer_cert.pem c crypto_quote
```


14. Run the producer in the ```data-feed-examples``` folder. 
```
    python3 alpaca-producer.py
```

15. In a separate terminal window, ssh to the client instance and run the consumer in the ```data-feed-examples``` folder
```
    python3 alpaca-consumer.py
```

## Contributors

[Diego Soares](https://www.linkedin.com/in/diegogsoares/)

[Rana Dutt](https://www.linkedin.com/in/ranadutt/)

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

