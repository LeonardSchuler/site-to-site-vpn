import ipaddress
import aws_cdk.aws_ec2 as ec2
import aws_cdk.custom_resources as cr
from aws_cdk import aws_ssm as ssm
from aws_cdk import CfnOutput, SecretValue
from constructs import Construct


class VpnConnection(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        vpc: ec2.IVpc,
        datacenter_cidr: str,
        customer_gateway_public_ip: str,
        tun1_pre_shared_key: str,
        tun1_inner_cidr: str,
    ):
        super().__init__(scope, id)
        self.vpc = vpc
        self.datacenter_cidr = datacenter_cidr
        self.tun1_inner_cidr = tun1_inner_cidr
        self.vpgw_tun1_link_local_ip, self.cgw_tun1_link_local_ip = self._get_hosts(
            self.tun1_inner_cidr
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

        tun1_secret = SecretValue.unsafe_plain_text(tun1_pre_shared_key)
        tun1 = ec2.VpnTunnelOption(
            pre_shared_key_secret=tun1_secret, tunnel_inside_cidr=self.tun1_inner_cidr
        )
        self._vpn_connection = self.vpc.add_vpn_connection(
            "Site2SiteVPN",
            ip=customer_gateway_public_ip,
            static_routes=[self.datacenter_cidr],
            tunnel_options=[tun1],
        )

        # Custom resource to fetch tunnel IPs
        provider = cr.AwsCustomResource(
            self,
            "FetchVpnTunnels",
            on_create=cr.AwsSdkCall(
                service="EC2",
                action="describeVpnConnections",
                parameters={
                    "VpnConnectionIds": [self._vpn_connection.vpn_id],
                },
                physical_resource_id=cr.PhysicalResourceId.of("FetchVpnTunnels"),
                output_paths=[
                    "VpnConnections.0.Options.TunnelOptions.0.OutsideIpAddress",
                    "VpnConnections.0.Options.TunnelOptions.1.OutsideIpAddress",
                    "VpnConnections.0.Options.TunnelOptions.0.TunnelInsideCidr",
                    "VpnConnections.0.Options.TunnelOptions.1.TunnelInsideCidr",
                ],
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            ),
            install_latest_aws_sdk=False,
        )

        # Now you can grab the tunnel IPs directly
        self.vpgw_tun1_public_ip = provider.get_response_field(
            "VpnConnections.0.Options.TunnelOptions.0.OutsideIpAddress"
        )
        self.vpgw_tun2_public_ip = provider.get_response_field(
            "VpnConnections.0.Options.TunnelOptions.1.OutsideIpAddress"
        )
        # Tunnel inside CIDRs (link-local /30 ranges)
        self.vpgw_tun1_link_local_inner_ip = provider.get_response_field(
            "VpnConnections.0.Options.TunnelOptions.0.TunnelInsideCidr"
        )
        self.vpgw_tun2_link_local_inner_ip = provider.get_response_field(
            "VpnConnections.0.Options.TunnelOptions.1.TunnelInsideCidr"
        )

        CfnOutput(self, "VpgwTun1PublicIp", value=self.vpgw_tun1_public_ip)
        CfnOutput(self, "VpgwTun2PublicIp", value=self.vpgw_tun2_public_ip)

        CfnOutput(
            self, "VpgwTun1LinkLocalInnerIp", value=self.vpgw_tun1_link_local_inner_ip
        )
        CfnOutput(
            self, "VpgwTun2LinkLocalInnerIp", value=self.vpgw_tun2_link_local_inner_ip
        )

        # Publish to SSM so EC2/UserData can fetch them at runtime
        ssm.StringParameter(
            self,
            "VpgwTun1PublicIpParam",
            parameter_name="/vpn/vpgw/tunnel1/public_ip",
            string_value=self.vpgw_tun1_public_ip,
        )

        ssm.StringParameter(
            self,
            "VpgwTun2PublicIpParam",
            parameter_name="/vpn/vpgw/tunnel2/public_ip",
            string_value=self.vpgw_tun2_public_ip,
        )

    def add_routes_to_vpgw(self):
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
                destination_cidr_block=self.datacenter_cidr,
                gateway_id=self.vpc.vpn_gateway_id,
            )
            route.add_dependency(self._vpn_connection.node.default_child)  # type: ignore

    @staticmethod
    def _get_hosts(cidr) -> list[str]:
        network = ipaddress.ip_network(cidr)
        if not isinstance(network, ipaddress.IPv4Network):
            raise ValueError(f"Only IPv4 networks are supported, got {network}")
        hosts = [str(h) for h in network.hosts()]
        return hosts
