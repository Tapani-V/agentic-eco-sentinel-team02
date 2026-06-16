#!/bin/bash
# Create custom VPC, subnet, and security group for ECS
# Usage: bash scripts/create_agentic_ai_roy_vpc.sh

set -e
AWS_REGION=us-east-1
VPC_CIDR=10.10.0.0/16
SUBNET_CIDR=10.10.1.0/24
VPC_NAME=agentic-ai-roy
SG_NAME=ECS-SG

# 1. Create VPC
echo "Creating VPC..."
VPC_ID=$(aws ec2 create-vpc --cidr-block $VPC_CIDR --region $AWS_REGION --query 'Vpc.VpcId' --output text)
aws ec2 create-tags --resources $VPC_ID --tags Key=Name,Value=$VPC_NAME --region $AWS_REGION
echo "VPC ID: $VPC_ID"

# 2. Create Subnet
echo "Creating Subnet..."
SUBNET_ID=$(aws ec2 create-subnet --vpc-id $VPC_ID --cidr-block $SUBNET_CIDR --region $AWS_REGION --query 'Subnet.SubnetId' --output text)
aws ec2 create-tags --resources $SUBNET_ID --tags Key=Name,Value=${VPC_NAME}-subnet --region $AWS_REGION
echo "Subnet ID: $SUBNET_ID"

# 3. Create Security Group
echo "Creating Security Group..."
SG_ID=$(aws ec2 create-security-group --group-name $SG_NAME --description "ECS SG" --vpc-id $VPC_ID --region $AWS_REGION --query 'GroupId' --output text)
aws ec2 create-tags --resources $SG_ID --tags Key=Name,Value=$SG_NAME --region $AWS_REGION
echo "Security Group ID: $SG_ID"

# 4. Allow inbound traffic on port 8000
echo "Authorizing inbound traffic on port 8000..."
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 8000 --cidr 0.0.0.0/0 --region $AWS_REGION
echo "Inbound rule added."

# 5. Output summary
echo "\n--- VPC/Network Resources Created ---"
echo "VPC ID: $VPC_ID"
echo "Subnet ID: $SUBNET_ID"
echo "Security Group ID: $SG_ID"
