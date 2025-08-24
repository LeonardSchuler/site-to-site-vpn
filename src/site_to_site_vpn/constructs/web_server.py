from constructs import Construct
from .ec2 import Instance
import aws_cdk.aws_ec2 as ec2
from .constants import Ubuntu


USER_DATA = """#!/usr/bin/bash
sudo apt update
sudo apt -y upgrade

# Install Apache if not already installed
sudo apt -y install apache2

# Start and enable Apache
sudo systemctl start apache2
sudo systemctl enable apache2
"""


class WebServer(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        vpc: ec2.IVpc,
        subnet: ec2.ISubnet,
        access_from_cidr: str,
    ):
        super().__init__(scope, id)
        self.instance = Instance(
            self,
            "WebServer",
            name="web-server",
            vpc=vpc,
            subnet=subnet,
            instance_type="m7a.xlarge",
            ami_id=Ubuntu.X86.value,
            user_data=USER_DATA,
        )
        # TODO: add option to provide port as arg
        self.instance.security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(access_from_cidr),
            connection=ec2.Port.tcp(80),  # default port of apache httpd
        )
        self.instance.allow_ssh_from_local()
        self.instance.allow_ping_from(access_from_cidr)
