import os.path
import subprocess
import sys,boto3,json

# Update the advertised listeners ports on the MSK cluster

kafka_home = os.environ["HOME"] + "/kafka/"
properties_file = kafka_home + "client.properties"

if not os.path.exists(properties_file):
    sys.exit(properties_file + " does not exist.")

client = boto3.client('kafka')
response = client.describe_cluster_v2(
    ClusterArn=os.environ["CLUSTERARN"]
)

number_of_nodes = int(response.get("ClusterInfo").get("Provisioned").get("NumberOfBrokerNodes"))

i=1
init_port = 8441
while i <= number_of_nodes:
    command = "~/kafka/bin/zookeeper-shell.sh $ZKNODES get /brokers/ids/"+str(i)+" | grep features"
    command_result = subprocess.run(command, capture_output=True, shell=True)
    out = command_result.stdout

    print("###")
    output=json.loads(out.decode('utf-8'))

    print(json.dumps(output, indent=2, default=str))

    endpoints = output.get("endpoints")
    host = output.get("host")
    protocol_map = output.get("listener_security_protocol_map")
    endpoints.append("CLIENT_SECURE_VPCE://"+str(host)+":"+str(init_port))
    protocol_map["CLIENT_SECURE_VPCE"] = "SSL"

    update_listener_part1 = "~/kafka/bin/kafka-configs.sh --bootstrap-server "+str(host)+":9094  --entity-type brokers --entity-name "+str(i)
    update_listener_part2 = " --alter --command-config " + properties_file + " --add-config advertised.listeners=\""+str(endpoints)+"\""

    update_map_part1 = "~/kafka/bin/kafka-configs.sh --bootstrap-server "+str(host)+":9094  --entity-type brokers --entity-name "+str(i)
    update_map_part2 = " --alter --command-config " + properties_file + " --add-config listener.security.protocol.map=\""+str(protocol_map)+"\""


    print(update_listener_part1+update_listener_part2)
    print("###############")
    print(update_map_part1+update_map_part2)
    print("\n\n\n")



    init_port = init_port+1
    i=i+1

