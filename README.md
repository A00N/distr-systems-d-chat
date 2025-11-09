# D-Chat — Distributed Chat System (Starter)

**Team:** Nooa Saareks, Atte Högman, Joona Kettunen

This repository contains a starter implementation for the D-Chat project (Distributed Chat).
It uses Python 3.11+, asyncio for networking, and a simple Tkinter GUI client.

**Structure**
```
dchat/
├── README.md
├── aws_setup_guide.md
├── requirements.txt
├── server/
│   ├── main.py
│   ├── message_protocol.py
│   ├── node_manager.py
│   ├── state_manager.py
│   └── utils.py
└── client/
    ├── main.py
    ├── ui.py
    ├── message_handler.py
    └── utils.py
```

Quick start (local testing)
1. Create a virtualenv: `python3 -m venv venv && source venv/bin/activate`
2. Install requirements: `pip install -r requirements.txt`
3. Start coordinator server:
   `python3 server/main.py --mode coordinator --host 0.0.0.0 --port 9000 --config server/config_coordinator.json`
4. Start a worker server (different terminal or host):
   `python3 server/main.py --mode worker --host 0.0.0.0 --port 9001 --coordinator 127.0.0.1:9000 --peers 127.0.0.1:9002`
5. Start the GUI client:
   `python3 client/main.py --host 127.0.0.1 --port 9001 --user alice`

Local testing - alternative way:
1. Run `python3 server/test_server.py --host 127.0.0.1 --port 9001` in Terminal 1
2. Run `python3 client/main.py --host 127.0.0.1 --port 9001 --user alice` in Terminal 2
3. Run `python3 client/main.py --host 127.0.0.1 --port 9001 --user bob` in Terminal 3

See `aws_setup_guide.md` for EC2 deployment instructions and `server`/`client` code comments for details.

## System Architecture Diagram

```mermaid
graph TD
    A[Client Devices<br/>Python clients]
    B[Application Load Balancer<br/>AWS ALB]

    A --> B

    subgraph AWS["AWS Cloud (VPC)"]
        B -->|HTTP :80 / :443| C[Target Group<br/>Port 5000]

        subgraph ASG["Auto Scaling Group (3-4EC2s)"]
            C --> E1[EC2 Instance 1<br/>Docker Container]
            C --> E2[EC2 Instance 2<br/>Docker Container<br/>Current Leader]
            C --> E3[EC2 Instance 3<br/>Docker Container]
            C --> E4[EC2 Instance 4<br/>Docker Container]
        end

        E1 <-.-> E2
        E1 <-.-> E3
        E1 <-.-> E4

        E2 <-.-> E3
        E2 <-.-> E4

        E3 <-.-> E4
    end

    subgraph Storage["Optional Shared Storage"]
        S[(S3 Bucket / DynamoDB)]
    end

    E2 <-->|Sync logs / snapshots| S

    classDef serviceBox fill:#e0f2fe,stroke:#0ea5e9,stroke-width:2px
    classDef computeBox fill:#e2eda1,stroke:#b3bf6d,stroke-width:2px
    classDef clientBox fill:#ede9fe,stroke:#8b5cf6,stroke-width:2px
    classDef dataBox fill:#ccfbf1,stroke:#14b8a6,stroke-width:2px

    classDef containerBox fill:#e6e6e6,stroke:#121212,stroke-width:2px
    classDef autoBox fill:#dadae0,stroke:#aca9cc,stroke-width:2px

    class A clientBox
    class B,C serviceBox
    class E1,E2,E3,E4 computeBox
    class S dataBox
    class AWS containerBox
    class ASG autoBox
```
