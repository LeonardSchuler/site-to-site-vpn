from aws_cdk import CfnOutput, Stack
import aws_cdk.aws_ec2 as ec2
from constructs import Construct

from ..constructs.ec2 import Instance
from ..constructs.customer_gateway import CustomerGateway
from ..constructs.constants import Ubuntu


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
        self,
        scope: Construct,
        id: str,
        dc_vpc: ec2.Vpc,
        cgw_eip_allocation_id: str,
        vpgw_tun1_public_ip: str,
        tun1_pre_shared_key: str,
        cgw_tun1_link_local_ip: str,
        vpgw_tun1_link_local_ip: str,
        vpc_cidr: str,
        dc_cidr: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.customer_gateway = CustomerGateway(
            self,
            "CustomerGateway",
            dc_vpc=dc_vpc,
            dc_public_subnet=dc_vpc.public_subnets[0],
            cgw_eip_allocation_id=cgw_eip_allocation_id,
            vpgw_tun1_public_ip=vpgw_tun1_public_ip,
            tun1_pre_shared_key=tun1_pre_shared_key,
            cgw_tun1_link_local_inner_ip=cgw_tun1_link_local_ip,
            vpgw_tun1_link_local_inner_ip=vpgw_tun1_link_local_ip,
            vpc_cidr=vpc_cidr,
            dc_cidr=dc_cidr,
        )

        all_subnets = (
            dc_vpc.select_subnets(subnet_type=ec2.SubnetType.PUBLIC).subnets
            + dc_vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED).subnets
            + dc_vpc.select_subnets(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ).subnets
        )
        for subnet in all_subnets:
            ec2.CfnRoute(
                self,
                f"{subnet.node.id}CgwRoute",
                route_table_id=subnet.route_table.route_table_id,
                destination_cidr_block=vpc_cidr,
                instance_id=self.customer_gateway.instance.instance_id,
            )


class DatacenterClient(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        dc_vpc: ec2.Vpc,
        dc_subnet: ec2.ISubnet,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.client = Instance(
            self,
            "Client",
            name="dc-client",
            vpc=dc_vpc,
            subnet=dc_subnet,
            instance_type="m7a.large",
            ami_id=Ubuntu.X86.value,
        )
        self.client.allow_ssh_from_local()

        # TODO: remove
        self.client.allow_ping_from("10.0.0.0/8")
