# Publishing real-time financial data feeds using Amazon Managed Streaming for Kafka

![image](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/f7f19884-9d49-4f70-8246-8cdb8356380d)

## Solution Overview

The code here illustrates taking a raw stock quotes feed, enriching it with a sentiment indicator, and delivering it for consumption by a Kafka client. We use a feed from Alpaca and add an indicator when the stock price moves above or below 5% from the previous business day's closing price.

You will deploy an Apache Flink application that enriches the raw data feed, an MSK cluster that contains the messages streams for both the raw and enriched feeds, and an Amazon OpenSearch database that acts as a persistent data store for querying the data. In a separate account that acts as your customer’s account, you will also deploy an EC2 instance running a Kafka client that consumes the enriched data feed.

## Prerequisites

To deploy this solution, you need to do the following: 
 
•	[Create an AWS account](https://portal.aws.amazon.com/gp/aws/developer/registration/index.html) if you do not already have one and log in. We’ll call this the producer account. Then create an IAM user with full admin permissions as described at [Create an Administrator](https://docs.aws.amazon.com/streams/latest/dev/setting-up.html) User. Log out and log back into the AWS console as this IAM admin user.

•   Create an EC2 key pair named *my-ec2-keypair* in this producer account. If you already have an EC2 key pair, you can skip this step

•	Follow the instructions at [ALPACA_README](ALPACA_README.md) to sign up for a free Basic account at [Alpaca](https://alpaca.markets/data). Alpaca will provide the real time stock quotes for our input data feed. 

•	Install the AWS Command Line Interface (AWS CLI) on your local development machine and create a profile for the admin user as described at [Set Up the AWS CLI](https://docs.aws.amazon.com/streams/latest/dev/setup-awscli.html).   

•	Install the latest version of AWS CDK globally

```
npm install -g aws-cdk@latest
```

## Infrastructure Automation
 
AWS CDK is used to develop parameterized scripts for building the necessary infrastructure. These scripts include various services required for the infrastructure setup.
 
1.	Amazon VPC and Security Groups
2.	KMS Keys
3.	Secrets Manager
4.	SSM Parameter Stores
5.	CloudWatch Log Groups
6.	MSK Cluster
7.	IAM Roles
8.	EC2 Instances
9.	OpenSearch Domain
10.	Apache Flink Application

## Deploying the MSK Cluster 
These steps will create a new provider VPC and launch the Amazon MSK cluster there. It also deploys the Apache Flink application and launches a new EC2 instance to run the application that fetches the raw stock quotes.
 
1.	On your development machine, clone this repo and install the Python packages.

```
git clone git@github.com:aws-samples/msk-powered-financial-data-feed.git
cd msk-powered-financial-data-feed
pip install –r requirements.txt
```

2.	Set the below environment variables. Specify your producer AWS account ID below. 
```
export CDK_DEFAULT_ACCOUNT={your_aws_account_id}
export CDK_DEFAULT_REGION=us-east-1
```

3. Run the following commands to create your config.py file 
```
echo "mskCrossAccountId = '<Your producer AWS account ID>'" > config.py
echo "producerEc2KeyPairName = '' " >> config.py
echo "consumerEc2KeyPairName = '' " >> config.py
echo "mskConsumerPwdParamStoreValue = '' " >> config.py
echo "mskClusterArn = '' " >> config.py

```

4.	Run the following commands to create your alpaca.conf file. 
```
[alpaca]
echo [alpaca] > dataFeedMsk/alpaca.conf
echo ALPACA_API_KEY=your_api_key >> dataFeedMsk/alpaca.conf
echo ALPACA_SECRET_KEY=your_secret_key >> dataFeedMsk/alpaca.conf
```
Edit the alpaca.conf file and replace *your_api_key* and *your_secret_key* with your Alpaca API key and secret key. 

5.	Bootstrap the environment for the producer account.
```
cdk bootstrap aws://{your_aws_account_id}/{your_aws_region}
```

6.	Using your editor or IDE, edit the config.py file. Update the *mskCrossAccountId* parameter with your AWS producer account number.

7.  If you have an existing EC2 key pair, update the *producerEc2KeyPairName* parameter with the name of your key pair

8.	Now, view the *dataFeedMsk/parameters.py* file. Make sure that the *enableSaslScramClientAuth*, *enableClusterConfig*, and *enableClusterPolicy* parameters are set to False. Make sure you are in the directory where the app1.py file is located. Then deploy as follows. 

```
cdk deploy --all --app "python app1.py" --profile {your_profile_name}
```

![cfn_resources](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/d4b88398-32ea-4719-87fc-b5299f041642)

![cfn_resources_1](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/35dfe8ab-e0ba-43f9-92f0-f14030b09b59)

*NOTE*: This step can take up to 45-60 minutes.

9. This deployment creates an S3 bucket to store the solution artifacts, which include the Flink application JAR file, Python scripts, and user data for both the producer and consumer.

![bucket1](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/81459024-5557-4f50-a8e6-8ad0f626715c)

![bucket2](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/d4bb6283-0f38-4e06-9779-edd7fbaf084f)

![bucket3](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/de60279e-b60c-4f0a-9ae3-d4b1e04138ec)

## Deploying Multi-VPC Connectivity and SASL / SCRAM

1.	Now, set the *enableSaslScramClientAuth*, *enableClusterConfig*, and *enableClusterPolicy* parameters in the *parameters.py* file in the *dataFeedMsk* folder to True. 
 
This step will enable the SASL/SCRAM client authentication, Cluster configuration and PrivateLink.

Make sure you are in the directory where the app1.py file is located. Then deploy as follows. 

```
cdk deploy --all --app "python app1.py" --profile {your_profile_name}
```

*NOTE*: This step can take up to 30 minutes.

2. To check the results, click on your MSK cluster in your AWS console, and click the Properties tab. You should see AWS PrivateLink turned on, and SASL/SCRAM as the authentication type.

![msk_cluster](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/d28e34a4-c870-4c0d-bf57-367d0e7581c3)


3. Copy the MSK cluster ARN shown at the top. Edit your *config.py* file and paste the ARN as the value for the mskClusterArn parameter.  Save the updated file.

## Deploying the Data Feed Consumer
The steps below will create an EC2 instance in a new consumer account to run the Kafka consumer application. The application will connect to the MSK cluster via PrivateLink and SASL/SCRAM.

1.  Navigate to Systems Manager (SSM) [Parameter Store](https://console.aws.amazon.com/systems-manager/parameters) in your producer account.

2.  Copy the value of the *blogAws-dev-mskConsumerPwd-ssmParamStore* parameter, and update the *mskConsumerPwdParamStoreValue* parameter in the *config.py* file.

3.  Then, check the value of the parameter named *getAzIdsParamStore* and make a note of these two values.

4.  Create another AWS account for the Kafka consumer if you do not already have one, and log in. Then create an IAM user with full admin permissions as described at [Create an Administrator User](https://docs.aws.amazon.com/streams/latest/dev/setting-up.html#setting-up-iam). Log out and log back in to the AWS console as this IAM admin user. 

5. Make sure you are in the same region as the region you used in the producer account. Create a new EC2 key pair, named e.g.  *my-ec2-consumer-keypair* in this consumer account. Update the value of *consumerEc2KeyPairName* in your config.py file with the name of the key pair you just created. 

6. Navigate to this [Resource Access Manager](https://console.aws.amazon.com/ram/home#Home) (RAM) home page in your consumer account AWS console.

![ram](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/f07d4133-62a6-4755-b6a2-69d68cbee827)

    At the bottom right, you will see a table listing AZ Names and AZ IDs.

![ram_1](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/16af7e28-6af1-441e-9fbe-43dcc79fbf58)

7.  Compare the AZ IDs from the SSM parameter store with the AZ IDs in this table. Identify the corresponding AZ Names for the matching AZ IDs.

8.  Open the *parameters.py* file and insert these AZ Names into the variables *crossAccountAz1* and *crossAccountAz2*.

![ram_2](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/1bb3b341-b825-4069-b3f0-3b10047a0eae)

For example, in the SSM Parameter Store, the values are "use1-az4" and "use1-az6". When you switch to the second account's RAM and compare, you may find that these values correspond to the AZ names "us-east-1a" and "us-east-1b". In that case you need to update the *parameters.py* file with these AZ names by setting crossAccountAz1 to "us-east-1a" and crossAccountAz2 to "us-east-1b".

Note: Ensure that the Availability Zone IDs for both of your accounts are the same.

9.	Now, set up the AWS CLI credentials of your consumer AWS Account. Set the environment variables

```
export CDK_DEFAULT_ACCOUNT={your_aws_account_id}
export CDK_DEFAULT_REGION=us-east-1
```

10.	Bootstrap the consumer account environment. Note that we need to add specific policies to the CDK execution role in this case. 

```
cdk bootstrap aws://{your_aws_account_id}/{your_aws_region} --cloudformation-execution-policies "arn:aws:iam::aws:policy/AmazonMSKFullAccess,arn:aws:iam::aws:policy/AdministratorAccess" –-profile <your-user-profile>
```

11.	We now need to grant the consumer account access to the MSK cluster. In your AWS console, copy the consumer AWS account number to your clipboard. Log out and log back in to your producer AWS account. Find your MSK cluster, click Properties and scroll down to Security settings. Click Edit cluster policy and add the consumer account root to the Principal section as follows. Save the changes. 

```
"Principal": {
    "AWS": ["arn:aws:iam::<producer-acct-no>:root", "arn:aws:iam::<consumer-acct-no>:root"]
},
```

12.	Create the IAM role that needs to be attached to the EC2 consumer instance. 
```
aws iam create-role --role-name awsblog-dev-app-consumerEc2Role --assume-role-policy-document file://dataFeedMsk/ec2ConsumerPolicy.json --profile <your-user-profile>
```

13.	Deploy the consumer account infrastructure, including the VPC, consumer EC2 instance, security groups and connectivity to the MSK cluster. 

```
cdk deploy --all --app "python app2.py" --profile {your_profile_name}
```

![cross_account_cfn](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/61297eb5-ae09-4b65-a7cc-3662e27b4933)

![vpc_connection](https://github.com/uzairmansoor/dataFeed-MSK-cdk/assets/82077348/80d9b43b-0966-4a80-b473-3e280689b609)

## Run the applications and view the data

Now that we have the infrastructure up, we can produce a raw stock quotes feed from the producer EC2 instance to the MSK cluster, enrich it using the Apache Flink application, and consume the enriched feed from the consumer application through PrivateLink

## Run the Managed Flink application

1.	In your producer account, open the Amazon Managed Service for Apache Flink console and navigate to your application.

2. 	To run the application, choose **Run**, select **Run with latest snapshot**, and choose **Run**.

3.	When the application changes to the **Running** state, choose **Open Apache Flink dashboard**.  You should see your application under Running Jobs.

### Run the Kafka producer application

1.	On the Amazon EC2 console, locate the IP address of the producer EC2 instance named _awsblog-dev-app-kafkaProducerEC2Instance_. 

2.	Connect to the instance using SSH and run the following commands at a time that the US Nasdaq stock market is open:

```
sudo su
cd environment
source alpaca-script/bin/activate
python3 ec2-script-live.py AMZN NVDA
```

### View the enriched data feed in OpenSearch Dashboards

1.	To find the master user name for OpenSearch, open the parameters.py file and locate the value assigned to the _openSearchMasterUsername_ parameter. 

2.	Open Secrets Manager and click on _awsblog-dev-app-openSearchSecrets_ secret to retrieve the password for OpenSearch. 

3.	Navigate to your OpenSearch console and find the URL to your OpenSearch dashboard by clicking on the domain name for your OpenSearch cluster. Click on the URL and sign in using your master user name and password.

4.	In the OpenSearch navigation bar on the left, select **Dashboards Management** under the Management section.

5.	Choose **Index patterns**, then choose **Create index pattern**.

6.	Enter amzn* in the Index pattern name field to match the AMZN ticker, then choose **Next step**.

7.	Select timestamp under the Time field and choose **Create index pattern**. 

8.	Choose **Discover** in the OpenSearch Dashboards navigation pane. 

9.	With **amzn** selected on the index pattern dropdown, select the fields to view the enriched quotes data. The indicator field has been added to the raw data by Amazon Managed Service for Apache Flink to indicate whether the current price direction is neutral, bullish, or bearish.

### Run the Kafka consumer application

To run the consumer application to consume the data feed, you first need to get the multi-VPC brokers URL for the MSK cluster in the producer account. 

1.	On the Amazon MSK console, navigate to your MSK cluster and choose **View client information.** 

2.	Copy the value of the Private endpoint (multi-VPC). 

3.	SSH to your consumer EC2 instance and run the following commands:

```
sudo su
alias kafka-consumer=/kafka_2.13-3.5.1/bin/kafka-console-consumer.sh
kafka-consumer --bootstrap-server {$MULTI_VPC_BROKER_URL} --topic amznenhanced --from-beginning --consumer.config ./customer_sasl.properties

```

You should then see lines of output for the enriched data feed.
 
