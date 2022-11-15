# Clients Examples

In this folder you will find some examples of Kafka clients to use.

Before you start:
1. Install requirements.txt
   
    ```
    python3 -m pip install -r requirements.txt
    ```

2. Follow the instructions on setting up TLS for your clients in [this document](../best-practices/SetupTLS.md) 
3. Create an environment variable called **TLSBROKERS** that contains the bootstrap servers DNS names.

    ```
    export TLSBROKERS="x.y.z.kafka.<region-name>.amazonaws.com,x.y.z.kafka.<region-name>.amazonaws.com,x.y.z.kafka.<region-name>.amazonaws.com"
    ```


### Example 1 - Basic mTLS-enabled Kafka producer and consumer for testing

**producer.py** and **consumer.py** are examples of a basic Kafka producer and consumer that use mTLS to authenticate against the MSK cluster. 

1. Make sure you followed the `Before you start` steps

2. Log in using ssh to the provider instance and create a topic called ```topic1```
```
    kfeed --create-topic topic1
    kfeed --list-topics
```
3. Go to the ```data-feed-examples``` folder and run the producer
```
    python3 producer.py
```

4. In a separate terminal window, ssh to the client instance and run the consumer in the ```data-feed-examples``` folder
```
    python3 consumer.py
```

### Example 2 - mTLS-enabled producer and consumer for a live market data feed
**alpaca-producer.py** is an example of a Kafka producer that ingests data from a market data provider called [Alpaca Markets](https://alpaca.markets/) and feeds the data to your MSK Cluster. Alpaca offers a [free tier](https://alpaca.markets/data) API that is a good example of real world data, since it is live market data. There are a few steps that you need to perform to make it work correctly.

1. Make sure you followed the `Before you start` steps

2. Sign up for the Alpaca free tier API.

3. Generate an **API KEY ID** and a **Secret Key**

4. Export them to the following environment variables.

    ```
    export APCA_API_KEY_ID="<API KEY ID>"
    export APCA_API_SECRET_KEY="<Secret Key>"
    ```

5. Log in using ssh to the provider instance and create the following topics. 
```
    kfeed -c trade 
    kfeed -c quote
    kfeed -c crypto_quote
    kfeed -l 
``` 

6. Run the producer in the ```data-feed-examples``` folder. 
```
    python3 alpaca-producer.py
```

7. In a separate terminal window, ssh to the client instance and run the consumer in the ```data-feed-examples``` folder
```
    python3 alpaca-consumer.py
```
