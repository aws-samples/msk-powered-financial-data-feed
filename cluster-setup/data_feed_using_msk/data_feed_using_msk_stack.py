import os.path

from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
    aws_msk as msk,
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct

dirname = os.path.dirname(__file__)

class DataFeedUsingMskStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create a VPC with public subnets
        vpc_cidr = '10.0.0.0/16'
        vpc = ec2.Vpc(self, 'my-msk-vpc',
            cidr = vpc_cidr,
            nat_gateways = 0,
            #availability_zones=[os.environ["CDK_DEFAULT_REGION"]+"a",os.environ["CDK_DEFAULT_REGION"]+"b",os.environ["CDK_DEFAULT_REGION"]+"c"]
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
        msk_cluster_security_group.add_ingress_rule(ec2.Peer.ipv4(vpc_cidr), ec2.Port.tcp(9094), "Allow access to private TLS port from within the VPC")
        msk_cluster_security_group.add_ingress_rule(ec2.Peer.ipv4(vpc_cidr), ec2.Port.tcp(2181), "Allow access to Zookeeper port from within the VPC")
        msk_cluster_security_group.add_ingress_rule(ec2.Peer.ipv4(vpc_cidr), ec2.Port.tcp(2182), "Allow access to Zookeeper TLS port from within the VPC")
        msk_cluster_security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(9194), "Allow access to public TLS port from anywhere")

        # Create the configuration resource for the cluster
        msk_feed_config = msk.CfnConfiguration(self, "msk-feed-config",
            name="msk-feed-config",
            server_properties="allow.everyone.if.no.acl.found=false",
            description="Financial Data Feeds Configuration"
        )


        # Create the MSK cluster
        msk_cluster = msk.CfnCluster( self, 'msk-cluster', 
            cluster_name='my-msk-cluster', 
            number_of_broker_nodes=len(vpc.public_subnets),
            kafka_version='2.8.1', 
            broker_node_group_info=msk.CfnCluster.BrokerNodeGroupInfoProperty(
                instance_type="kafka.m5.large",
                security_groups = [msk_cluster_security_group.security_group_id],
                client_subnets=[ subnet.subnet_id for subnet in vpc.public_subnets],
                #
                # After deploying this CDK stack for the first time, uncomment the 3 lines 
                # of code below and re-deploy to allow public access to the cluster. 
                # For security reasons, MSK does not allow public access to be enabled on the 
                # initial deployment.
                #
                # connectivity_info=msk.CfnCluster.ConnectivityInfoProperty(
                #   public_access=msk.CfnCluster.PublicAccessProperty(type="SERVICE_PROVIDED_EIPS")
                # ),
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
        )

        # Create an EC2 provider instance in this same VPC to set up the MSK cluster and run the provider app
        # AMI
        amzn_linux = ec2.MachineImage.latest_amazon_linux(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
            edition=ec2.AmazonLinuxEdition.STANDARD,
            virtualization=ec2.AmazonLinuxVirt.HVM,
            storage=ec2.AmazonLinuxStorage.GENERAL_PURPOSE
        )

        # Security group
        provider_instance_security_group = ec2.SecurityGroup(self, "provider-instance-security-group",
            vpc = vpc,
            description="Provider instance security group",
            security_group_name="provider-instance-sg",
            allow_all_outbound=True,
        )
        provider_instance_security_group.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "allow ssh access from anywhere")

        # Instance
        instance = ec2.Instance(self, "msk-provider-instance",
            instance_type = ec2.InstanceType("t3.large"),
            machine_image = amzn_linux,
            security_group = provider_instance_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type = ec2.SubnetType.PUBLIC),
            vpc = vpc,
            key_name = os.environ["EC2_KEY_PAIR"],
        )

        instance.add_to_role_policy(
            iam.PolicyStatement(
                actions=["acm-pca:ListCertificateAuthorities", "acm-pca:IssueCertificate", "acm-pca:GetCertificate"],
                resources=["*"]
            )
        )

        user_data_path = os.path.join(dirname, "user-data.sh")
        f = open(user_data_path, encoding='utf-8')
        commands = f.read()
        instance.add_user_data(commands)

        CfnOutput(self, "MskVpcId", export_name="msk-vpc-id", value=vpc.vpc_id)
        CfnOutput(self, "MskClusterArn", export_name="msk-cluster-arn", value=msk_cluster.attr_arn)

