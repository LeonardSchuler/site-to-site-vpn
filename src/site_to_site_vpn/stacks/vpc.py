from aws_cdk import CfnOutput, Stack
import aws_cdk.aws_ec2 as ec2
from constructs import Construct
from ..constructs.ec2 import Instance


class VpcStack(Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        cidr: str,
        datacenter_cidr: str,
        customer_gateway_public_ip: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

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

        # use this instead of add_vpn_connection for dynamic routing via bgp
        # vpc.enable_vpn_gateway(
        #    vpn_route_propagation=[
        #        ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        #        ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        #        ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
        #    ],
        #    type="ipsec.1",
        # )
        vpn_connection = self.vpc.add_vpn_connection(
            "Site2SiteVPN",
            ip=customer_gateway_public_ip,
            static_routes=[datacenter_cidr],
        )

        all_subnets = (
            self.vpc.select_subnets(subnet_type=ec2.SubnetType.PUBLIC).subnets
            + self.vpc.select_subnets(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ).subnets
            + self.vpc.select_subnets(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ).subnets
        )
        for subnet in all_subnets:
            route = ec2.CfnRoute(
                self,
                f"{subnet.node.id}DcRoute",
                route_table_id=subnet.route_table.route_table_id,
                destination_cidr_block=datacenter_cidr,
                gateway_id=self.vpc.vpn_gateway_id,
            )
            route.add_dependency(vpn_connection.node.default_child)  # type: ignore

        CfnOutput(self, "VPCId", value=self.vpc.vpc_id)


# class WebServerStack(Stack):
#    def __init__(
#        self,
#        scope: Construct,
#        id: str,
#        *,
#        vpc: ec2.IVpc,
#        subnet: ec2.ISubnet,
#        **kwargs,
#    ) -> None:
#        super().__init__(scope, id, **kwargs)
#        self.web_server = Instance(
#            self, "WebServer", name="webserver", vpc=vpc, subnet=subnet, instance_type="m7a.large",
#        )
