import os.path
import dns.resolver

from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_targets as target
)

from constructs import Construct

class NlbSetupStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

    
        vpc = ec2.Vpc.from_lookup(self, "msk-vpc", vpc_name="DataFeedUsingMskStack/my-msk-vpc")


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
                # print("Broker: ", name, "IP: ", ip)
        

        # Create the target groups for the NLBs
        advertised_listeners_starting_port = 8441
        tls_port = 9094


        # Create a public (Internet-facing) NLB
        nlb = elbv2.NetworkLoadBalancer(self, "public-nlb", load_balancer_name="public-nlb", vpc=vpc, internet_facing=True)

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

