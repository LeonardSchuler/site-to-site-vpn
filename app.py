#!/usr/bin/env python3
from dotenv import load_dotenv


import os

from aws_cdk import App

from site_to_site_vpn.stacks.datacenter import (
    DatacenterVPCStack,
    DatacenterCustomerGatewayStack,
    DatacenterClient,
)

from site_to_site_vpn.stacks.vpc import VpcStack, WebServerStack

load_dotenv()

app = App()


DC_CIDR = "10.0.0.0/16"
VPC_CIDR = "10.1.0.0/16"
TUN1_LINK_LOCAL_INNER_CIDR = "169.254.88.80/30"

# tun1_pre_shared_key: Allowed characters are alphanumeric characters period . and underscores _. Must be between 8 and 64 characters in length and cannot start with zero (0).
try:
    TUN1_PRE_SHARED_KEY = os.environ["TUN1_PRE_SHARED_KEY"]
except KeyError as e:
    print("Provide a .env with a TUN1_PRE_SHARED_KEY value")
    raise e

dc_network_stack = DatacenterVPCStack(app, "dc-vpc", cidr=DC_CIDR)


vpc_stack = VpcStack(
    app,
    "infra-vpc",
    cidr=VPC_CIDR,
    datacenter_cidr=DC_CIDR,
    customer_gateway_public_ip=dc_network_stack.customer_gateway_public_ip,
    tun1_pre_shared_key=TUN1_PRE_SHARED_KEY,
    tun1_inner_cidr=TUN1_LINK_LOCAL_INNER_CIDR,
)


dc_ip_tunnel_gw_stack = DatacenterCustomerGatewayStack(
    app,
    "dc-gw",
    dc_vpc=dc_network_stack.vpc,
    cgw_eip_allocation_id=dc_network_stack.customer_gateway_public_ip_allocation_id,
    vpc_cidr=VPC_CIDR,
    vpgw_tun1_public_ip=vpc_stack.vpn_connection.vpgw_tun1_public_ip,
    tun1_pre_shared_key=TUN1_PRE_SHARED_KEY,
    cgw_tun1_link_local_ip=vpc_stack.vpn_connection.cgw_tun1_link_local_ip,
    vpgw_tun1_link_local_ip=vpc_stack.vpn_connection.vpgw_tun1_link_local_ip,
    dc_cidr=DC_CIDR,
)
dc_ip_tunnel_gw_stack.add_dependency(dc_network_stack)
dc_ip_tunnel_gw_stack.add_dependency(vpc_stack)

DatacenterClient(
    app,
    "dc-client",
    dc_vpc=dc_network_stack.vpc,
    dc_subnet=dc_network_stack.vpc.public_subnets[0],
)

WebServerStack(
    app,
    "infra-server",
    vpc=vpc_stack.vpc,
    subnet=vpc_stack.vpc.public_subnets[0],
    access_from_cidr=DC_CIDR,
)

app.synth()
