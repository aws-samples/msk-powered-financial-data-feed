import os.path
import sys

# Update the advertised listeners ports on the MSK cluster

kafka_home = os.environ["HOME"] + "/kafka/"
properties_file = kafka_home + "client.properties"

if not os.path.exists(properties_file):
    sys.exit(properties_file + " does not exist.")


# Get list of MSK brokers in cluster from env variable
broker_string = os.environ["TLSBROKERS"]

brokers = broker_string.split(',')
broker_names = []

for url in brokers:
    name = url.split(':')[0]
    broker_names.append(name)

advertised_listeners_starting_port = 8441

command_part1 = os.environ["HOME"] + "/kafka/bin/kafka-configs.sh --bootstrap-server "
command_part2 = " --entity-type brokers --entity-name "
command_part3 = " --alter --command-config " + properties_file + " --add-config advertised.listeners=[CLIENT_SECURE://"

entity_name = 1
port = advertised_listeners_starting_port

for name in broker_names:
    internal_name = name[0:3] + "-internal" + name[3:]
    public_name = name[0:3] + "-public" + name[3:]
    command = command_part1 + name + ":9094" + command_part2 + str(entity_name)
    command += command_part3 + name + ":" + str(port)  + ","
    command += "CLIENT_SECURE_PUBLIC://" + public_name + ":9194,"
    command += "REPLICATION://" + internal_name + ":9093,"
    command += "REPLICATION_SECURE://" + internal_name + ":9095]"
    print(command)
    os.system(command)

    entity_name += 1
    port += 1

