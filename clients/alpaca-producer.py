from alpaca_trade_api.stream import Stream
from kafka import KafkaProducer
import json, os, logging

#Define Logging
log = logging.getLogger(__name__)

#Capture Brokers from environment variables
tlsbrokers = os.environ.get('TLSBROKERS')

#Create Kafka Producer
producer = KafkaProducer(
    bootstrap_servers=tlsbrokers, #Brokers List

    # For mTLS auth:
    security_protocol='SSL',
    ssl_check_hostname=True,
    ssl_certfile='kafkacert/client_cert.pem',
    ssl_keyfile='kafkacert/private_key.pem',
    ssl_cafile='kafkacert/truststore.pem',
    
    value_serializer=lambda v: json.dumps(v).encode('utf-8'), #Serialization Method
    acks=(1) #Number of ACKs to wait on. (0= None, 1=Partition Leader, All= All Brokers with the partion)
)

#Create a handler to catch connection exceptions
def run_connection(stream):
    try:
        stream.run()
    except Exception as e:
        print(f'Exception from websocket connection: {e}')
        logging.info(f'Exception from websocket connection: {e}')
    finally:
        print("Trying to re-establish connection")
        logging.info("Trying to re-establish connection")
        time.sleep(5)
        run_connection(stream)

#Post messages into Kafka Topics
async def post_bars(b):
    #print('trade', b)
    producer.send('trade', value=str(b))
    producer.flush()

async def post_trade(t):
    #print('trade', t)
    producer.send('trade', value=str(t))
    producer.flush()

async def post_quote(q):
    #print('quote', q)
    producer.send('quote', value=str(q))
    producer.flush()

async def post_crypto_trade(t):
    #print('crypto trade', t)
    producer.send('crypto_trade', value=str(t))
    producer.flush()

#Main Function that create Alpaca Stream Subscriptions
def main():
    logging.basicConfig(level=logging.INFO)
    feed = 'iex'  # <- replace to SIP if you have PRO subscription
    stream = Stream( data_feed=feed, raw_data=True)
    stream.subscribe_trades(post_trade, 'QQQ','AMZN','VIX')
    print('Subscribed to trades.')
    stream.subscribe_quotes(post_quote, 'QQQ','AMZN','VIX')
    print('Subscribed to quotes.')
    stream.subscribe_bars(post_bars, 'QQQ','AMZN','VIX')
    print('Subscribed to Bars.')
    stream.subscribe_crypto_trades(post_crypto_trade, 'BTCUSD')
    print('Subscribed to Crypto trades.')

    #Initiate Stream
    stream.run()

    #Initiate new stream if original fails
    run_connection(stream)


if __name__ == "__main__":
    main()
