from constructs import Construct
from aws_cdk import (
    Stack,
    CfnOutput,
    Aws as AWS,
    RemovalPolicy,
    aws_s3 as s3,
    Tags as tags,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_iam as iam,
    aws_msk as msk,
    aws_s3_deployment as s3deployment
)
import os
from . import parameters

class dataFeedMskCrossAccount(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

#############       VPC Configurations      #############

        availabilityZonesList = [parameters.crossAccountAz1, parameters.crossAccountAz2]
        vpc = ec2.Vpc (self, "vpc",
            vpc_name = f"{parameters.project}-{parameters.env}-{parameters.app}-vpc",
            ip_addresses = ec2.IpAddresses.cidr(parameters.cidrRange),
            enable_dns_hostnames = parameters.enableDnsHostnames,
            enable_dns_support = parameters.enableDnsSupport,
            availability_zones = availabilityZonesList,
            nat_gateways = parameters.numberOfNatGateways,
            subnet_configuration = [
                {
                    "name": f"{parameters.project}-{parameters.env}-{parameters.app}-publicSubnet1",
                    "subnetType": ec2.SubnetType.PUBLIC,
                    "cidrMask": parameters.cidrMaskForSubnets
                },
                {
                    "name": f"{parameters.project}-{parameters.env}-{parameters.app}-privateSubnet1",
                    "subnetType": ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    "cidrMask": parameters.cidrMaskForSubnets
                }
            ]
        )
        tags.of(vpc).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-vpc")
        tags.of(vpc).add("project", parameters.project)
        tags.of(vpc).add("env", parameters.env)
        tags.of(vpc).add("app", parameters.app)

#############       EC2 Key Pair Configurations      #############

        keyPair = ec2.KeyPair.from_key_pair_name(self, "ec2KeyPair", parameters.consumerEc2KeyPairName)

#############       Security Group Configurations      #############

        sgMskCluster = ec2.SecurityGroup(self, "sgMskCluster",
            security_group_name = f"{parameters.project}-{parameters.env}-{parameters.app}-sgMskCluster",
            vpc=vpc,
            description="Security group associated with the MSK Cluster",
            allow_all_outbound=True,
            disable_inline_rules=True
        )
        tags.of(sgMskCluster).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-sgMskCluster")
        tags.of(sgMskCluster).add("project", parameters.project)
        tags.of(sgMskCluster).add("env", parameters.env)
        tags.of(sgMskCluster).add("app", parameters.app)

        sgConsumerEc2 = ec2.SecurityGroup(self, "sgConsumerEc2",
            security_group_name = f"{parameters.project}-{parameters.env}-{parameters.app}-sgConsumerEc2",
            vpc=vpc,
            description="Security group associated with the EC2 instance of MSK Cluster",
            allow_all_outbound=True,
            disable_inline_rules=True
        )
        tags.of(sgConsumerEc2).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-sgConsumerEc2")
        tags.of(sgConsumerEc2).add("project", parameters.project)
        tags.of(sgConsumerEc2).add("env", parameters.env)
        tags.of(sgConsumerEc2).add("app", parameters.app)

        sgConsumerEc2.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "Allow SSH access from the internet")

        sgConsumerEc2.add_ingress_rule(
            peer = ec2.Peer.security_group_id(sgMskCluster.security_group_id),
            connection = ec2.Port.tcp_range(parameters.sgKafkaInboundPort, parameters.sgKafkaOutboundPort),
            description = "Allow Custom TCP traffic from sgConsumerEc2 to sgMskCluster"
        )

        sgMskCluster.add_ingress_rule(
            peer = ec2.Peer.security_group_id(sgConsumerEc2.security_group_id),
            connection = ec2.Port.tcp_range(parameters.sgMskClusterInboundPort, parameters.sgMskClusterOutboundPort),
            description = "Allow all TCP traffic from sgConsumerEc2 to sgMskCluster"
        )
        sgMskCluster.add_ingress_rule(
            peer = ec2.Peer.security_group_id(sgMskCluster.security_group_id),
            connection = ec2.Port.tcp_range(parameters.sgMskClusterInboundPort, parameters.sgMskClusterOutboundPort),
            description = "Allow all TCP traffic from sgMskCluster to sgMskCluster"
        )

        consumerEc2Role = iam.Role.from_role_name(self, "consumerEc2Role", role_name=parameters.ec2ConsumerRoleName)
        tags.of(consumerEc2Role).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-consumerEc2Role")
        tags.of(consumerEc2Role).add("project", parameters.project)
        tags.of(consumerEc2Role).add("env", parameters.env)
        tags.of(consumerEc2Role).add("app", parameters.app)

#############       S3 Bucket Configurations      #############
#############       Deploying Artifacts from source bucket to destination bucket      #############

        s3SourceBucket = s3.Bucket.from_bucket_name(self, "s3SourceBucketArtifacts", parameters.s3BucketName)
 
        s3DestinationBucket = s3.Bucket(self, "s3DestinationBucket",
            bucket_name=f"{parameters.project}-{parameters.env}-artifacts-{AWS.REGION}-{AWS.ACCOUNT_ID}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY
        )
 
        s3ArtifactsDeployment = s3deployment.BucketDeployment(self, 's3ArtifactsDeployment',
            sources=[s3deployment.Source.bucket(s3SourceBucket, 'dataFeedMskArtifacts.zip')],
            destination_bucket=s3DestinationBucket,
            destination_key_prefix = ''
        )
#############       IAM Roles and Policies Configurations      #############

        consumerEc2Role.attach_inline_policy(
            iam.Policy(self, 'ec2MskClusterPolicy',
                statements = [
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions=[
                            "ec2:DescribeInstances",
                            "ec2:DescribeInstanceAttribute",
                            "ec2:ModifyInstanceAttribute",
                            "ec2:DescribeVpcs",
                            "ec2:DescribeSecurityGroups",
                            "ec2:DescribeSubnets",
                            "ec2:DescribeTags"
                        ],
                        resources= [f"arn:aws:ec2:{AWS.REGION}:{AWS.ACCOUNT_ID}:instance/*",
                            f"arn:aws:ec2:{AWS.REGION}:{AWS.ACCOUNT_ID}:volume/*",
                            f"arn:aws:ec2:{AWS.REGION}:{AWS.ACCOUNT_ID}:security-group/*"
                        ]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions=[
                            "kafka:ListClusters",
                            "kafka:DescribeCluster",
                            "kafka-cluster:Connect",
                            "kafka-cluster:ReadData",
                            "kafka:DescribeClusterV2",
                            "kafka-cluster:CreateTopic",
                            "kafka-cluster:DeleteTopic",
                            "kafka-cluster:AlterCluster",
                            "kafka-cluster:WriteData",
                            "kafka-cluster:AlterGroup",
                            "kafka-cluster:DescribeGroup",
                            "kafka-cluster:DescribeClusterDynamicConfiguration",
                        ],
                        resources= [parameters.mskClusterArn,
                            f"arn:aws:kafka:{AWS.REGION}:{AWS.ACCOUNT_ID}:topic/{parameters.mskClusterName}/*/*",
                            f"arn:aws:kafka:{AWS.REGION}:{AWS.ACCOUNT_ID}:group/{parameters.mskClusterName}/*/*"
                        ]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions=[
                            "kafka:GetBootstrapBrokers"
                        ],
                        resources= ["*"]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions=[
                            "s3:GetObject",
                            "s3:PutObject"
                        ],
                        resources = [f"arn:aws:s3:::{s3DestinationBucket.bucket_name}",
                                    f"arn:aws:s3:::{s3DestinationBucket.bucket_name}/*"
                        ]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions=[
                            "secretsmanager:GetSecretValue"
                        ],
                        resources = [
                            parameters.mskConsumerSecretArn
                        ]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions=[
                            "kms:Decrypt"
                        ],
                        resources = [
                            parameters.customerManagedKeyArn
                        ]
                    )
                ]
            )
        )

#############      Consumer EC2 Instance Configurations      #############

        user_data = ec2.UserData.for_linux()

        user_data.add_s3_download_command(
            bucket=s3.Bucket.from_bucket_name(self, "s3BucketArtifacts", s3DestinationBucket.bucket_name),
            bucket_key="dataFeedMskArtifacts/kafkaConsumerEC2Instance.sh"
        )

        script_path = os.path.join(os.path.dirname(__file__), 'kafkaConsumerEC2Instance.sh')
        with open(script_path, 'r') as file:
            user_data_script = file.read()

        user_data_script = user_data_script.replace("${MSK_CONSUMER_USERNAME}", parameters.mskConsumerUsername)
        user_data_script = user_data_script.replace("${MSK_CONSUMER_SECRET_ARN}", parameters.mskConsumerSecretArn)
        user_data_script = user_data_script.replace("${AWS_REGION}", self.region)

        user_data.add_commands(user_data_script)
        
        kafkaConsumerEc2BlockDevices = ec2.BlockDevice(device_name="/dev/xvda", volume=ec2.BlockDeviceVolume.ebs(10))
        kafkaConsumerEC2Instance = ec2.Instance(self, "kafkaConsumerEC2Instance",
            instance_name = f"{parameters.project}-{parameters.env}-{parameters.app}-kafkaConsumerEC2Instance",
            vpc = vpc,
            instance_type = ec2.InstanceType.of(ec2.InstanceClass(parameters.ec2InstanceClass), ec2.InstanceSize(parameters.ec2InstanceSize)),
            machine_image = ec2.AmazonLinuxImage(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
            availability_zone = vpc.availability_zones[1],
            block_devices = [kafkaConsumerEc2BlockDevices],
            vpc_subnets = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            key_pair = keyPair,
            security_group = sgConsumerEc2,
            user_data = user_data,
            role = consumerEc2Role
        )
        tags.of(kafkaConsumerEC2Instance).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-kafkaConsumerEC2Instance")
        tags.of(kafkaConsumerEC2Instance).add("project", parameters.project)
        tags.of(kafkaConsumerEC2Instance).add("env", parameters.env)
        tags.of(kafkaConsumerEC2Instance).add("app", parameters.app)

#############       MSK Cluster VPC Connection      #############

        mskClusterVpcConnection = msk.CfnVpcConnection(self, "mskClusterVpcConnection",
            authentication="SASL_SCRAM",
            client_subnets=vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS).subnet_ids[:2],
            security_groups=[sgMskCluster.security_group_id],
            target_cluster_arn=parameters.mskClusterArn,
            vpc_id=vpc.vpc_id
        )
        mskClusterVpcConnection.node.add_dependency(vpc)
        mskClusterVpcConnection.node.add_dependency(sgMskCluster)
        tags.of(mskClusterVpcConnection).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-mskClusterVpcConnection")
        tags.of(mskClusterVpcConnection).add("project", parameters.project)
        tags.of(mskClusterVpcConnection).add("env", parameters.env)
        tags.of(mskClusterVpcConnection).add("app", parameters.app)

#############       Output Values      #############

        CfnOutput(self, "vpcId",
            value = vpc.vpc_id,
            description = "VPC Id",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-vpcId"
        )
        CfnOutput(self, "sgMskClusterId",
            value = sgMskCluster.security_group_id,
            description = "Security group ID of the MSK cluster attached to mskClusterVpcConnection",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-sgMskClusterId"
        )
        CfnOutput(self, "sgConsumerEc2Id",
            value = sgConsumerEc2.security_group_id,
            description = "Security group ID of the EC2 consumer for the MSK cluster",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-sgConsumerEc2Id"
        )
        CfnOutput(self, "consumerEc2RoleArn",
            value = consumerEc2Role.role_arn,
            description = "ARN of EC2 MSK cluster role",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-consumerEc2RoleArn"
        )
        CfnOutput(self, "kafkaConsumerEC2InstanceId",
            value = kafkaConsumerEC2Instance.instance_id,
            description = "Kafka consumer EC2 instance Id",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-kafkaConsumerEC2InstanceId"
        )