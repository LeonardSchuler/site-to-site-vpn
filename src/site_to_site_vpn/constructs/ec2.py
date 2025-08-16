from aws_cdk import CfnOutput, CfnTag
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_iam as iam
from constructs import Construct
import base64


class Instance(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        name: str,
        vpc: ec2.Vpc,
        subnet: ec2.ISubnet,
        instance_type: str,
        ami_id: str,
        user_data: str = "",
        ssh_key_name: str | None = None,
        allow_packet_forwarding: bool = False,
    ):
        super().__init__(scope, id)
        self.instance_name = name
        self.vpc = vpc
        self.subnet = subnet
        self.subnet_id = subnet.subnet_id
        role_name = f"{self.instance_name}-role"
        self.role = iam.Role(
            self,
            "Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),  # type: ignore
            role_name=role_name,
        )
        self.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonSSMManagedInstanceCore"
            )
        )
        instance_profile = iam.InstanceProfile(
            self,
            "InstanceProfile",
            role=self.role,  # type: ignore
        )
        self.security_group = ec2.SecurityGroup(
            self,
            "SecurityGroup",
            vpc=vpc,
            allow_all_outbound=True,
            security_group_name="sg",
        )
        self.cfn_instance = ec2.CfnInstance(
            self,
            "Instance",
            block_device_mappings=[
                ec2.CfnInstance.BlockDeviceMappingProperty(
                    device_name="/dev/sda1",
                    ebs=ec2.CfnInstance.EbsProperty(
                        delete_on_termination=True,
                        encrypted=False,
                        volume_size=50,
                        volume_type="gp3",
                    ),
                )
            ],
            disable_api_termination=False,
            iam_instance_profile=instance_profile.instance_profile_name,
            image_id=ami_id,
            instance_type=instance_type,
            key_name=ssh_key_name,
            metadata_options=ec2.CfnInstance.MetadataOptionsProperty(
                http_endpoint="enabled",
                http_put_response_hop_limit=1,
                http_tokens="required",
                instance_metadata_tags="enabled",
            ),
            propagate_tags_to_volume_on_creation=True,
            security_group_ids=[self.security_group.security_group_id],
            source_dest_check=not allow_packet_forwarding,
            subnet_id=self.subnet_id,
            tags=[CfnTag(key="Name", value=self.instance_name)],
            user_data=base64.b64encode(user_data.encode("utf-8")).decode("utf-8"),
        )
        self.instance_id = self.cfn_instance.get_att("InstanceId")
        self.private_ip = self.cfn_instance.get_att("PrivateIp")
        self.public_ip = self.cfn_instance.get_att("PublicIp")
        self.private_dns_name = self.cfn_instance.get_att("PrivateDnsName")
        self.public_dns_name = self.cfn_instance.get_att("PublicDnsName")
        CfnOutput(self, "InstanceId", value=self.instance_id.to_string())
        CfnOutput(self, "PrivateIp", value=self.private_ip.to_string())
        CfnOutput(
            self,
            "PrivateDns",
            value=self.private_dns_name.to_string(),
        )
        CfnOutput(self, "PublicIp", value=self.public_ip.to_string())
        CfnOutput(
            self,
            "PublicDns",
            value=self.public_dns_name.to_string(),
        )

    def add_admin_permission(self):
        self.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )

    def allow_ssh_from_local(self):
        from pathlib import Path

        ssh_dir = Path.home() / ".ssh"

        pub_files = list(ssh_dir.glob("*.pub"))

        public_key = pub_files[0].read_text().strip()

        kp = ec2.KeyPair(self, "KeyPair", public_key_material=public_key)
        self.cfn_instance.key_name = kp.key_pair_name

        import urllib.request

        with urllib.request.urlopen("https://checkip.amazonaws.com") as response:
            your_public_ip = response.read().decode("utf-8").strip()
        self.security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(f"{your_public_ip}/32"),
            connection=ec2.Port.tcp(22),
            description="Allow SSH from my IP",
        )
