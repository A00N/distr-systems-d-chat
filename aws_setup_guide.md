# AWS EC2 Setup Guide for D-Chat

This guide shows how to set up three EC2 instances (1 coordinator + 2 worker servers) and run the starter D-Chat servers.
Use the Ubuntu 24.04 / Amazon Linux images. The guide assumes you have an AWS account and basic familiarity with EC2.

## 1) Create EC2 instances
- Launch 3 EC2 instances (t3.micro or t2.micro).
- SSH key pair: create/download and keep safe.
- Security group inbound rules:
  - SSH (TCP 22) from your IP
  - App ports (TCP) open between instances and from your client IP: 9000-9010 (or specific ports you choose)
  - For demo on public internet, allow your IP for client port only. Prefer using EC2 private IPs for server-to-server communication.

## 2) Instance setup (run on each instance)
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git
git clone https://github.com/YOUR_REPO/dchat.git
cd dchat
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## 3) Configure servers
Edit `server/config_coordinator.json` and `server/config_worker_N.json` before starting.
- Coordinator: use coordinator's private IP and chosen port (e.g., 9000)
- Worker: set `--coordinator <coordinator_private_ip>:9000` and list any peers

## 4) Start servers (systemd recommended)
Example using `tmux` or `screen`:
```bash
source venv/bin/activate
python3 server/main.py --mode coordinator --host 0.0.0.0 --port 9000 --config server/config_coordinator.json
```
For worker:
```bash
python3 server/main.py --mode worker --host 0.0.0.0 --port 9001 --coordinator <coord-ip>:9000 --peers <peer1-ip>:9002,<peer2-ip>:9003
```

### Optional: systemd unit (coordinator.service)
```
[Unit]
Description=DChat Coordinator
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/dchat
ExecStart=/home/ubuntu/dchat/venv/bin/python3 server/main.py --mode coordinator --host 0.0.0.0 --port 9000 --config server/config_coordinator.json
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable + start:
```bash
sudo cp coordinator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now coordinator.service
```

## 5) Notes & security
- Use private IPs for server-to-server traffic inside the same VPC.
- Do not open ports 9000-9010 to the whole internet; restrict to your IP or VPC.
- Monitor instance CPU and network; t3.micro can handle a small prototype, but not heavy load.

## 6) Troubleshooting
- Ensure security groups allow inbound/outbound traffic for the ports you use.
- Check logs printed to stdout or configure logging to files in `server/state_manager.py`.

---
