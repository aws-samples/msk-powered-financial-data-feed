from kafka import KafkaProducer
import json, os

#Import Bootstrap server from environment variable
tlsbrokers = os.environ.get('TLSBROKERS')

#Create Producer
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

#Message to send
msg = {"hello":"world"}

#Send message to Kafka Brokers
producer.send('topic1', value=msg)
producer.flush()