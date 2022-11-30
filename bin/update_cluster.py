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
config_result = []
while i <= number_of_nodes:
    command = "~/kafka/bin/zookeeper-shell.sh $ZKNODES get /brokers/ids/"+str(i)+" | grep features"
    command_result = subprocess.run(command, capture_output=True, shell=True)
    out = command_result.stdout
    output=json.loads(out.decode('utf-8'))
    config_result.append(output)

    endpoints = output.get("endpoints")
    host = output.get("host")
    host = str(host).replace("-internal","")
    protocol_map = output.get("listener_security_protocol_map")
    endpoints.append("CLIENT_SECURE_VPCE://"+str(host).replace("b-"+str(i)+".","b-"+str(i)+"-tls.")+":"+str(init_port))
    endpoints_str = str(endpoints).replace(" ","").replace("'","")
    protocol_map["CLIENT_SECURE_VPCE"] = "SSL"
    protocol_map_str = str(protocol_map).replace(" ","").replace("'","").replace("{","[").replace("}","]")

    update_listener_part1 = "~/kafka/bin/kafka-configs.sh --bootstrap-server "+str(host)+":9094  --entity-type brokers --entity-name "+str(i)
    update_listener_part2 = " --alter --command-config " + properties_file + " --add-config advertised.listeners="+endpoints_str

    update_map_part1 = "~/kafka/bin/kafka-configs.sh --bootstrap-server "+str(host)+":9094  --entity-type brokers --entity-name "+str(i)
    update_map_part2 = " --alter --command-config " + properties_file + " --add-config listener.security.protocol.map="+protocol_map_str

    listener_part1 = "~/kafka/bin/kafka-configs.sh --bootstrap-server "+str(host)+":9094  --entity-type brokers --entity-name "+str(i)
    listener_part2 = " --alter --command-config " + properties_file + " --add-config listeners="+endpoints_str

    print(update_map_part1+update_map_part2)
    print(listener_part1+listener_part2)
    print(update_listener_part1+update_listener_part2)


    os.system(update_map_part1+update_map_part2)
    os.system(listener_part1+listener_part2)
    os.system(update_listener_part1+update_listener_part2)

    init_port = init_port+1
    i=i+1

#print(json.dumps(config_result, indent=3, default=str))

