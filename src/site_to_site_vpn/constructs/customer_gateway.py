from constructs import Construct
from .ec2 import Instance
from .constants import Ubuntu
import aws_cdk.aws_ec2 as ec2


USER_DATA = """#!/usr/bin/bash
sudo apt update
sudo apt -y upgrade
sudo apt install -y strongswan-starter
sudo snap install aws-cli --classic

# Fetch CGW private IP from IMDSv2
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")

AWS_DEFAULT_REGION=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r '.region')
CGW_TUN1_PRIVATE_IP=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/local-ipv4)
CGW_TUN1_PUBLIC_IP=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/public-ipv4)


VPGW_TUN1_PUBLIC_IP=$(aws ssm get-parameter --name /vpn/vpgw/tunnel1/public_ip --query "Parameter.Value" --output text --region $AWS_DEFAULT_REGION)
VPGW_TUN2_PUBLIC_IP=$(aws ssm get-parameter --name /vpn/vpgw/tunnel2/public_ip --query "Parameter.Value" --output text --region $AWS_DEFAULT_REGION)



sudo sed -i 's/# install_routes = yes/install_routes = no/' /etc/strongswan.d/charon.conf

sudo echo "$CGW_TUN1_PUBLIC_IP $VPGW_TUN1_PUBLIC_IP : PSK \"{tun1_pre_shared_key}\"" >> /etc/ipsec.secrets
sudo ip link add Tunnel1 type vti local $CGW_TUN1_PRIVATE_IP remote $VPGW_TUN1_PUBLIC_IP key 100
sudo ip addr add {cgw_tun1_link_local_inner_ip}/30 remote {vpgw_tun1_link_local_inner_ip}/30 dev Tunnel1
sudo ip link set Tunnel1 up mtu 1419
sudo ip route add {vpc_cidr} dev Tunnel1 metric 100


cat << EOF > /etc/ipsec.conf
config setup
        charondebug="all"
        uniqueids=yes
        strictcrlpolicy=no

conn Tunnel1
        type=tunnel
        auto=start
        keyexchange=ikev2
        authby=psk
        leftid=$CGW_TUN1_PRIVATE_IP
        leftsubnet={dc_cidr}
        right=$VPGW_TUN1_PUBLIC_IP
        rightsubnet={vpc_cidr}
        aggressive=no
        ikelifetime=28800s
        lifetime=3600s
        margintime=270s
        rekey=yes
        rekeyfuzz=100%
        fragmentation=yes
        replay_window=1024
        dpddelay=30s
        dpdtimeout=120s
        dpdaction=restart
        ike=aes128-sha1-modp1024
        esp=aes128-sha1
        keyingtries=%forever

        ## Please note the following line assumes you only have two tunnels in your Strongswan configuration file. This "mark" value must be unique and may need to be changed based on other entries in your configuration file.
        mark=100
EOF
sudo sed -i 's/        /\t/g' /etc/ipsec.conf



cat << EOF >> /etc/sysctl.conf

net.ipv4.ip_forward=1
net.ipv4.conf.Tunnel1.rp_filter=2 #This value allows the Linux kernel to handle asymmetric routing
net.ipv4.conf.Tunnel1.disable_policy=1 #This value disables IPsec policy (SPD) for the interface
net.ipv4.conf.enp39s0.disable_xfrm=1 #This value disables crypto transformations on the physical interface
net.ipv4.conf.enp39s0.disable_policy=1 #This value disables IPsec policy (SPD) for the interface
EOF
sudo sysctl -p


sudo ipsec restart
"""


class CustomerGateway(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        dc_vpc: ec2.Vpc,
        dc_public_subnet: ec2.ISubnet,
        cgw_eip_allocation_id: str,
        vpgw_tun1_public_ip: str,
        tun1_pre_shared_key: str,
        cgw_tun1_link_local_inner_ip: str,
        vpgw_tun1_link_local_inner_ip: str,
        vpc_cidr: str,
        dc_cidr: str,
    ):
        super().__init__(scope, id)
        formatted_user_data = USER_DATA.format(
            vpgw_tun1_public_ip=vpgw_tun1_public_ip,
            tun1_pre_shared_key=tun1_pre_shared_key,
            cgw_tun1_link_local_inner_ip=cgw_tun1_link_local_inner_ip,
            vpgw_tun1_link_local_inner_ip=vpgw_tun1_link_local_inner_ip,
            vpc_cidr=vpc_cidr,
            dc_cidr=dc_cidr,
        )
        self.instance = Instance(
            self,
            "CustomerGateway",
            name="customer-gateway",
            vpc=dc_vpc,
            subnet=dc_public_subnet,
            instance_type="m7a.xlarge",
            ami_id=Ubuntu.X86.value,
            allow_packet_forwarding=True,
            user_data=formatted_user_data,
        )
        self.instance.allow_ssh_from_local()
        self.instance.add_eip(eip_allocation=cgw_eip_allocation_id)
        self.instance.security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(dc_cidr), connection=ec2.Port.all_traffic()
        )
        # Note: CGW establishes a long-lived connection with the vpgw endpoint
        # on which other traffic is piggy-backing. I.e. vpgw tunnel endpoints does not
        # connect to the cgw, i.e. no further inbound route is required
