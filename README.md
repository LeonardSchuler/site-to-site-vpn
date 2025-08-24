# Site-to-Site VPN with AWS CDK & StrongSwan

This project provisions a **site-to-site VPN** between an on-premises-like datacenter VPC and an AWS infrastructure VPC using **AWS CDK** and **StrongSwan**.

It automates the setup of:
- A **Datacenter VPC** with a **Customer Gateway (CGW)** running StrongSwan.
- An **AWS Infrastructure VPC** with a **Virtual Private Gateway (VPGW)** and VPN connection.
- A **Datacenter Client EC2** instance to simulate on-prem workloads.
- An **Infrastructure Web Server EC2** instance accessible from the datacenter via the VPN.

---

## Prerequisites
- [AWS CDK](https://docs.aws.amazon.com/cdk/) v2
- Python **3.13** (managed via uv and `.python-version`)
- AWS credentials configured (`aws configure`)
- SSH public key available in `~/.ssh/*.pub`. This will be used to configure SSH access to all deployed instances.

---

## Setup

### 1. Clone & install dependencies
```bash
# Clone this repo
cd site-to-site-vpn

# Install dependencies with uv
uv sync
```

### 2. Generate Pre-Shared Key (PSK)
The VPN tunnel requires a **pre-shared key (PSK)**. Generate it with:
```bash
make .env
```
This creates a `.env` file containing:
```env
TUN1_PRE_SHARED_KEY="<randomly-generated-psk>"
```

⚠️ Requirements:
- 8–64 characters
- Allowed chars: `A–Z a–z 1–9 . _`
- Cannot start with `0`

### 3. Deploy all stacks
```bash
cdk deploy --all --require-approval never
```

This provisions:
- `dc-vpc` → Datacenter VPC + EIP for CGW
- `infra-vpc` → Infrastructure VPC + VPN connection
- `dc-gw` → Customer Gateway EC2 (StrongSwan)
- `dc-client` → Client EC2 inside Datacenter
- `infra-server` → Web Server inside Infra VPC

---

## Verification
Once deployment finishes, you can verify:

1. **Check EC2 outputs** (from `cdk deploy` logs):
   - `dc-client.ClientPublicIp` → SSH into datacenter client
   - `infra-server.webserverWebServerPublicIp` → Access web server

2. **SSH into Datacenter Client**:
```bash
ssh ubuntu@<dc-client-public-ip>
```

3. **Ping Web Server over VPN**:
```bash
ping 10.1.0.98   # Private IP of infra web server
```

4. **Access Web Server via private network**:
```bash
curl http://10.1.0.98
```
Should return the default Apache page.

---

## Manual StrongSwan Setup (for reference)
This section details how the repository configures StrongSwan.

### Automatic Setup
See customer gateway construct in the repo [customer_gateway.py](src/site_to_site_vpn/constructs/customer_gateway.py)

### Manual Setup
Example IP addressing scheme:
```
Datacenter CIDR:      10.0.0.0/16
Infra VPC CIDR:       10.1.0.0/16
Customer Gateway IP:  18.192.30.10 & 10.0.0.110 # check values in output from cdk deploy
Tunnel 1 VPGW IP:     3.79.132.236 # check value in output from cdk deploy
Link-local subnet:    169.254.88.80/30
  - VPGW: 169.254.88.81
  - CGW:  169.254.88.82
```

Connect via `ssh ubuntu@18.192.30.10` with the customer gateway, and run the following commands:
```bash
sudo apt update && sudo apt install -y strongswan-starter

# Configure PSK
sudo echo '18.192.30.10 3.79.132.236 : PSK "<psk>"' >> /etc/ipsec.secrets

# Create tunnel interface
sudo ip link add Tunnel1 type vti local 10.0.0.110 remote 3.79.132.236 key 100
sudo ip addr add 169.254.88.82/30 remote 169.254.88.81/30 dev Tunnel1
sudo ip link set Tunnel1 up mtu 1419
sudo ip route add 10.1.0.0/16 dev Tunnel1 metric 100


```
Configure `/etc/ipsec.conf`
```
config setup
        charondebug="all"
        uniqueids=yes
        strictcrlpolicy=no

conn Tunnel1
        type=tunnel
        auto=start
        keyexchange=ikev2
        authby=psk
        leftid=10.0.0.110
        leftsubnet=10.0.0.0/16
        right=3.79.132.236
        rightsubnet=10.1.0.0/16
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
        mark=100
```
Configure `/etc/sysctl.conf`

```
net.ipv4.ip_forward=1
net.ipv4.conf.Tunnel1.rp_filter=2 #This value allows the Linux kernel to handle asymmetric routing
net.ipv4.conf.Tunnel1.disable_policy=1 #This value disables IPsec policy (SPD) for the interface
net.ipv4.conf.enp39s0.disable_xfrm=1 #This value disables crypto transformations on the physical interface
net.ipv4.conf.enp39s0.disable_policy=1 #This value disables IPsec policy (SPD) for the interface
```
and reload the kernel
```
sudo sysctl -p
```

---

## Cleanup
To remove all resources:
```bash
cdk destroy --all
```

---

## Project Structure
```
├── app.py                     # CDK entrypoint
├── Makefile                   # Helper to generate .env with PSK
├── pyproject.toml             # Python project setup
├── src/site_to_site_vpn/
│   ├── stacks/                # CDK stacks (vpc, datacenter, client, gw)
│   └── constructs/            # Reusable CDK constructs (EC2, VPN, WebServer)
```

---

## License
[MIT License](./LICENSE)