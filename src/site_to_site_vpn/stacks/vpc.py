from aws_cdk import Stack
import aws_cdk.aws_ec2 as ec2
from constructs import Construct
from ..constructs.web_server import WebServer
from ..constructs.vpn_connection import VpnConnection


class VpcStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        cidr: str,
        datacenter_cidr: str,
        customer_gateway_public_ip: str,
        tun1_pre_shared_key: str,
        tun1_inner_cidr: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)
        # tun1_pre_shared_key: Allowed characters are alphanumeric characters period . and underscores _. Must be between 8 and 64 characters in length and cannot start with zero (0).

        # The code that defines your stack goes here

        self.vpc = ec2.Vpc(
            self,
            "VPC",
            vpc_name="webservers-vpc",
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
            nat_gateways=2,
        )
        self.vpc.add_gateway_endpoint(
            "S3Endpoint", service=ec2.GatewayVpcEndpointAwsService.S3
        )
        self.vpc.add_gateway_endpoint(
            "DynamoDbEndpoint", service=ec2.GatewayVpcEndpointAwsService.DYNAMODB
        )

        self.vpn_connection = VpnConnection(
            self,
            "VpnConnection",
            vpc=self.vpc,
            datacenter_cidr=datacenter_cidr,
            customer_gateway_public_ip=customer_gateway_public_ip,
            tun1_pre_shared_key=tun1_pre_shared_key,
            tun1_inner_cidr=tun1_inner_cidr,
        )
        self.vpn_connection.add_routes_to_vpgw()


class WebServerStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        vpc: ec2.IVpc,
        subnet: ec2.ISubnet,
        access_from_cidr: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)
        self.web_server = WebServer(
            self,
            "webserver",
            vpc=vpc,
            subnet=subnet,
            access_from_cidr=access_from_cidr,
        )
