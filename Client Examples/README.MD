# Clients Examples

In this folder you will find some examples of Kafka clients to use.

Before you start:
1. Install requirements.txt
   
    ```
    python3 -m pip install -r requirements.txt
    ```

2. Follow the instructions on setting up TLS for your clients in [this document](../Best%20Practices/SetupTLS.md) 
3. Create an environment variable called **TLSBROKERS** that contains the bootstrap servers DNS names.

    ```
    export TLSBROKERS="x.y.z.kafka.<region-name>.amazonaws.com,x.y.z.kafka.<region-name>.amazonaws.com,x.y.z.kafka.<region-name>.amazonaws.com"
    ```


### Example 1 - producer.py

**producer.py** is an example of a Kafka producer that uses mTLS to authenticate against the MSK cluster. There are a few steps that you need to perform to make it work correctly.

1. Make sure you followed the `Before you start` steps
2. Change the topic name to suite your needs.

### Example 2 - consumer.py
**consumer.py** is an example of a Kafka consumer that uses mTLS to authenticate against the MSK cluster. There are a few steps that you need to perform to make it work correctly.

1. Make sure you followed the `Before you start` steps
2. Change the topic name to suite your needs.

### Example 3 - alpaca-producer.py
**alpaca-producer.py** is an example of a Kafka producer that is more complete and uses mTLS to authenticate against the MSK cluster. This example ingest data from a market data provider called [Alpaca Markets](https://alpaca.markets/) and post them on your MSK Cluster. Alpaca offers a [free tier](https://alpaca.markets/data) API that is a really good example of real world data, since is live market data.There are a few steps that you need to perform to make it work correctly.

1. Make sure you followed the `Before you start` steps
2. Sign up for Alpaca free tier API.
3. Generate an **API KEY ID** and a **Secret Key**
4. Export them to the following environment variables.

    ```
    export APCA_API_KEY_ID="<API KEY ID>"
    export APCA_API_SECRET_KEY="<Secret Key>"
    ```