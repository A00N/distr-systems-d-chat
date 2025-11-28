import os
from dataclasses import dataclass
from typing import List, Protocol

try:
    import boto3  # needed in AWS mode
except ImportError:
    boto3 = None


@dataclass
class PeerInfo:
    host: str
    raft_port: int

    def as_endpoint(self) -> str:
        return f"{self.host}:{self.raft_port}"


class PeerProvider(Protocol):
    def peers(self) -> List[str]:
        """
        Return RAFT peer endpoints as a list of 'host:port' strings.
        Must NOT include this node itself.
        """
        ...


class StaticPeerProvider:
    """
    Local/dev mode: peers are passed in as host:port strings
    """

    def __init__(self, peers: List[str]):
        self._peers = [p.strip() for p in peers if p.strip()]

    def peers(self) -> List[str]:
        return list(self._peers)


class AwsEc2TagPeerProvider:
    """
    AWS EC2 mode:
    - Instances are discovered by tag DCHAT_CLUSTER=<cluster_name>.
    - Each instance's PrivateIpAddress is used with a common RAFT_PORT env var.
    - This node's own private IP is excluded from the list of peers.
    """

    def __init__(self, cluster_name: str, this_private_ip: str, raft_port: int, region: str):
        if boto3 is None:
            raise RuntimeError("boto3 is required for AwsEc2TagPeerProvider but is not installed")

        self.cluster_name = cluster_name
        self.this_private_ip = this_private_ip
        self.raft_port = raft_port
        self.region = region
        self._ec2 = boto3.client("ec2", region_name=region)

    def peers(self) -> List[str]:
        filters = [
            {"Name": "tag:DCHAT_CLUSTER", "Values": [self.cluster_name]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]

        resp = self._ec2.describe_instances(Filters=filters)
        endpoints: List[str] = []

        for reservation in resp.get("Reservations", []):
            for inst in reservation.get("Instances", []):
                ip = inst.get("PrivateIpAddress")

                if not ip:
                    continue
                if ip == self.this_private_ip:
                    continue

                endpoints.append(f"{ip}:{self.raft_port}")

        return endpoints


def build_peer_provider_from_env(static_peers: List[str]) -> PeerProvider:
    """
    - If DCHAT_DISCOVERY_MODE=aws-ec2, use AwsEc2TagPeerProvider.
    - Otherwise, use StaticPeerProvider with the provided static_peers.
    """

    mode = os.environ.get("DCHAT_DISCOVERY_MODE", "static").lower()

    if mode == "aws-ec2":
        cluster_name = os.environ.get("DCHAT_CLUSTER_NAME")
        private_ip = os.environ.get("DCHAT_PRIVATE_IP")
        region = os.environ.get("AWS_REGION", "eu-north-1")
        raft_port_s = os.environ.get("DCHAT_RAFT_PORT")

        if not (cluster_name and private_ip and raft_port_s):
            raise RuntimeError(
                "DCHAT_DISCOVERY_MODE=aws-ec2 requires DCHAT_CLUSTER_NAME, "
                "DCHAT_PRIVATE_IP, and DCHAT_RAFT_PORT env vars."
            )

        raft_port = int(raft_port_s)

        return AwsEc2TagPeerProvider(
            cluster_name=cluster_name,
            this_private_ip=private_ip,
            raft_port=raft_port,
            region=region,
        )

    return StaticPeerProvider(static_peers)
