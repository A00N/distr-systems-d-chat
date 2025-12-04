#!/bin/bash
set -e

exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "Starting user-data script at $(date)"

sudo yum update -y

# Get instance metadata
echo "Fetching instance metadata..."

# Get IMDSv2 token
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")

INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/instance-id)

PRIVATE_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" \
  http://169.254.169.254/latest/meta-data/local-ipv4)

echo "Instance ID: ${INSTANCE_ID}"
echo "Private IP: ${PRIVATE_IP}"

echo "Logging into ECR..."

aws ecr get-login-password --region eu-north-1 | \
  docker login --username AWS --password-stdin 826087506501.dkr.ecr.eu-north-1.amazonaws.com


echo "Pulling the latest Docker image..."

docker pull 826087506501.dkr.ecr.eu-north-1.amazonaws.com/distributed/server:latest

if [ "$(docker ps -aq -f name=chat-node)" ]; then
    echo "Removing existing chat-node container..."
    docker stop chat-node || true
    docker rm chat-node || true
fi

echo "Starting chat-node container..."

docker run -d \
  --name chat-node \
  --restart unless-stopped \
  -p 5000:9000 \
  -p 6000:6000 \
  -e DCHAT_NODE_ID="${PRIVATE_IP}:6000" \
  -e DCHAT_PUBLIC_HOST="DChatALB-596522607.eu-north-1.elb.amazonaws.com" \
  -e DCHAT_PUBLIC_SCHEME="http" \
  -e DCHAT_DISCOVERY_MODE="aws-ec2" \
  -e DCHAT_CLUSTER_NAME="dchat-cluster" \
  -e DCHAT_RAFT_PORT=6000 \
  -e DCHAT_PRIVATE_IP="${PRIVATE_IP}" \
  -e DCHAT_RAFT_LOG_LEVEL="INFO" \
  -e AWS_REGION="eu-north-1" \
  -e AWS_DEFAULT_REGION="eu-north-1" \
  826087506501.dkr.ecr.eu-north-1.amazonaws.com/distributed/server:latest

echo "Verifying container status..."
docker ps -a | grep chat-node

echo "User-data script completed at $(date)"
