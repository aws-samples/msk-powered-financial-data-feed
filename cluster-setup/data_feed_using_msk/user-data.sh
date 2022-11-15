#!/bin/bash -xe
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
yum -y install java-1.8.0
yum -y install git
yum -y install jq
wget https://archive.apache.org/dist/kafka/2.6.2/kafka_2.12-2.6.2.tgz
tar -xzf kafka_2.12-2.6.2.tgz
cp -r kafka_2.12-2.6.2 /home/ec2-user/kafka
chown -R ec2-user.ec2-user /home/ec2-user/kafka

