# Clients Examples

In this folder you will find some examples of Kafka clients to use.

Before you start:
1. Install requirements.txt
   
    `python3 -m pip install -r requirements.txt`

2. Create the private key file named `private_key.pem`.
3. Create the certificate file named `client_cert.pem`.
4. Create the public trust store with Amazon Public CA certificate file named `truststore.pem`. 
5. Create an environment variable called **TLSBROKERS** that contains the bootstrap servers DNS names.

### Example 1 - producer.py

**producer.py** is an example of a Kafka producer that uses mTLS to authenticate against the MSK cluster. There are a few steps that you need to perform to make it work correctly.

1. Make sure you followed the `Before you start` steps
2. Change the topic name to suite your needs.

### Example 2 - consumer.py
**consumer.py** is an example of a Kafka consumer that uses mTLS to authenticate against the MSK cluster. There are a few steps that you need to perform to make it work correctly.

1. Make sure you followed the `Before you start` steps
2. Change the topic name to suite your needs.

### Example 3 - alpaca-producer.py

