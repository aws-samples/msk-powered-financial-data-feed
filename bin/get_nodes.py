import boto3
import json, os

client = boto3.client('kafka')

response = client.describe_cluster_v2(
    ClusterArn=os.environ["CLUSTERARN"]
)

response1 = client.get_bootstrap_brokers(
    ClusterArn=os.environ["CLUSTERARN"]
)

f = open(os.path.expanduser('~')+"/.bashrc", "a")

f.write("export ZKNODES="+json.dumps(response.get("ClusterInfo").get("Provisioned").get("ZookeeperConnectString"), indent=2, default=str)+"\n")
f.write("export TLS_ZKNODES="+json.dumps(response.get("ClusterInfo").get("Provisioned").get("ZookeeperConnectStringTls"), indent=2, default=str)+"\n")
f.write("export TLSBROKERS="+json.dumps(response1.get("BootstrapBrokerStringTls"), indent=2, default=str)+"\n")
f.write("export PUBLIC_TLSBROKERS="+json.dumps(response1.get("BootstrapBrokerStringPublicTls"), indent=2, default=str)+"\n")
f.close()

print("Bootstrap Nodes added to ~/.bashrc file. Please add them to your Environment variables.\n\n")
print("source ~/.bashrc")
