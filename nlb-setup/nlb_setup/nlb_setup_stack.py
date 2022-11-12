import os.path
import dns.resolver

from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_targets as target,
    aws_route53_targets as r53_targets,
    aws_route53 as route53,
    Fn
)

from constructs import Construct

class NlbSetupStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

    
        msk_vpc_id = os.environ["MSK_VPC_ID"]


        msk_vpc = ec2.Vpc.from_lookup(self, "msk-vpc", vpc_id=msk_vpc_id)
        print("VPC ID is ", msk_vpc.vpc_id)


        # Get list of MSK brokers in cluster from env variable
        broker_string = os.environ["TLSBROKERS"]

        brokers = broker_string.split(',')
        broker_names = []

        for url in brokers:
            name = url.split(':')[0]
            broker_names.append(name)

        # Get the IP addresses of the brokers by resolving their DNS names
        broker_ips = []
        for name in broker_names:
            result = dns.resolver.query(name, 'A')
            for ipval in result:
                ip = ipval.to_text()
                broker_ips.append(ip)
        

        # Get the list of Zookeeper nodes from the env variable
        zk_node_string = os.environ["ZKNODES"]

        zk_nodes = zk_node_string.split(',')
        zk_node_names = []

        for url in zk_nodes:
            name = url.split(':')[0]
            zk_node_names.append(name)

        # Get the IP addresses of the Zookeeper nodes by resolving their DNS names
        zk_node_ips = []
        for name in zk_node_names:
            result = dns.resolver.query(name, 'A')
            for ipval in result:
                ip = ipval.to_text()
                zk_node_ips.append(ip)
                # print("ZK node: ", name, "IP: ", ip)


        # Create the target groups for the NLBs
        advertised_listeners_starting_port = 8441
        tls_port = 9094

        # Create a private NLB
        nlb = elbv2.NetworkLoadBalancer(self, "private-nlb", 
            load_balancer_name="private-nlb", cross_zone_enabled=True, vpc=msk_vpc)

        # We need an advertised listener for each individual broker, plus a listener for all brokers

        port = advertised_listeners_starting_port
        for ip in broker_ips:
            listener = nlb.add_listener("listener-"+str(port), port=port)
            ip_target = target.IpTarget(ip, tls_port)
            listener.add_targets("target", port=port, targets=[ip_target] )
            port += 1

        listener = nlb.add_listener("listener-"+str(tls_port), port=tls_port) 
        ip_targets = []

        for ip in broker_ips: 
            ip_target = target.IpTarget(ip, tls_port)
            ip_targets.append(ip_target) 

        listener.add_targets("target", port=tls_port, targets=ip_targets)

        # Create a VPC endpoint service for PrivateLink access

        vpce = ec2.VpcEndpointService(self, "vpc-endpoint-service",
            vpc_endpoint_service_load_balancers=[nlb],
            allowed_principals=[iam.ArnPrincipal("*")],
            acceptance_required=False
        )

        # Create a Route 53 Private Hosted Zone

        region = os.getenv('CDK_DEFAULT_REGION')
        zone = route53.PrivateHostedZone(self, "hosted-zone", zone_name="kafka."+region+".amazonaws.com", vpc=msk_vpc)
        
        # Alias the broker names to the NLB name
        for name in broker_names:
            kafka_index = name.find("kafka")
            route53.ARecord(self, "ARecord"+name[0:3],
                    record_name=name[0:kafka_index-1],
                    zone=zone,
                    target=route53.RecordTarget.from_alias(r53_targets.LoadBalancerTarget(nlb))
            )

        # Add the Zookeeper node A records 
        for name, ip in zip(zk_node_names, zk_node_ips):
            kafka_index = name.find("kafka")
            route53.ARecord(self, "ARecord"+name[0:3],
                    record_name=name[0:kafka_index-1],
                    zone=zone,
                    target=route53.RecordTarget.from_values(ip)
            )
