#!/bin/bash -xe
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1
sudo su
yum update -y
yum groupinstall "Development Tools" -y
yum -y install openssl-devel bzip2-devel  
yum -y install openssl-devel bzip2-devel zlib-devel libffi-devel ncurses-devel sqlite-devel readline-devel tk-devel gdbm-devel db4-devel libpcap-devel xz-devel
yum -y install java-1.8.0 git jq wget python3-pip

mkdir /home/ec2-user/certs
chown -R ec2-user.ec2-user /home/ec2-user/certs


wget https://archive.apache.org/dist/kafka/2.6.2/kafka_2.12-2.6.2.tgz
tar -xzf kafka_2.12-2.6.2.tgz
cp -r kafka_2.12-2.6.2 /home/ec2-user/kafka
chown -R ec2-user.ec2-user /home/ec2-user/kafka

cd /home/ec2-user
su ec2-user -c "git clone https://github.com/aws-samples/msk-powered-financial-data-feed.git /home/ec2-user/msk-feed"
python3 -m pip install -r /home/ec2-user/msk-feed/requirements.txt
