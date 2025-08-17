#!/usr/bin/env python3

from aws_cdk import App

from site_to_site_vpn.stacks.datacenter import (
    DatacenterVPCStack,
    DatacenterCustomerGatewayStack,
)

from site_to_site_vpn.stacks.vpc import VpcStack


app = App()

DC_CIDR = "10.0.0.0/16"
VPC_CIDR = "10.1.0.0/16"

dc_network_stack = DatacenterVPCStack(app, "dc-vpc", cidr=DC_CIDR)


vpc_stack = VpcStack(
    app,
    "webserver-vpc",
    cidr=VPC_CIDR,
    datacenter_cidr=DC_CIDR,
    customer_gateway_public_ip=dc_network_stack.customer_gateway_public_ip,
)


# TODO: dependency on vpc_stack for user data relevant information
dc_ip_tunnel_gw_stack = DatacenterCustomerGatewayStack(
    app,
    "dc-gw",
    vpc=dc_network_stack.vpc,
    eip_allocation=dc_network_stack.customer_gateway_public_ip_allocation_id,
)

app.synth()
