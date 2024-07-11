from constructs import Construct
from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3 as s3,
    aws_msk as msk,
    aws_ssm as ssm,
    aws_secretsmanager as secretsmanager,
    aws_opensearchservice as opensearch,
    aws_kms as kms,
    aws_logs as logs,
    Tags as tags,
    aws_opensearchservice as opensearch,
    aws_kinesisanalyticsv2 as kinesisanalyticsv2,
    aws_s3_deployment as s3deployment,
    Aws as AWS
)
import os
from . import parameters

class dataFeedMsk(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

#############       VPC Configurations      #############

        availabilityZonesList = [parameters.az1, parameters.az2]
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
                    "cidrMask": parameters.cidrMaskForSubnets,
                },
                {
                    "name": f"{parameters.project}-{parameters.env}-{parameters.app}-privateSubnet1",
                    "subnetType": ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    "cidrMask": parameters.cidrMaskForSubnets,
                }
            ]
        )
        tags.of(vpc).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-vpc")
        tags.of(vpc).add("project", parameters.project)
        tags.of(vpc).add("env", parameters.env)
        tags.of(vpc).add("app", parameters.app)

#############       EC2 Key Pair Configurations      #############

        keyPair = ec2.KeyPair.from_key_pair_name(self, "ec2KeyPair", parameters.producerEc2KeyPairName)

#############       Security Group Configurations      #############

        sgEc2MskCluster = ec2.SecurityGroup(self, "sgEc2MskCluster",
            security_group_name = f"{parameters.project}-{parameters.env}-{parameters.app}-sgEc2MskCluster",
            vpc=vpc,
            description="Security group associated with the EC2 instance of MSK Cluster",
            allow_all_outbound=True,
            disable_inline_rules=True
        )
        tags.of(sgEc2MskCluster).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-sgEc2MskCluster")
        tags.of(sgEc2MskCluster).add("project", parameters.project)
        tags.of(sgEc2MskCluster).add("env", parameters.env)
        tags.of(sgEc2MskCluster).add("app", parameters.app)

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

        sgApacheFlink = ec2.SecurityGroup(self, "sgApacheFlink",
            security_group_name = f"{parameters.project}-{parameters.env}-{parameters.app}-sgApacheFlink",
            vpc=vpc,
            description="Security group associated with the Apache Flink",
            allow_all_outbound=True,
            disable_inline_rules=True
        )
        tags.of(sgApacheFlink).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-sgApacheFlink")
        tags.of(sgApacheFlink).add("project", parameters.project)
        tags.of(sgApacheFlink).add("env", parameters.env)
        tags.of(sgApacheFlink).add("app", parameters.app)

        sgEc2MskCluster.add_ingress_rule(
            peer = ec2.Peer.any_ipv4(), 
            connection = ec2.Port.tcp(22), 
            description = "Allow SSH access from the internet"
        )

        sgEc2MskCluster.add_ingress_rule(
            peer = ec2.Peer.security_group_id(sgMskCluster.security_group_id),
            connection = ec2.Port.tcp_range(parameters.sgKafkaInboundPort, parameters.sgKafkaOutboundPort),
            description = "Allow Custom TCP traffic from sgEc2MskCluster to sgMskCluster"
        )

        sgMskCluster.add_ingress_rule(
            peer = ec2.Peer.security_group_id(sgEc2MskCluster.security_group_id),
            connection = ec2.Port.tcp_range(parameters.sgMskClusterInboundPort, parameters.sgMskClusterOutboundPort),
            description = "Allow all TCP traffic from sgEc2MskCluster to sgMskCluster"
        )
        sgMskCluster.add_ingress_rule(
            peer = ec2.Peer.security_group_id(sgMskCluster.security_group_id),
            connection = ec2.Port.tcp_range(parameters.sgMskClusterInboundPort, parameters.sgMskClusterOutboundPort),
            description = "Allow all TCP traffic from sgMskCluster to sgMskCluster"
        )
        sgMskCluster.add_ingress_rule(
            peer = ec2.Peer.security_group_id(sgApacheFlink.security_group_id),
            connection = ec2.Port.tcp_range(parameters.sgMskClusterInboundPort, parameters.sgMskClusterOutboundPort),
            description = "Allow all TCP traffic from security group sgApacheFlink to security group sgMskCluster"
        )
        sgApacheFlink.add_ingress_rule(
            peer = ec2.Peer.security_group_id(sgMskCluster.security_group_id),
            connection = ec2.Port.tcp_range(parameters.sgMskClusterInboundPort, parameters.sgMskClusterOutboundPort),
            description = "Allow all TCP traffic from security group sgMskCluster to security group sgApacheFlink"
        )
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

#############       KMS Configurations      #############

        customerManagedKey = kms.Key(self, "customerManagedKey",
            alias = f"{parameters.project}-{parameters.env}-{parameters.app}-sasl/scram-key",
            description = "Customer managed key",
            enable_key_rotation = True,
            removal_policy = RemovalPolicy.DESTROY
        )
        tags.of(customerManagedKey).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-customerManagedKey")
        tags.of(customerManagedKey).add("project", parameters.project)
        tags.of(customerManagedKey).add("env", parameters.env)
        tags.of(customerManagedKey).add("app", parameters.app)

        customerManagedKeyPolicy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "kms:Decrypt",
                "kms:Encrypt",
                "kms:GenerateDataKey",
                "kms:DescribeKey"
            ],
            resources=[
                f"arn:aws:kms:{AWS.REGION}:{AWS.ACCOUNT_ID}:key/*"
            ],
            principals=[
                iam.ArnPrincipal(f"arn:aws:iam::{parameters.mskCrossAccountId}:role/{parameters.ec2ConsumerRoleName}")
            ]
        )
        customerManagedKey.add_to_resource_policy(customerManagedKeyPolicy)

#############       Secrets Manager Configurations      #############

        mskProducerSecret = secretsmanager.Secret(self, "mskProducerSecret",
            description = "MSK Cluster Producer Secrets",
            secret_name = f"AmazonMSK_/-{parameters.project}-{parameters.env}-{parameters.app}-mskProducerSecret",
            generate_secret_string = secretsmanager.SecretStringGenerator(
                generate_string_key = "password",
                secret_string_template = '{"username": "%s"}' % parameters.mskProducerUsername,
                exclude_punctuation = True
            ),
            encryption_key=customerManagedKey
        )
        tags.of(mskProducerSecret).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-mskProducerSecret")
        tags.of(mskProducerSecret).add("project", parameters.project)
        tags.of(mskProducerSecret).add("env", parameters.env)
        tags.of(mskProducerSecret).add("app", parameters.app)
        mskProducerSecretPassword = mskProducerSecret.secret_value_from_json("password").unsafe_unwrap()

        mskConsumerSecret = secretsmanager.Secret(self, "mskConsumerSecret",
            description = "MSK Cluster Consumer Secrets",
            secret_name = f"AmazonMSK_/-{parameters.project}-{parameters.env}-{parameters.app}-mskConsumerSecret",
            generate_secret_string = secretsmanager.SecretStringGenerator(
                generate_string_key = "password",
                secret_string_template = '{"username": "%s"}' % parameters.mskConsumerUsername,
                exclude_punctuation = True
            ),
            encryption_key=customerManagedKey
        )
        tags.of(mskConsumerSecret).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-mskConsumerSecret")
        tags.of(mskConsumerSecret).add("project", parameters.project)
        tags.of(mskConsumerSecret).add("env", parameters.env)
        tags.of(mskConsumerSecret).add("app", parameters.app)
        mskConsumerSecretPassword= mskConsumerSecret.secret_value_from_json("password").unsafe_unwrap()

        mskConsumerSecretPolicy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "secretsmanager:GetSecretValue"
            ],
            resources=[
                f"arn:aws:secretsmanager:{AWS.REGION}:{AWS.ACCOUNT_ID}:secret:AmazonMSK_/-{parameters.project}-{parameters.env}-{parameters.app}-mskConsumerSecret-*"
            ],
            principals=[
                iam.ArnPrincipal(f"arn:aws:iam::{parameters.mskCrossAccountId}:role/{parameters.ec2ConsumerRoleName}")
            ]
        )
        mskConsumerSecret.add_to_resource_policy(mskConsumerSecretPolicy)

        openSearchSecrets = secretsmanager.Secret(self, "openSearchSecrets",
            description = "Secrets for OpenSearch",
            secret_name = f"{parameters.project}-{parameters.env}-{parameters.app}-openSearchSecrets",
            generate_secret_string = secretsmanager.SecretStringGenerator(),
            encryption_key = customerManagedKey
        )
        tags.of(openSearchSecrets).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-openSearchSecrets")
        tags.of(openSearchSecrets).add("project", parameters.project)
        tags.of(openSearchSecrets).add("env", parameters.env)
        tags.of(openSearchSecrets).add("app", parameters.app)
        openSearchMasterPasswordSecretValue = openSearchSecrets.secret_value
        openSearchMasterPassword = openSearchMasterPasswordSecretValue.unsafe_unwrap()

#############       SSM Parameter Store Configurations      #############

        mskProducerPwdParamStore = ssm.StringParameter(self, "mskProducerPwdParamStore",
            parameter_name = f"blogAws-{parameters.env}-mskProducerPwd-ssmParamStore",
            string_value = mskProducerSecretPassword,
            tier = ssm.ParameterTier.STANDARD
        )
        tags.of(mskProducerPwdParamStore).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-mskProducerPwdParamStore")
        tags.of(mskProducerPwdParamStore).add("project", parameters.project)
        tags.of(mskProducerPwdParamStore).add("env", parameters.env)
        tags.of(mskProducerPwdParamStore).add("app", parameters.app)
        mskProducerPwdParamStoreValue = mskProducerPwdParamStore.string_value

        mskConsumerPwdParamStore = ssm.StringParameter(self, "mskConsumerPwdParamStore",
            parameter_name = f"blogAws-{parameters.env}-mskConsumerPwd-ssmParamStore",
            string_value = mskConsumerSecretPassword,
            tier = ssm.ParameterTier.ADVANCED
        )
        tags.of(mskConsumerPwdParamStore).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-mskConsumerPwdParamStore")
        tags.of(mskConsumerPwdParamStore).add("project", parameters.project)
        tags.of(mskConsumerPwdParamStore).add("env", parameters.env)
        tags.of(mskConsumerPwdParamStore).add("app", parameters.app)

#############       Logs of MSK and Apache flink Configurations      #############
        
        mskClusterLogGroup = logs.LogGroup(self, "mskClusterLogGroup",
            log_group_name = f"{parameters.project}-{parameters.env}-{parameters.app}-mskClusterLogGroup",
            retention = logs.RetentionDays.ONE_WEEK,
            removal_policy = RemovalPolicy.DESTROY
        )
        tags.of(mskClusterLogGroup).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-mskClusterLogGroup")
        tags.of(mskClusterLogGroup).add("project", parameters.project)
        tags.of(mskClusterLogGroup).add("env", parameters.env)
        tags.of(mskClusterLogGroup).add("app", parameters.app)

        apacheFlinkAppLogGroup = logs.LogGroup(self, "apacheFlinkAppLogGroup",
            log_group_name = f"{parameters.project}-{parameters.env}-{parameters.app}-flinkAppLogGroup",
            retention = logs.RetentionDays.ONE_WEEK,
            removal_policy = RemovalPolicy.DESTROY
        )
        tags.of(apacheFlinkAppLogGroup).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-apacheFlinkAppLogGroup")
        tags.of(apacheFlinkAppLogGroup).add("project", parameters.project)
        tags.of(apacheFlinkAppLogGroup).add("env", parameters.env)
        tags.of(apacheFlinkAppLogGroup).add("app", parameters.app)
        
        apacheFlinkAppLogStream = logs.LogStream(self, "apacheFlinkAppLogStream",
            log_stream_name = f"{parameters.project}-{parameters.env}-{parameters.app}-flinkAppLogStream",
            log_group = logs.LogGroup.from_log_group_name(self, "importLogGroupName", log_group_name = apacheFlinkAppLogGroup.log_group_name),
            removal_policy = RemovalPolicy.DESTROY
        )
        tags.of(apacheFlinkAppLogStream).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-apacheFlinkAppLogStream")
        tags.of(apacheFlinkAppLogStream).add("project", parameters.project)
        tags.of(apacheFlinkAppLogStream).add("env", parameters.env)
        tags.of(apacheFlinkAppLogStream).add("app", parameters.app)

#############       MSK Cluster Configurations      #############

        mskClusterConfigProperties = [
            "auto.create.topics.enable=false",
            "default.replication.factor=3",
            "min.insync.replicas=2",
            "num.io.threads=8",
            "num.network.threads=5",
            "num.partitions=1",
            "num.replica.fetchers=2",
            "replica.lag.time.max.ms=30000",
            "socket.receive.buffer.bytes=102400",
            "socket.request.max.bytes=104857600",
            "socket.send.buffer.bytes=102400",
            "unclean.leader.election.enable=false",
            "zookeeper.session.timeout.ms=18000",
            "allow.everyone.if.no.acl.found=true"
        ]
        mskClusterConfigProperties = "\n".join(mskClusterConfigProperties)
        mskClusterConfiguration = msk.CfnConfiguration(self, "mskClusterConfiguration",
            name = f"{parameters.project}-{parameters.env}-{parameters.app}-mskClusterConfiguration",
            server_properties = mskClusterConfigProperties,
            description = "MSK cluster configuration"
        )

        mskCluster = msk.CfnCluster(self, "mskCluster",
            cluster_name = f"{parameters.project}-{parameters.env}-{parameters.app}-mskCluster",
            kafka_version = parameters.mskVersion,
            number_of_broker_nodes = parameters.mskNumberOfBrokerNodes,
            broker_node_group_info = msk.CfnCluster.BrokerNodeGroupInfoProperty(
                instance_type = parameters.mskClusterInstanceType,
                client_subnets = vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS).subnet_ids[:2],
                security_groups = [sgMskCluster.security_group_id],
                connectivity_info=None,
                storage_info = msk.CfnCluster.StorageInfoProperty(  
                    ebs_storage_info = msk.CfnCluster.EBSStorageInfoProperty(
                        volume_size = parameters.mskClusterVolumeSize
                    )
                )
            ),
            logging_info = msk.CfnCluster.LoggingInfoProperty(
                broker_logs = msk.CfnCluster.BrokerLogsProperty(
                    cloud_watch_logs = msk.CfnCluster.CloudWatchLogsProperty(
                        enabled = True,
                        log_group = mskClusterLogGroup.log_group_name
                    ),
                )
            ),
            client_authentication = msk.CfnCluster.ClientAuthenticationProperty(
                sasl = msk.CfnCluster.SaslProperty(
                    scram = msk.CfnCluster.ScramProperty(
                        enabled = parameters.mskScramPropertyEnable
                    )
                )
            ),
            configuration_info=msk.CfnCluster.ConfigurationInfoProperty(
                arn=mskClusterConfiguration.attr_arn,
                revision=mskClusterConfiguration.attr_latest_revision_revision
            ),
            encryption_info = msk.CfnCluster.EncryptionInfoProperty(
                encryption_in_transit = msk.CfnCluster.EncryptionInTransitProperty(
                    client_broker = parameters.mskEncryptionProducerBroker,
                    in_cluster = parameters.mskEncryptionInClusterEnable
                )
            )
        )
        tags.of(mskCluster).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-mskCluster")
        tags.of(mskCluster).add("project", parameters.project)
        tags.of(mskCluster).add("env", parameters.env)
        tags.of(mskCluster).add("app", parameters.app)

        batchScramSecret = msk.CfnBatchScramSecret(self, "mskBatchScramSecret",
            cluster_arn = mskCluster.attr_arn,
            secret_arn_list = [mskProducerSecret.secret_arn, mskConsumerSecret.secret_arn]
        )

        mskClusterArnParamStore = ssm.StringParameter(self, "mskClusterArnParamStore",
            parameter_name = f"blogAws-{parameters.env}-mskClusterArn-ssmParamStore",
            string_value = mskCluster.attr_arn,
            tier = ssm.ParameterTier.STANDARD
        )
        tags.of(mskClusterArnParamStore).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-mskClusterArnParamStore")
        tags.of(mskClusterArnParamStore).add("project", parameters.project)
        tags.of(mskClusterArnParamStore).add("env", parameters.env)
        tags.of(mskClusterArnParamStore).add("app", parameters.app)
        mskClusterArnParamStoreValue = mskClusterArnParamStore.string_value

        mskClusterBrokerUrlParamStore = ssm.StringParameter(self, "mskClusterBrokerUrlParamStore",
            parameter_name = f"blogAws-{parameters.env}-mskClusterBrokerUrl-ssmParamStore",
            string_value = "dummy",         # We're passing a dummy value in this SSM parameter. The actual value will be replaced by EC2 userdata during the process
            tier = ssm.ParameterTier.STANDARD
        )
        tags.of(mskClusterBrokerUrlParamStore).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-mskClusterBrokerUrlParamStore")
        tags.of(mskClusterBrokerUrlParamStore).add("project", parameters.project)
        tags.of(mskClusterBrokerUrlParamStore).add("env", parameters.env)
        tags.of(mskClusterBrokerUrlParamStore).add("app", parameters.app)

        getAzIdsParamStore = ssm.StringParameter(self, "getAzIdsParamStore",
                parameter_name = f"blogAws-{parameters.env}-getAzIdsParamStore-ssmParamStore",
                string_value = "dummy",         # We're passing a dummy value in this SSM parameter. The actual value will be replaced by EC2 userdata during the process
                tier = ssm.ParameterTier.STANDARD,
                type = ssm.ParameterType.STRING_LIST
            )
        tags.of(getAzIdsParamStore).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-getAzIdsParamStore")
        tags.of(getAzIdsParamStore).add("project", parameters.project)
        tags.of(getAzIdsParamStore).add("env", parameters.env)
        tags.of(getAzIdsParamStore).add("app", parameters.app)

#We are unable to activate the SASL/SCRAM authentication method for producer authentication during the cluster creation process
        enableSaslScramClientAuth = parameters.enableSaslScramClientAuth
        if enableSaslScramClientAuth:
            mskCluster.add_property_override(
                'BrokerNodeGroupInfo.ConnectivityInfo',
                {
                    'VpcConnectivity': {
                        'ClientAuthentication': {
                            'Sasl': {
                                'Iam': {'Enabled': False},
                                'Scram': {'Enabled': True}
                            },
                            'Tls': {'Enabled': False}
                        }
                    }
                }
            )
        else:
            print("SASL SCRAM is not associated with the MSK Cluster")

#In the second iteration, we will implement cluster configurations since setting "allow.everyone.if.no.acl.found=true" prevents topic creation in the MSK Cluster
        enableClusterConfig = parameters.enableClusterConfig
        if enableClusterConfig:
            mskCluster.add_property_override(
                'ConfigurationInfo',
                {
                    "Arn": mskClusterConfiguration.attr_arn,
                    "Revision": mskClusterConfiguration.attr_latest_revision_revision
                }
            )
        else:
            print("Cluster Configuration is not associated with the MSK Cluster")

#In the second iteration, we'll attach a cluster policy to address the Private Link scenario.
        
        enableClusterPolicy = parameters.enableClusterPolicy
        if enableClusterPolicy:
            mskClusterPolicy = msk.CfnClusterPolicy(self, "mskClusterPolicy",
                cluster_arn = mskClusterArnParamStoreValue,
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {
                                "AWS": [parameters.mskCrossAccountId]
                            },
                            "Action": [
                                "kafka:CreateVpcConnection",
                                "kafka:GetBootstrapBrokers",
                                "kafka:DescribeCluster",
                                "kafka:DescribeClusterV2"
                            ],
                            "Resource": mskClusterArnParamStoreValue
                        }
                    ]
                }
            )
            mskClusterPolicy.node.add_dependency(mskCluster)
        else:
            print("Cluster Policy is not associated with the MSK Cluster")

#############       IAM Roles and Policies Configurations      #############

        ec2MskClusterRole = iam.Role(self, "ec2MskClusterRole",
            role_name = f"{parameters.project}-{parameters.env}-{parameters.app}-ec2MskClusterRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com")
        )
        tags.of(ec2MskClusterRole).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-ec2MskClusterRole")
        tags.of(ec2MskClusterRole).add("project", parameters.project)
        tags.of(ec2MskClusterRole).add("env", parameters.env)
        tags.of(ec2MskClusterRole).add("app", parameters.app)
        
        ec2MskClusterRole.attach_inline_policy(
            iam.Policy(self, 'ec2MskClusterPolicy',
                statements = [
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
                        resources= [mskCluster.attr_arn,
                            f"arn:aws:kafka:{AWS.REGION}:{AWS.ACCOUNT_ID}:topic/{mskCluster.cluster_name}/*/*",
                            f"arn:aws:kafka:{AWS.REGION}:{AWS.ACCOUNT_ID}:group/{mskCluster.cluster_name}/*/*"
                        ]
                    ),
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
                            "ec2:DescribeSubnets"
                        ],
                        resources= ["*"]
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
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        resources= [f"arn:aws:logs:{AWS.REGION}:{AWS.ACCOUNT_ID}:log-group:okok:log-stream:*",
                            f"arn:aws:logs:{AWS.REGION}:{AWS.ACCOUNT_ID}:log-group:*"
                        ]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions=[
                            "s3:GetObject",
                            "s3:PutObject"
                        ],
                        resources= [f"arn:aws:s3:::{s3DestinationBucket.bucket_name}",
                                    f"arn:aws:s3:::{s3DestinationBucket.bucket_name}/*"
                        ]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions=[
                            "ssm:PutParameter",
                            "ssm:GetParameters",
                            "ssm:GetParameter"
                        ],
                        resources= [f"arn:aws:ssm:{AWS.REGION}:{AWS.ACCOUNT_ID}:parameter/{mskClusterBrokerUrlParamStore.parameter_name}",
                                    f"arn:aws:ssm:{AWS.REGION}:{AWS.ACCOUNT_ID}:parameter/{getAzIdsParamStore.parameter_name}"
                                    ]
                    )
                ]
            )
        )

        apacheFlinkAppRole = iam.Role(self, "apacheFlinkAppRole",
            role_name = f"{parameters.project}-{parameters.env}-{parameters.app}-apacheFlinkAppRole",
            assumed_by=iam.ServicePrincipal("kinesisanalytics.amazonaws.com"),
            managed_policies = [
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonMSKReadOnlyAccess")
            ]
        )
        tags.of(apacheFlinkAppRole).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-apacheFlinkAppRole")
        tags.of(apacheFlinkAppRole).add("project", parameters.project)
        tags.of(apacheFlinkAppRole).add("env", parameters.env)
        tags.of(apacheFlinkAppRole).add("app", parameters.app)

        apacheFlinkAppRole.attach_inline_policy(
            iam.Policy(self, 'apacheFlinkAppPolicy',
                statements = [
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions = [
                            "s3:GetObject",
                            "s3:GetObjectVersion"
                        ],
                        resources = [f"{s3DestinationBucket.bucket_arn}/dataFeedMskArtifacts/{parameters.apacheFlinkBucketKey}"]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions = [
                            "logs:DescribeLogGroups"
                        ],
                        resources = [apacheFlinkAppLogGroup.log_group_arn]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions = [
                            "ec2:DescribeVpcs",
                            "ec2:DescribeSubnets",
                            "ec2:DescribeSecurityGroups",
                            "ec2:DescribeDhcpOptions"
                        ],
                        resources = ["*"]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions = [
                            "ec2:CreateNetworkInterface",
                            "ec2:CreateNetworkInterfacePermission",
                            "ec2:DescribeNetworkInterfaces",
                            "ec2:DeleteNetworkInterface"
                        ],
                        resources = [f"arn:aws:ec2:{AWS.REGION}:{AWS.ACCOUNT_ID}:network-interface/*",
                                     f"arn:aws:ec2:{AWS.REGION}:{AWS.ACCOUNT_ID}:security-group/*",
                                     f"arn:aws:ec2:{AWS.REGION}:{AWS.ACCOUNT_ID}:subnet/*"
                        ]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions = [
                            "logs:DescribeLogStreams"
                        ],
                        resources = [f"arn:aws:logs:{AWS.REGION}:{AWS.ACCOUNT_ID}:log-group:{apacheFlinkAppLogGroup.log_group_name}:log-stream:*"]
                    ),
                    iam.PolicyStatement(
                        effect = iam.Effect.ALLOW,
                        actions = [
                            "logs:PutLogEvents"
                        ],
                        resources = [f"arn:aws:logs:{AWS.REGION}:{AWS.ACCOUNT_ID}:log-group:{apacheFlinkAppLogGroup.log_group_name}:log-stream:{apacheFlinkAppLogStream.log_stream_name}"
                        ]
                    )
                ]
            )
        )

#############       MSK Producer and Producer EC2 Instance Configurations      #############

        user_data = ec2.UserData.for_linux()

        user_data.add_s3_download_command(
            bucket=s3.Bucket.from_bucket_name(self, "s3BucketArtifacts", s3DestinationBucket.bucket_name),
            bucket_key="dataFeedMskArtifacts/kafkaProducerEC2Instance.sh"
        )

        script_path = os.path.join(os.path.dirname(__file__), 'kafkaProducerEC2Instance.sh')
        with open(script_path, 'r') as file:
            user_data_script = file.read()

        user_data_script = user_data_script.replace("${MSK_PRODUCER_USERNAME}", parameters.mskProducerUsername)
        user_data_script = user_data_script.replace("${MSK_PRODUCER_PASSWORD}", mskProducerPwdParamStoreValue)
        user_data_script = user_data_script.replace("${MSK_CLUSTER_ARN}", mskCluster.attr_arn)
        user_data_script = user_data_script.replace("${MSK_CLUSTER_BROKER_URL_PARAM_NAME}", mskClusterBrokerUrlParamStore.parameter_name)
        user_data_script = user_data_script.replace("${AWS_REGION}", self.region)
        user_data_script = user_data_script.replace("${VPC_ID}", vpc.vpc_id)
        user_data_script = user_data_script.replace("${AZ_IDS_PARAM_NAME}", getAzIdsParamStore.parameter_name)
        user_data_script = user_data_script.replace("${AZ_IDS_PARAM_TYPE}", getAzIdsParamStore.parameter_type)
        user_data_script = user_data_script.replace("${MSK_TOPIC_NAME_1}", parameters.mskTopicName1)
        user_data_script = user_data_script.replace("${MSK_TOPIC_NAME_2}", parameters.mskTopicName2)
        user_data_script = user_data_script.replace("${MSK_TOPIC_NAME_3}", parameters.mskTopicName3)
        user_data_script = user_data_script.replace("${MSK_TOPIC_NAME_4}", parameters.mskTopicName4)
        user_data_script = user_data_script.replace("${MSK_CONSUMER_USERNAME}", parameters.mskConsumerUsername)
        user_data_script = user_data_script.replace("${BUCKET_NAME}", s3DestinationBucket.bucket_name)

        user_data.add_commands(user_data_script)

        kafkaProducerEc2BlockDevices = ec2.BlockDevice(device_name="/dev/xvda", volume=ec2.BlockDeviceVolume.ebs(10))
        kafkaProducerEC2Instance = ec2.Instance(self, "kafkaProducerEC2Instance",
            instance_name = f"{parameters.project}-{parameters.env}-{parameters.app}-kafkaProducerEC2Instance",
            vpc = vpc,
            instance_type = ec2.InstanceType.of(ec2.InstanceClass(parameters.ec2InstanceClass), ec2.InstanceSize(parameters.ec2InstanceSize)),
            machine_image = ec2.AmazonLinuxImage(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2), #ec2.MachineImage().lookup(name = parameters.ec2AmiName),
            availability_zone = vpc.availability_zones[1],
            block_devices = [kafkaProducerEc2BlockDevices],
            vpc_subnets = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            key_pair = keyPair,
            security_group = sgEc2MskCluster,
            user_data = user_data,
            role = ec2MskClusterRole
        )
        tags.of(kafkaProducerEC2Instance).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-kafkaProducerEC2Instance")
        tags.of(kafkaProducerEC2Instance).add("project", parameters.project)
        tags.of(kafkaProducerEC2Instance).add("env", parameters.env)
        tags.of(kafkaProducerEC2Instance).add("app", parameters.app)

#############       OpenSearch Configurations      #############

        opensearch_access_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            principals=[iam.AnyPrincipal()],
            actions=["es:*"],
            resources= ["*"]
        )

        OPENSEARCH_VERSION = parameters.openSearchVersion
        openSearchDomain = opensearch.Domain(self, "openSearchDomain",
            domain_name = f"awsblog-{parameters.env}-public-domain",
            version = opensearch.EngineVersion.open_search(OPENSEARCH_VERSION),
            capacity = opensearch.CapacityConfig(
                multi_az_with_standby_enabled = parameters.openSearchMultiAzWithStandByEnable,
                data_nodes = parameters.openSearchDataNodes,
                data_node_instance_type = parameters.openSearchDataNodeInstanceType
            ),
            ebs = opensearch.EbsOptions(
                volume_size = parameters.openSearchVolumeSize,
                volume_type = ec2.EbsDeviceVolumeType.GP3
            ),
            access_policies = [opensearch_access_policy],
            enforce_https = True,                                                 # Required when FGAC is enabled
            node_to_node_encryption = parameters.openSearchNodeToNodeEncryption,  # Required when FGAC is enabled
            encryption_at_rest = opensearch.EncryptionAtRestOptions(
                enabled = parameters.openSearchEncryptionAtRest
            ),
            fine_grained_access_control = opensearch.AdvancedSecurityOptions(
                master_user_name = parameters.openSearchMasterUsername,
                master_user_password = openSearchMasterPasswordSecretValue
            ),
            removal_policy = RemovalPolicy.DESTROY
        )
        openSearchDomain.node.add_dependency(kafkaProducerEC2Instance)
        tags.of(openSearchDomain).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-openSearchDomain")
        tags.of(openSearchDomain).add("project", parameters.project)
        tags.of(openSearchDomain).add("env", parameters.env)
        tags.of(openSearchDomain).add("app", parameters.app)

#############       Apache Flink Configurations      #############

        subnetIds = vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS).subnet_ids
        apacheFlinkApp = kinesisanalyticsv2.CfnApplication(self, "apacheFlinkApp",
            application_name = f"{parameters.project}-{parameters.env}-{parameters.app}-apacheFlinkApp",
            application_description = "Apache Flink Application",
            runtime_environment=parameters.apacheFlinkRuntimeVersion,
            service_execution_role=apacheFlinkAppRole.role_arn,
            application_configuration=kinesisanalyticsv2.CfnApplication.ApplicationConfigurationProperty(
                application_code_configuration=kinesisanalyticsv2.CfnApplication.ApplicationCodeConfigurationProperty(
                    code_content_type = "ZIPFILE",
                    code_content=kinesisanalyticsv2.CfnApplication.CodeContentProperty(
                        s3_content_location=kinesisanalyticsv2.CfnApplication.S3ContentLocationProperty(
                            bucket_arn=s3DestinationBucket.bucket_arn,
                            file_key=f"dataFeedMskArtifacts/{parameters.apacheFlinkBucketKey}"
                        )
                    )
                ),
                application_snapshot_configuration=kinesisanalyticsv2.CfnApplication.ApplicationSnapshotConfigurationProperty(
                    snapshots_enabled=False
                ),
                flink_application_configuration=kinesisanalyticsv2.CfnApplication.FlinkApplicationConfigurationProperty(
                    checkpoint_configuration=kinesisanalyticsv2.CfnApplication.CheckpointConfigurationProperty(
                        configuration_type="CUSTOM",
                        checkpointing_enabled=True
                    ),
                    monitoring_configuration=kinesisanalyticsv2.CfnApplication.MonitoringConfigurationProperty(
                        configuration_type="CUSTOM",
                        log_level="INFO",
                        metrics_level="APPLICATION"
                    ),
                    parallelism_configuration=kinesisanalyticsv2.CfnApplication.ParallelismConfigurationProperty(
                        configuration_type="CUSTOM",
                        auto_scaling_enabled=True
                    )
                ),
                environment_properties=kinesisanalyticsv2.CfnApplication.EnvironmentPropertiesProperty(
                    property_groups=[kinesisanalyticsv2.CfnApplication.PropertyGroupProperty(
                        property_group_id="FlinkApplicationProperties",
                        property_map={
                            "msk.username" : parameters.mskProducerUsername,
                            "msk.broker.url" : mskClusterBrokerUrlParamStore.string_value,
                            "msk.password" : mskProducerSecretPassword, 
                            "opensearch.endpoint" : openSearchDomain.domain_endpoint,
                            "opensearch.username" : parameters.openSearchMasterUsername,
                            "opensearch.password" : openSearchMasterPassword,
                            "opensearch.port" : "443",
                            "event.ticker.interval.minutes" : parameters.eventTickerIntervalMinutes,
                            "event.ticker.1" : parameters.mskTopicName1,
                            "event.ticker.2" : parameters.mskTopicName2,
                            "topic.ticker.1" : parameters.mskTopicName3,
                            "topic.ticker.2" : parameters.mskTopicName4
                        }
                    )]
                ),
                vpc_configurations = [kinesisanalyticsv2.CfnApplication.VpcConfigurationProperty(
                    security_group_ids = [sgApacheFlink.security_group_id],
                    subnet_ids = subnetIds
                )],
            )
        )
        apacheFlinkApp.node.add_dependency(apacheFlinkAppRole)
        apacheFlinkApp.node.add_dependency(sgApacheFlink)
        apacheFlinkApp.node.add_dependency(kafkaProducerEC2Instance)
        apacheFlinkApp.node.add_dependency(openSearchDomain)
        tags.of(apacheFlinkApp).add("name", f"{parameters.project}-{parameters.env}-{parameters.app}-apacheFlinkApp")
        tags.of(apacheFlinkApp).add("project", parameters.project)
        tags.of(apacheFlinkApp).add("env", parameters.env)
        tags.of(apacheFlinkApp).add("app", parameters.app)

        apacheFlinkAppLogs = kinesisanalyticsv2.CfnApplicationCloudWatchLoggingOption(self, "apacheFlinkAppLogs",
            application_name = apacheFlinkApp.application_name,
            cloud_watch_logging_option = kinesisanalyticsv2.CfnApplicationCloudWatchLoggingOption.CloudWatchLoggingOptionProperty(
                log_stream_arn = f"arn:aws:logs:{AWS.REGION}:{AWS.ACCOUNT_ID}:log-group:{apacheFlinkAppLogGroup.log_group_name}:log-stream:{apacheFlinkAppLogStream.log_stream_name}"
            )
        )
        apacheFlinkAppLogs.node.add_dependency(apacheFlinkApp)

#############       Output Values      #############

        CfnOutput(self, "vpcId",
            value = vpc.vpc_id,
            description = "VPC Id",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-vpcId"
        )
        CfnOutput(self, "sgEc2MskClusterId",
            value = sgEc2MskCluster.security_group_id,
            description = "Security group Id of EC2 MSK cluster",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-sgEc2MskClusterId"
        )
        CfnOutput(self, "sgMskClusterId",
            value = sgMskCluster.security_group_id,
            description = "Security group Id of MSK Cluster",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-sgMskClusterId"
        )
        CfnOutput(self, "ec2MskClusterRoleArn",
            value = ec2MskClusterRole.role_arn,
            description = "ARN of EC2 MSK cluster role",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-ec2MskClusterRoleArn"
        )
        CfnOutput(self, "mskClusterName",
            value = mskCluster.cluster_name,
            description = "Name of an MSK cluster",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-mskClusterName"
        )
        CfnOutput(self, "mskClusterArn",
            value = mskCluster.attr_arn,
            description = "ARN of an MSK cluster",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-mskClusterArn"
        )
        CfnOutput(self, "apacheFlinkAppRoleArn",
            value = apacheFlinkAppRole.role_arn,
            description = "ARN of apache flink app role",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-apacheFlinkAppRoleArn"
        )
        CfnOutput(self, "kafkaProducerEC2InstanceId",
            value = kafkaProducerEC2Instance.instance_id,
            description = "Kafka producer EC2 instance Id",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-kafkaProducerEC2InstanceId"
        )
        CfnOutput(self, "customerManagedKeyArn",
            value = customerManagedKey.key_arn,
            description = "ARN of customer managed key",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-customerManagedKeyArn"
        )
        CfnOutput(self, "mskProducerSecretName",
            value = mskProducerSecret.secret_name,
            description = "MSK cluster producer secrets name",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-mskProducerSecretName"
        )
        CfnOutput(self, "mskConsumerSecretName",
            value = mskConsumerSecret.secret_name,
            description = "MSK cluster consumer secrets name",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-mskConsumerSecretName"
        )
        CfnOutput(self, "flinkAppLogGroupArn",
            value = apacheFlinkAppLogGroup.log_group_arn,
            description = "Arn of an Apache Flink log group",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-apacheFlinkAppLogGroupArn"
        )
        CfnOutput(self, "flinkAppLogGroupName",
            value = apacheFlinkAppLogGroup.log_group_name,
            description = "Name of an Apache Flink log group",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-apacheFlinkAppLogGroupName"
        )
        CfnOutput(self, "openSearchSecretsArn",
            value = openSearchSecrets.secret_arn,
            description = "ARN of MSK cluster secrets",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-openSearchSecretsArn"
        )
        CfnOutput(self, "openSearchDomainName",
            value = openSearchDomain.domain_name,
            description = "OpenSearch domain name",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-openSearchDomainName"
        )
        CfnOutput(self, "openSearchDomainEndpoint",
            value = openSearchDomain.domain_endpoint,
            description = "OpenSearch domain endpoint",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-openSearchDomainEndpoint"
        )
        CfnOutput(self, "apacheFlinkAppName",
            value = apacheFlinkApp.application_name,
            description = "Apache flink application name",
            export_name = f"{parameters.project}-{parameters.env}-{parameters.app}-apacheFlinkAppName"
        )