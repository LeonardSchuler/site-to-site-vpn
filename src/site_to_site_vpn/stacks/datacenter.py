from aws_cdk import CfnOutput, Stack
import aws_cdk.aws_ec2 as ec2
from constructs import Construct
from ..constructs.customer_gateway import CustomerGateway


class DatacenterVPCStack(Stack):
    def __init__(self, scope: Construct, id: str, *, cidr: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # The code that defines your stack goes here

        self.vpc = ec2.Vpc(
            self,
            "VPC",
            vpc_name="datacenter",
            max_azs=3,
            ip_addresses=ec2.IpAddresses.cidr(cidr),
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

        customer_gateway_public_ip = ec2.CfnEIP(self, "CustomerGatewayElasticIpv4")
        self.customer_gateway_public_ip = customer_gateway_public_ip.attr_public_ip
        self.customer_gateway_public_ip_allocation_id = (
            customer_gateway_public_ip.attr_allocation_id
        )
        CfnOutput(self, "VPCId", value=self.vpc.vpc_id)


class DatacenterCustomerGatewayStack(Stack):
    def __init__(
        self, scope: Construct, id: str, vpc: ec2.Vpc, eip_allocation: str, **kwargs
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.customer_gateway = CustomerGateway(
            self,
            "CustomerGateway",
            vpc=vpc,
            public_subnet=vpc.public_subnets[0],
            eip_allocation=eip_allocation,
        )
