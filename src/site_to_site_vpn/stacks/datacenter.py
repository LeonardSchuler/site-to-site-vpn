from aws_cdk import CfnOutput, Stack
import aws_cdk.aws_ec2 as ec2
from constructs import Construct
from ..constructs.customer_gateway import CustomerGateway


class DatacenterVPCStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # The code that defines your stack goes here

        self.vpc = ec2.Vpc(
            self,
            "VPC",
            vpc_name="datacenter",
            max_azs=3,
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            # configuration will create 3 groups in 2 AZs = 6 subnets.
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC, name="Public", cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    name="Private",
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, name="DB", cidr_mask=24
                ),
            ],
            # nat_gateway_provider=ec2.NatProvider.gateway(),
            nat_gateways=2,
        )
        self.vpc.add_gateway_endpoint(
            "S3Endpoint", service=ec2.GatewayVpcEndpointAwsService.S3
        )
        self.vpc.add_gateway_endpoint(
            "DynamoDbEndpoint", service=ec2.GatewayVpcEndpointAwsService.DYNAMODB
        )

        CfnOutput(self, "VPCId", value=self.vpc.vpc_id)


class DatacenterCustomerGatewayStack(Stack):
    def __init__(self, scope: Construct, id: str, vpc: ec2.Vpc, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        CustomerGateway(
            self,
            "CustomerGateway",
            vpc=vpc,
            public_subnet=vpc.public_subnets[0],
        )
