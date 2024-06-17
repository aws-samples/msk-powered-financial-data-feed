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
    username="${MSK_CONSUMER_USERNAME}"
    password="${MSK_CONSUMER_PASSWORD}";
};
EOF
echo 'export KAFKA_OPTS=-Djava.security.auth.login.config=/home/ec2-user/users_jaas.conf' >> ~/.bashrc
mkdir tmp
cp /usr/lib/jvm/java-11-amazon-corretto.x86_64/lib/security/cacerts /home/ec2-user/tmp/kafka.client.truststore.jks
cat <<EOF > /home/ec2-user/customer_sasl.properties
security.protocol=SASL_SSL
sasl.mechanism=SCRAM-SHA-512
ssl.truststore.location=/home/ec2-user/tmp/kafka.client.truststore.jks
EOF