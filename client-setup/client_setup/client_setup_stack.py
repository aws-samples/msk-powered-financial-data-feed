import os.path, json, boto3
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_route53_targets as r53_targets,
    aws_route53 as route53,
)
from constructs import Construct

#SETUP DEPLOYMENT VARIABLES
dirname = os.path.dirname(__file__)
app_region = os.environ["CDK_DEFAULT_REGION"]

## Function to Write file for client
def create_client_export_file(TLSBROKERS, PUBLIC_TLSBROKERS):
    f = open(os.path.expanduser('~')+"/.client_export", "w")
    f.write("export TLSBROKERS="+TLSBROKERS+"\n")
    f.write("export PUBLIC_TLSBROKERS="+PUBLIC_TLSBROKERS+"\n")
    f.close()

    ## OUTPUT
    print("\nFile '"+str(os.path.expanduser('~'))+"/.client_export' was created.")
    print("Please share this file with your customer and ask them to add as Environment variables, before deploying client app.\n\n")

## Function to variable
def get_variables(CLUSTERARN):
    client = boto3.client('kafka')

    list_response = client.list_nodes(
        ClusterArn=CLUSTERARN
    )
    bootstrap_response = client.get_bootstrap_brokers(
        ClusterArn=CLUSTERARN
    )

    ## Create file with all variables needed by client 
    broker_names = []
    for broker in list_response.get("NodeInfoList"):
        broker_names.append(broker.get("BrokerNodeInfo").get("Endpoints")[0])

    TLSBROKERS = str(bootstrap_response.get("BootstrapBrokerStringTls"))
    PUBLIC_TLSBROKERS = str(bootstrap_response.get("BootstrapBrokerStringPublicTls"))
    BROKERLIST = json.dumps(broker_names)

    create_client_export_file(TLSBROKERS, PUBLIC_TLSBROKERS)

    return (TLSBROKERS, PUBLIC_TLSBROKERS, BROKERLIST)


class ClientSetupStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get list of MSK brokers in cluster from env variable
        CLUSTERARN = os.environ["CLUSTERARN"]
        TLSBROKERS, PUBLIC_TLSBROKERS, BROKERLIST = get_variables(CLUSTERARN)
        broker_list=[]
        broker_list=json.loads(BROKERLIST)

        # Create a client VPC with public subnets for the Kafka consumer
        vpc_cidr = '10.1.0.0/16'
        vpc = ec2.Vpc(self, 'msk-client-vpc',
            cidr = vpc_cidr,
            nat_gateways = 0,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public",cidr_mask=24,subnet_type=ec2.SubnetType.PUBLIC)
            ]
        )

        # Create a VPC endpoint for the MSK cluster endpoint service
        # Security group for the VPC endpoint
        vpc_endpoint_security_group = ec2.SecurityGroup(self, "msk-vpc-endpoint-security-group",
            vpc = vpc,
            description="MSK VPC endpoint security group",
            security_group_name="msk-vpc-endpoint-sg",
            allow_all_outbound=True,
        )
        vpc_endpoint_security_group.add_ingress_rule(ec2.Peer.ipv4(vpc_cidr), ec2.Port.tcp(9094), "All brokers")
        i=0
        while i < len(broker_list):
            #print(i)
            vpc_endpoint_security_group.add_ingress_rule(ec2.Peer.ipv4(vpc_cidr), ec2.Port.tcp(int(i+8441)), "Broker "+str(i+1))
            i=i+1
       
        # Deploy Interface VPC Endpoint
        vpc_endpoint_service = os.environ["MSK_VPC_ENDPOINT_SERVICE"]
        msk_vpc_endpoint = ec2.InterfaceVpcEndpoint(self, "msk-vpc-endpoint",
            vpc=vpc,
            service=ec2.InterfaceVpcEndpointService(vpc_endpoint_service, 9094),
            security_groups = [vpc_endpoint_security_group],
            lookup_supported_azs=True
        )

        # Create a Route 53 Private Hosted Zone
        # Alias the broker names to the NLB name
        i=1
        for broker in broker_list:
            zone = route53.PrivateHostedZone(self, "hosted-zone-"+str(i), zone_name=broker, vpc=vpc)
            route53.ARecord(self, "ARecord_"+str(broker),
                    zone=zone,
                    target=route53.RecordTarget.from_alias(r53_targets.InterfaceVpcEndpointTarget(msk_vpc_endpoint))
            )
            i=i+1

        # Create an EC2 instance in this  VPC to run the Kafka feed consumer app
        # AMI
        amzn_linux = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
            edition=ec2.AmazonLinuxEdition.STANDARD,
            virtualization=ec2.AmazonLinuxVirt.HVM,
            storage=ec2.AmazonLinuxStorage.GENERAL_PURPOSE
        )

        # Security group
        client_instance_security_group = ec2.SecurityGroup(self, "kafka-client-security-group",
            vpc = vpc,
            description="Kafka client instance security group",
            security_group_name="kafka-client-instance-sg",
            allow_all_outbound=True,
        )
        client_instance_security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "allow ssh access from anywhere")

        # EC2 Instance BootStrap configuration  
        user_data_path = os.path.join(dirname, "user-data.sh")
        with open(user_data_path, encoding='utf-8') as f:
            user_data = f.read()

        user_data = user_data+"echo \"export TLSBROKERS='"+str(TLSBROKERS)+"'\" >> /home/ec2-user/.bashrc \n"
        user_data = user_data+"echo \"export PUBLIC_TLSBROKERS='"+str(PUBLIC_TLSBROKERS)+"'\" >> /home/ec2-user/.bashrc \n"

        # EC2 Instance definition
        instance = ec2.Instance(self, "msk-consumer-instance",
            instance_type = ec2.InstanceType("t3.small"),
            machine_image = amzn_linux,
            security_group = client_instance_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type = ec2.SubnetType.PUBLIC),
            vpc = vpc,
            key_name = os.environ["EC2_KEY_PAIR"],
            user_data=ec2.UserData.custom(user_data),

        )

