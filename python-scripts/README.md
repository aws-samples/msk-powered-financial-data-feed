**Pre-requisites**
- Place python-scripts folder in a s3 bucket

**Steps to set up Python on Ec2**

- sudo su
- sudo yum update 
- sudo yum install python3 -y
- sudo yum install python3-pip -y
- sudo mkdir environment
- cd environment
- sudo yum install python3 virtualenv -y
- sudo python3 -m virtualenv alpaca-script
- source alpaca-script/bin/activate
- pip install -r <(aws s3 cp s3://{YOUR-S3-BUCKET-NAME}/python-scripts/requirement.txt -)
- aws s3 cp s3://{YOUR-S3-BUCKET-NAME}/python-scripts/ec2-script-live.py .

**Running script on Ec2**

1- Run the following command python3 ec2-live-script.py <arg1> <arg2>......<arg n>
    example: python3 ec2-live-script.py AAPL GOOGL

