import boto3
import json, os

client = boto3.client('kafka')

list_response = client.list_nodes(
    ClusterArn=os.environ["CLUSTERARN"]
)
bootstrap_response = client.get_bootstrap_brokers(
    ClusterArn=os.environ["CLUSTERARN"]
)

## Create file with all variables needed by client 
broker_names = []
for broker in list_response.get("NodeInfoList"):
    broker_names.append(broker.get("BrokerNodeInfo").get("Endpoints")[0])

## Write Results to File
f = open(os.path.expanduser('~')+"/.client_export", "w")
f.write("export TLSBROKERS="+str(bootstrap_response.get("BootstrapBrokerStringTls"))+"\n")
f.write("export PUBLIC_TLSBROKERS="+str(bootstrap_response.get("BootstrapBrokerStringPublicTls"))+"\n")
f.write("export BROKERLIST='"+json.dumps(broker_names)+"'\n")
f.write("export MSK_VPC_ENDPOINT_SERVICE="+str(os.environ["MSK_VPC_ENDPOINT_SERVICE"])+"\n")
f.close()

## OUTPUT
print("\nFile '"+str(os.path.expanduser('~'))+"/.client_export' was created.")
print("Please share this file with your customer and ask them to add as Environment variables, before deploying client app.\n\n")

# file = open(os.path.expanduser('~')+"/.client_export", "r")
# for line in file:
#     print(line.strip())