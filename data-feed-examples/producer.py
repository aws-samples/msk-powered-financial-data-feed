from kafka import KafkaProducer
import json, os, sys

#Import Bootstrap server from environment variable
tlsbrokers = os.environ.get('TLSBROKERS')

#Create Producer
producer = KafkaProducer(
    bootstrap_servers=tlsbrokers, #Brokers List
    api_version=(0,11,5),
    # For mTLS auth:
    security_protocol='SSL',
    ssl_check_hostname=True,
    ssl_certfile='client_cert.pem',
    ssl_keyfile='private_key.pem',
    ssl_cafile='truststore.pem',
    
    value_serializer=lambda v: json.dumps(v).encode('utf-8'), #Serialization Method
    acks=(1) #Number of ACKs to wait on. (0= None, 1=Partition Leader, All= All Brokers with the partion)
)

# Read lines of input from the terminal, and send them as messages 

print("Enter a message to send at the prompt. Type 'q' to quit"),
sys.stdout.write("> ")
sys.stdout.flush()

for line in sys.stdin:
    if line.rstrip() == 'q':
        break

    msg = {"Sending": line.rstrip()}

    # Send message to Kafka Brokers
    producer.send('topic1', value=msg)
    producer.flush()
    sys.stdout.write("> ")
    sys.stdout.flush()


