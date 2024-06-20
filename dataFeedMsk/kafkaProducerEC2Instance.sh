sudo su
sudo yum update -y
sudo yum -y install java-11
sudo yum install jq -y
wget https://archive.apache.org/dist/kafka/3.5.1/kafka_2.13-3.5.1.tgz
tar -xzf kafka_2.13-3.5.1.tgz
cd kafka_2.13-3.5.1/libs
wget https://github.com/aws/aws-msk-iam-auth/releases/download/v1.1.1/aws-msk-iam-auth-1.1.1-all.jar
cd /home/ec2-user
cat <<EOF > /home/ec2-user/users_jaas.conf
KafkaClient {
    org.apache.kafka.common.security.scram.ScramLoginModule required
    username="${MSK_PRODUCER_USERNAME}"
    password="${MSK_PRODUCER_PASSWORD}";
};
EOF
echo 'export KAFKA_OPTS=-Djava.security.auth.login.config=/home/ec2-user/users_jaas.conf' >> ~/.bashrc
BOOTSTRAP_SERVERS=$(aws kafka get-bootstrap-brokers --cluster-arn ${MSK_CLUSTER_ARN} --region ${AWS_REGION} | jq -r '.BootstrapBrokerStringSaslScram')
export BOOTSTRAP_SERVERS
echo "export BOOTSTRAP_SERVERS=${BOOTSTRAP_SERVERS}" >> ~/.bashrc
sleep 5
source ~/.bashrc
aws ssm put-parameter --name "${MSK_CLUSTER_BROKER_URL_PARAM_NAME}" --value "$BOOTSTRAP_SERVERS" --type "String" --overwrite --region "${AWS_REGION}"
ZOOKEEPER_CONNECTION=$(aws kafka describe-cluster --cluster-arn ${MSK_CLUSTER_ARN} --region ${AWS_REGION} | jq -r '.ClusterInfo.ZookeeperConnectString')
export ZOOKEEPER_CONNECTION
echo "export ZOOKEEPER_CONNECTION=${ZOOKEEPER_CONNECTION}" >> ~/.bashrc
mkdir tmp
cp /usr/lib/jvm/java-11-amazon-corretto.x86_64/lib/security/cacerts /home/ec2-user/tmp/kafka.client.truststore.jks
cat <<EOF > /home/ec2-user/client_sasl.properties
security.protocol=SASL_SSL
sasl.mechanism=SCRAM-SHA-512
ssl.truststore.location=/home/ec2-user/tmp/kafka.client.truststore.jks
EOF
AZ_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=${VPC_ID}" --region ${AWS_REGION} | jq -r '.Subnets[].AvailabilityZoneId' | sort -u | tr "\n" ",")
export AZ_IDS
echo "export AZ_IDS=${AZ_IDS}" >> ~/.bashrc
sleep 5
source ~/.bashrc
aws ssm put-parameter --name "${AZ_IDS_PARAM_NAME}" --value "$AZ_IDS" --type "${AZ_IDS_PARAM_TYPE}" --overwrite --region "${AWS_REGION}"
/kafka_2.13-3.5.1/bin/kafka-acls.sh --authorizer-properties zookeeper.connect=$ZOOKEEPER_CONNECTION --add --allow-principal User:${MSK_PRODUCER_USERNAME} --operation Read --topic '*'
/kafka_2.13-3.5.1/bin/kafka-acls.sh --authorizer-properties zookeeper.connect=$ZOOKEEPER_CONNECTION --add --allow-principal User:${MSK_PRODUCER_USERNAME} --operation Write --topic '*'
/kafka_2.13-3.5.1/bin/kafka-acls.sh --authorizer-properties zookeeper.connect=$ZOOKEEPER_CONNECTION --add --allow-principal User:${MSK_PRODUCER_USERNAME} --operation Read --group '*'
/kafka_2.13-3.5.1/bin/kafka-topics.sh --bootstrap-server $BOOTSTRAP_SERVERS --command-config /home/ec2-user/client_sasl.properties --create --topic ${MSK_TOPIC_NAME_1} --replication-factor 2
/kafka_2.13-3.5.1/bin/kafka-topics.sh --bootstrap-server $BOOTSTRAP_SERVERS --command-config /home/ec2-user/client_sasl.properties --create --topic ${MSK_TOPIC_NAME_2} --replication-factor 2
/kafka_2.13-3.5.1/bin/kafka-topics.sh --bootstrap-server $BOOTSTRAP_SERVERS --command-config /home/ec2-user/client_sasl.properties --create --topic ${MSK_TOPIC_NAME_3} --replication-factor 2
/kafka_2.13-3.5.1/bin/kafka-topics.sh --bootstrap-server $BOOTSTRAP_SERVERS --command-config /home/ec2-user/client_sasl.properties --create --topic ${MSK_TOPIC_NAME_4} --replication-factor 2
/kafka_2.13-3.5.1/bin/kafka-topics.sh --bootstrap-server $BOOTSTRAP_SERVERS --list --command-config ./client_sasl.properties
/kafka_2.13-3.5.1/bin/kafka-acls.sh --authorizer-properties zookeeper.connect=$ZOOKEEPER_CONNECTION --add --allow-principal User:${MSK_CONSUMER_USERNAME} --operation Read --topic=${MSK_TOPIC_NAME_3}
/kafka_2.13-3.5.1/bin/kafka-acls.sh --authorizer-properties zookeeper.connect=$ZOOKEEPER_CONNECTION --add --allow-principal User:${MSK_CONSUMER_USERNAME} --operation Read --topic=${MSK_TOPIC_NAME_4}
/kafka_2.13-3.5.1/bin/kafka-acls.sh --authorizer-properties zookeeper.connect=$ZOOKEEPER_CONNECTION --add --allow-principal User:${MSK_CONSUMER_USERNAME} --operation Read --group '*'
cd /home/ec2-user
sudo yum update -y
sudo yum install python3 -y
sudo yum install python3-pip -y
sudo mkdir environment
cd environment
sudo yum install python3 virtualenv -y
sudo pip3 install virtualenv
sudo python3 -m virtualenv alpaca-script
source alpaca-script/bin/activate
pip install -r <(aws s3 cp s3://${BUCKET_NAME}/dataFeedMskArtifacts/python-scripts/requirement.txt -)
aws s3 cp s3://${BUCKET_NAME}/dataFeedMskArtifacts/python-scripts/ec2-script-live.py .
export ALPACA_API_KEY=${ALPACA_API_KEY}
export ALPACA_SECRET_KEY=${ALPACA_SECRET_KEY}
echo "export ALPACA_API_KEY=${ALPACA_API_KEY}" >> ~/.bashrc
echo "export ALPACA_SECRET_KEY=${ALPACA_SECRET_KEY}" >> ~/.bashrc
echo 'export KAFKA_SASL_MECHANISM=SCRAM-SHA-512' >> ~/.bashrc
export KAFKA_SASL_USERNAME=${MSK_PRODUCER_USERNAME}
echo "export KAFKA_SASL_USERNAME=${KAFKA_SASL_USERNAME}" >> ~/.bashrc
export KAFKA_SASL_PASSWORD=${MSK_PRODUCER_PASSWORD}
echo "export KAFKA_SASL_PASSWORD=${KAFKA_SASL_PASSWORD}" >> ~/.bashrc

