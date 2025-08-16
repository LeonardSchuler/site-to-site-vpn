#!/usr/bin/env python3

from aws_cdk import App

from site_to_site_vpn.stacks.datacenter import (
    DatacenterVPCStack,
    DatacenterCustomerGatewayStack,
)


app = App()

dc_vpc_stack = DatacenterVPCStack(app, "dc-vpc")
dc_gw_stack = DatacenterCustomerGatewayStack(app, "dc-gw", vpc=dc_vpc_stack.vpc)


app.synth()
