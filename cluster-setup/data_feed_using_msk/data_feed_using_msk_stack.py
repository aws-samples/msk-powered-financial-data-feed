import os.path

from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
    aws_msk as msk,
    aws_iam as iam,
    custom_resources as cr,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_targets as target,
    CfnOutput, Fn, Tags
)
from constructs import Construct

#SETUP DEPLOYMENT VARIABLES
dirname = os.path.dirname(__file__)
app_region = os.environ["CDK_DEFAULT_REGION"]
azs = [app_region+"a",app_region+"b"]
azs.append(app_region+"c") # If the region you choose has only 2 AZs please comment this line.

# For security reasons MSK does not allow to create a cluster with public access enabled. 
# To enable public access set the MSK_PUBLIC environment variable to TRUE after the cluster is deployed. And redeploy CDK Stack.
public_connectivity = os.environ["MSK_PUBLIC"].upper()


#Function to enable public Access
def enable_public_access():
    if public_connectivity == "TRUE":
        connectivity_type = "SERVICE_PROVIDED_EIPS"
    else:
        connectivity_type = "DISABLED"

    connectivity_config = msk.CfnCluster.ConnectivityInfoProperty(
        public_access=msk.CfnCluster.PublicAccessProperty(type=connectivity_type)
    )
    return connectivity_config
                

#CDK Application
class DataFeedUsingMskStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # START NETWORK COMPONENTS
        # Create a VPC with public subnets
        vpc_cidr = '10.0.0.0/16'
        vpc = ec2.Vpc(self, 'my-msk-vpc',
            cidr = vpc_cidr,
            nat_gateways = 0,
            availability_zones=azs,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public",cidr_mask=24,subnet_type=ec2.SubnetType.PUBLIC)
            ]
        )

        # Create security group for MSK cluster
        msk_cluster_security_group = ec2.SecurityGroup(self, "msk-cluster-security-group",
            vpc = vpc,
            description="MSK cluster security group",
            security_group_name="msk-cluster-sg",
            allow_all_outbound=True,
        )

        # Add rules to security group
        msk_cluster_security_group.add_ingress_rule(ec2.Peer.ipv4(vpc_cidr), ec2.Port.tcp(9094), "Allow access to private TLS port from within the VPC")
        msk_cluster_security_group.add_ingress_rule(ec2.Peer.ipv4(vpc_cidr), ec2.Port.tcp(2181), "Allow access to Zookeeper port from within the VPC")
        msk_cluster_security_group.add_ingress_rule(ec2.Peer.ipv4(vpc_cidr), ec2.Port.tcp(2182), "Allow access to Zookeeper TLS port from within the VPC")
        msk_cluster_security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(9194), "Allow access to public TLS port from anywhere")


        # START MSK COMPONENTS
        # Create the configuration resource for the cluster
        msk_feed_config = msk.CfnConfiguration(self, "msk-feed-config",
            name="msk-feed-config",
            server_properties="allow.everyone.if.no.acl.found=false",
            description="Financial Data Feeds Configuration"
        )

        # Create the MSK cluster
        number_of_nodes=len(vpc.public_subnets) # Change the number of Brokers here.
        msk_cluster = msk.CfnCluster( self, 'msk-cluster', 
            cluster_name='my-msk-cluster', 
            number_of_broker_nodes=number_of_nodes,
            kafka_version='2.8.1', 
            broker_node_group_info=msk.CfnCluster.BrokerNodeGroupInfoProperty(
                instance_type="kafka.m5.large",
                security_groups = [msk_cluster_security_group.security_group_id],
                client_subnets=[ subnet.subnet_id for subnet in vpc.public_subnets],
                connectivity_info=enable_public_access(),
            ),
            client_authentication = msk.CfnCluster.ClientAuthenticationProperty(
                tls = msk.CfnCluster.TlsProperty(
                    certificate_authority_arn_list=[os.environ["ACM_PCA_ARN"]],
                    enabled=True
                )
            ),
            configuration_info = msk.CfnCluster.ConfigurationInfoProperty(
                arn = msk_feed_config.attr_arn,
                revision = 1
            ),
            enhanced_monitoring="PER_TOPIC_PER_PARTITION",
            open_monitoring=msk.CfnCluster.OpenMonitoringProperty(
                prometheus=msk.CfnCluster.PrometheusProperty(
                    jmx_exporter=msk.CfnCluster.JmxExporterProperty(enabled_in_broker=True),
                    node_exporter=msk.CfnCluster.NodeExporterProperty(enabled_in_broker=True)
                )
            ),
        )


        # START SUPPORTING EC2 COMPONENTS
        # Create an EC2 provider instance in this same VPC to set up the MSK cluster and run the provider app
        # EC2 Instance AMI
        amzn_linux = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
            edition=ec2.AmazonLinuxEdition.STANDARD,
            virtualization=ec2.AmazonLinuxVirt.HVM,
            storage=ec2.AmazonLinuxStorage.GENERAL_PURPOSE
        )

        # EC2 Instance Security group
        provider_instance_security_group = ec2.SecurityGroup(self, "provider-instance-security-group",
            vpc = vpc,
            description="Provider instance security group",
            security_group_name="provider-instance-sg",
            allow_all_outbound=True,
        )
        provider_instance_security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "allow ssh access from anywhere")

        # EC2 Instance BootStrap configuration  
        user_data_path = os.path.join(dirname, "user-data.sh")
        with open(user_data_path, encoding='utf-8') as f:
            user_data = f.read()

        # EC2 Instance definition
        instance = ec2.Instance(self, "msk-provider-instance",
            instance_type = ec2.InstanceType("t3.large"),
            machine_image = amzn_linux,
            security_group = provider_instance_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type = ec2.SubnetType.PUBLIC),
            vpc = vpc,
            key_name = os.environ["EC2_KEY_PAIR"],
            user_data=ec2.UserData.custom(user_data),

        )

        # EC2 Instance IAM Permissions
        instance.add_to_role_policy(
            iam.PolicyStatement(
                actions=["acm-pca:ListCertificateAuthorities", "acm-pca:IssueCertificate", "acm-pca:GetCertificate", "kafka:DescribeClusterV2", "kafka:GetBootstrapBrokers"],
                resources=["*"]
            )
        )

        # EC2 Instance BootStrap configuration
        user_data_path = os.path.join(dirname, "user-data.sh")
        f = open(user_data_path, encoding='utf-8')
        commands = f.read()
        instance.add_user_data(commands)


        # START PRIVATE ENDPOINT COMPONENTS
        # GET MSK Cluster Nodes to deploy NLB
        get_nodes = cr.AwsCustomResource(self, "get_nodes",
            install_latest_aws_sdk=True,
            on_create=cr.AwsSdkCall(
                service="Kafka",
                action="listNodes",
                parameters={"ClusterArn": msk_cluster.attr_arn},
                region=app_region,
                physical_resource_id=cr.PhysicalResourceId.of('NODES'+app_region)
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            )
        )        

        # Get Brokers Details
        broker_ips = []
        broker_names = []
        i=0
        while i < number_of_nodes:
            broker_ips.append(get_nodes.get_response_field('NodeInfoList.'+str(i)+'.BrokerNodeInfo.ClientVpcIpAddress'))
            broker_names.append(get_nodes.get_response_field('NodeInfoList.'+str(i)+'.BrokerNodeInfo.Endpoints.0'))
            i=i+1

        # Setup target group ports for the NLB
        advertised_listeners_starting_port = 8441
        tls_port = 9094

        # Create a private NLB
        nlb = elbv2.NetworkLoadBalancer(self, "private-msk-nlb", 
            load_balancer_name="private-msk-nlb", cross_zone_enabled=True, vpc=vpc)

        # Create Specific Target Groups for Brokers
        port = advertised_listeners_starting_port
        for ip in broker_ips:
            listener = nlb.add_listener("listener-"+str(port), port=port)
            ip_target = target.IpTarget(ip, tls_port)
            listener.add_targets("target", port=port, targets=[ip_target] )
            port += 1

        # Create 9094 Target Group for all Brokers
        listener = nlb.add_listener("listener-"+str(tls_port), port=tls_port) 
        ip_targets = []
        for ip in broker_ips: 
            ip_target = target.IpTarget(ip, tls_port)
            ip_targets.append(ip_target) 
        listener.add_targets("target", port=tls_port, targets=ip_targets)

        # Create a VPC endpoint service for PrivateLink access
        vpce = ec2.VpcEndpointService(self, "msk-vpc-endpoint-service",
            vpc_endpoint_service_load_balancers=[nlb],
            allowed_principals=[iam.ArnPrincipal("*")],
            acceptance_required=False
        )
        Tags.of(vpce).add("Name", "msk-vpc-endpoint-service")
        

        # START LOCAL ENVIRONMENT SETUP
        # GET MSK Cluster TLS Brokers 
        get_tls_brokers = cr.AwsCustomResource(self, "get_tls_brokers", 
            on_create=cr.AwsSdkCall(
                service="Kafka",
                action="getBootstrapBrokers",
                parameters={"ClusterArn": msk_cluster.attr_arn},
                region=app_region,
                physical_resource_id=cr.PhysicalResourceId.of('TLS-BOOTSTRAP_BROKERS-'+app_region)
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            )
        )

        # Describe MSK Cluster 
        describe_cluster = cr.AwsCustomResource(self, "describe-cluster",
            on_create=cr.AwsSdkCall(
                service="Kafka",
                action="describeClusterV2",
                parameters={"ClusterArn": msk_cluster.attr_arn},
                region=app_region,
                physical_resource_id=cr.PhysicalResourceId.of('DESCRIBE-CLUSTER-'+app_region)
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            )
        )

        # Export TLS Brokers into an Environment Variable
        try:
            private_tls_brokers = get_tls_brokers.get_response_field("BootstrapBrokerStringTls")
        except:
            print("No Private TLS Brokers")
        
        if public_connectivity == "TRUE":
            get_pub_tls_brokers = cr.AwsCustomResource(self, "get_pub_tls_brokers", 
                on_create=cr.AwsSdkCall(
                    service="Kafka",
                    action="getBootstrapBrokers",
                    parameters={"ClusterArn": msk_cluster.attr_arn},
                    region=app_region,
                    physical_resource_id=cr.PhysicalResourceId.of('PUBLIC_TLS-BROKERS-'+app_region)
                ),
                policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                    resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
                )
            )
            try:
                public_tls_brokers = get_pub_tls_brokers.get_response_field("BootstrapBrokerStringPublicTls")
                CfnOutput(self, "MskClusterPublicTLSBrokers", export_name="msk-cluster-public-tls-brokers", value=public_tls_brokers)
            except:
                public_tls_brokers = "N/A"
                print("No Public TLS Brokers")

        # Export Zookeeper Nodes into an Environment Variable
        try:
            ZN_nodes = describe_cluster.get_response_field('ClusterInfo.Provisioned.ZookeeperConnectString')
        except:
            print("No Zookeeper Nodes")

        # Print all Outputs
        CfnOutput(self, "MskClusterArn", value=msk_cluster.attr_arn)
        CfnOutput(self, "MskVPCEndpoint", value=vpce.vpc_endpoint_service_name)
        CfnOutput(self, "MskClusterPrivateTLSBrokers", value=private_tls_brokers)
        CfnOutput(self, "MskClusterZookeeper", value=ZN_nodes)
        CfnOutput(self, "MskClusterNumberOfNodes", value=describe_cluster.get_response_field('ClusterInfo.Provisioned.NumberOfBrokerNodes'))
        