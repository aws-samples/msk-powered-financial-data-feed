import sys
import asyncio
import json, os, logging, time
from kafka import KafkaProducer
from alpaca.data.live import StockDataStream

# Define Logging
log = logging.getLogger(__name__)

#Environment variables 
API_KEY = os.environ.get('ALPACA_API_KEY')
SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY')
BOOTSTRAP_SERVERS = os.environ.get('BOOTSTRAP_SERVERS')
KAFKA_SASL_MECHANISM = os.environ.get('KAFKA_SASL_MECHANISM')
KAFKA_SASL_USERNAME = os.environ.get('KAFKA_SASL_USERNAME')
KAFKA_SASL_PASSWORD = os.environ.get('KAFKA_SASL_PASSWORD')

#Configure Kafka producer
producer = KafkaProducer(
    api_version=(2, 8, 1),
    bootstrap_servers=BOOTSTRAP_SERVERS,
    security_protocol="SASL_SSL", 
    sasl_mechanism=KAFKA_SASL_MECHANISM,
    sasl_plain_username=KAFKA_SASL_USERNAME,
    sasl_plain_password=KAFKA_SASL_PASSWORD,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Convert data to desired format and post messages into Kafka Topics
async def post_bars(bar):
    symbol = bar.symbol
    timestamp = bar.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    open_price = bar.open
    high_price = bar.high
    low_price = bar.low
    close_price = bar.close
    volume = bar.volume
    trade_count = bar.trade_count
    vwap = bar.vwap

    modified_bar = {
        'open': open_price,
        'high': high_price,
        'low': low_price,
        'close': close_price,
        'volume': volume,
        'trade_count': trade_count,
        'vwap': vwap,
        'timestamp': timestamp,
        'symbol': symbol
    }

    # print(symbol.lower(),value=modified_bar)
    producer.send(symbol.lower(), value=modified_bar)
    producer.flush()

# Main Function that create Alpaca Stream Subscriptions
def main(symbols):
    logging.basicConfig(level=logging.INFO)

    wss_client = StockDataStream(API_KEY, SECRET_KEY)
    wss_client.subscribe_bars(post_bars, *symbols)
    print('Subscribed to Bars.')

    # Initiate Stream
    wss_client.run()

if __name__ == "__main__":
    if len(sys.argv) < 1:
        print("Enter topic name!")
        sys.exit(1)
    symbols = sys.argv[1:]
    asyncio.run(main(symbols))