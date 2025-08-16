from enum import Enum
from constructs import Construct
from .ec2 import Instance
import aws_cdk.aws_ec2 as ec2


class Ubuntu(Enum):
    ARM = "ami-0fd8fe5cdf7cad6f62"
    X86 = "ami-02003f9f0fde924ea"


USER_DATA = """
#!/usr/bin/bash
sudo apt update
sudo apt -y upgrade
sudo shutdown -r now
"""


class CustomerGateway(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        vpc: ec2.Vpc,
        public_subnet: ec2.ISubnet,
    ):
        super().__init__(scope, id)
        self.gateway = Instance(
            self,
            "CustomerGateway",
            name="customer-gateway",
            vpc=vpc,
            subnet=public_subnet,
            instance_type="m7a.xlarge",
            ami_id=Ubuntu.X86.value,
            allow_packet_forwarding=True,
            user_data=USER_DATA,
        )
        self.gateway.allow_ssh_from_local()
