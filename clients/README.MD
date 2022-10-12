# Clients Examples

In this folder you will find some examples of Kafka clients to use.

Before you start install requirements.txt

`python3 -m pip install -r requirements.txt`

### Example 1 - producer.py

producer.py is an example of a Kafka producer that uses mTLS to authenticate against the MSK cluster. There are a few steps that you need to perform to make it work correctly.

1. Create the certificate in a Java Trust Store (.jks) file.
2. Create an environment variable called **TLSBROKERS** that contains the bootstrap servers DNS names.
3. Change the topic name to suite your needs.

### Example 2 - consumer.py
consumer.py is an example of a Kafka consumer that uses mTLS to authenticate against the MSK cluster. There are a few steps that you need to perform to make it work correctly.

1. Create the certificate in a Java Trust Store (.jks) file.
2. Create an environment variable called **TLSBROKERS** that contains the bootstrap servers DNS names.
3. Change the topic name to suite your needs.

### Example 3 - alpaca-producer.py

