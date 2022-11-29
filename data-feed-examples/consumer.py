from kafka import KafkaConsumer
import json,os

#Import Bootstrap server from environment variable
tlsbrokers = os.environ.get('TLSBROKERS')
    
#Create Consumer
consumer = KafkaConsumer(
    'topic1', #topic to consume
    group_id='consumer_python', #local consumer name
    bootstrap_servers=tlsbrokers, #Brokers List
    api_version=(0,11,5),
    # For mTLS auth:
    security_protocol='SSL',
    ssl_check_hostname=True,
    ssl_certfile='client_cert.pem',
    ssl_keyfile='private_key.pem',
    ssl_cafile='truststore.pem',
)

# Loop to consume messages and Print details.
for message in consumer:
    print ("%s:%d:%d: value=%s" % (message.topic, message.partition,message.offset,message.value))
    try: 
        print(json.loads(message.value))
    except:
        print(message.value.decode('utf-8'))
