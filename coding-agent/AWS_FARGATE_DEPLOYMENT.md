# AWS Fargate Deployment Guide for Coding Agent

## 🎯 Architecture Overview

```
┌─────────────────────────────────────┐
│     Your Main Backend               │
│     (Hosted on Sevalla)             │
│                                     │
│  - User management                  │
│  - Business logic                   │
│  - Database operations              │
└──────────────┬──────────────────────┘
               │
               │ HTTPS Request
               │ (VPC or public endpoint)
               ▼
┌─────────────────────────────────────┐
│      AWS Fargate (ECS)              │
│   Coding Agent Service              │
│                                     │
│  ┌────────────────────────────┐    │
│  │  Application Load Balancer │    │
│  └──────────┬─────────────────┘    │
│             │                       │
│  ┌──────────▼─────────────────┐    │
│  │    ECS Service              │    │
│  │  ┌──────────────────────┐  │    │
│  │  │  Fargate Task 1      │  │    │
│  │  │  (coding-agent)      │  │    │
│  │  └──────────────────────┘  │    │
│  │  ┌──────────────────────┐  │    │
│  │  │  Fargate Task 2      │  │    │
│  │  │  (auto-scaled)       │  │    │
│  │  └──────────────────────┘  │    │
│  └────────────────────────────┘    │
│                                     │
│  VPC with Private Subnets          │
│  + Security Groups                  │
└─────────────────────────────────────┘
               │
               ▼
         ┌─────────┐
         │ GitHub  │
         └─────────┘
```

## ✅ Why This Architecture?

### **AWS Fargate for Coding Agent:**
✅ **Production-grade isolation** - VPC, security groups, task isolation  
✅ **No server management** - Fully serverless containers  
✅ **Auto-scaling** - Scale based on load  
✅ **VPC security** - Private subnets, controlled egress  
✅ **IAM integration** - Fine-grained permissions  
✅ **Compliance ready** - Meets enterprise security standards

### **Sevalla for Main Backend:**
✅ **Simple deployment** - Easy to manage web apps  
✅ **GCP infrastructure** - Reliable and fast  
✅ **Quick iterations** - Auto-deploy from Git  
✅ **Cost-effective** - Usage-based pricing for backend  
✅ **Developer friendly** - Clean dashboard

## 📋 Prerequisites

- AWS Account with admin access
- AWS CLI installed and configured
- Docker installed locally
- Sevalla account with an application deployed
- Domain name (optional, for custom domains)

## 🚀 Part 1: AWS Setup

### Step 1: Install AWS CLI and Configure

```bash
# Install AWS CLI (macOS)
brew install awscli

# Configure credentials
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: us-east-1 (or your preferred region)
# Default output format: json
```

### Step 2: Create ECR Repository

```bash
# Create a repository for your Docker image
aws ecr create-repository \
  --repository-name coding-agent \
  --region us-east-1

# Output will include repositoryUri - save this!
# Example: 123456789012.dkr.ecr.us-east-1.amazonaws.com/coding-agent
```

### Step 3: Build and Push Docker Image

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build your Docker image
cd /Users/nagakarumuri/Documents/Hackathon/coding-agent
docker build -t coding-agent .

# Tag the image
docker tag coding-agent:latest \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/coding-agent:latest

# Push to ECR
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/coding-agent:latest
```

### Step 4: Create Secrets in AWS Secrets Manager

```bash
# Store your API keys securely
aws secretsmanager create-secret \
  --name coding-agent/codex-api-key \
  --secret-string "your-codex-api-key-here" \
  --region us-east-1

aws secretsmanager create-secret \
  --name coding-agent/github-token \
  --secret-string "your-github-token-here" \
  --region us-east-1
```

## 🏗️ Part 2: Infrastructure as Code

I'll provide both **Terraform** and **CloudFormation** options. Choose one:

### Option A: Terraform (Recommended)

Create `terraform/main.tf`:

```hcl
# terraform/main.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "aws_region" {
  default = "us-east-1"
}

variable "app_name" {
  default = "coding-agent"
}

variable "container_port" {
  default = 8000
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.app_name}-vpc"
  }
}

# Public Subnets (for ALB)
resource "aws_subnet" "public_1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "${var.aws_region}a"

  tags = {
    Name = "${var.app_name}-public-1"
  }
}

resource "aws_subnet" "public_2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.aws_region}b"

  tags = {
    Name = "${var.app_name}-public-2"
  }
}

# Private Subnets (for Fargate tasks)
resource "aws_subnet" "private_1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "${var.aws_region}a"

  tags = {
    Name = "${var.app_name}-private-1"
  }
}

resource "aws_subnet" "private_2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "${var.aws_region}b"

  tags = {
    Name = "${var.app_name}-private-2"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.app_name}-igw"
  }
}

# NAT Gateway (for private subnets to access internet)
resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public_1.id

  tags = {
    Name = "${var.app_name}-nat"
  }
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.app_name}-public-rt"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name = "${var.app_name}-private-rt"
  }
}

# Route Table Associations
resource "aws_route_table_association" "public_1" {
  subnet_id      = aws_subnet.public_1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_2" {
  subnet_id      = aws_subnet.public_2.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private_1" {
  subnet_id      = aws_subnet.private_1.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_2" {
  subnet_id      = aws_subnet.private_2.id
  route_table_id = aws_route_table.private.id
}

# Security Group for ALB
resource "aws_security_group" "alb" {
  name        = "${var.app_name}-alb-sg"
  description = "Security group for ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Security Group for ECS Tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.app_name}-ecs-tasks-sg"
  description = "Security group for ECS tasks"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.app_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public_1.id, aws_subnet.public_2.id]

  tags = {
    Name = "${var.app_name}-alb"
  }
}

# Target Group
resource "aws_lb_target_group" "main" {
  name        = "${var.app_name}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/"
    healthy_threshold   = 2
    unhealthy_threshold = 10
    timeout             = 60
    interval            = 120
    matcher             = "200"
  }
}

# ALB Listener
resource "aws_lb_listener" "main" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.app_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.app_name}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Additional policy for Secrets Manager
resource "aws_iam_role_policy" "secrets_access" {
  name = "${var.app_name}-secrets-access"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [
        "arn:aws:secretsmanager:${var.aws_region}:*:secret:coding-agent/*"
      ]
    }]
  })
}

# ECS Task Definition
resource "aws_ecs_task_definition" "main" {
  family                   = var.app_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "2048"  # 2 vCPU
  memory                   = "4096"  # 4 GB
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([{
    name  = var.app_name
    image = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/coding-agent:latest"
    
    portMappings = [{
      containerPort = var.container_port
      protocol      = "tcp"
    }]

    secrets = [
      {
        name      = "CODEX_API_KEY"
        valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:coding-agent/codex-api-key"
      },
      {
        name      = "GITHUB_TOKEN"
        valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:coding-agent/github-token"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/${var.app_name}"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "main" {
  name              = "/ecs/${var.app_name}"
  retention_in_days = 7
}

# ECS Service
resource "aws_ecs_service" "main" {
  name            = "${var.app_name}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.main.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.private_1.id, aws_subnet.private_2.id]
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.main.arn
    container_name   = var.app_name
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.main]
}

# Auto Scaling
resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.main.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "ecs_cpu" {
  name               = "${var.app_name}-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}

# Data source for AWS account ID
data "aws_caller_identity" "current" {}

# Outputs
output "alb_dns_name" {
  value       = aws_lb.main.dns_name
  description = "DNS name of the load balancer - use this to call your API"
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  value = aws_ecs_service.main.name
}
```

### Deploy with Terraform:

```bash
# Initialize Terraform
cd terraform
terraform init

# Plan the deployment
terraform plan

# Apply the infrastructure
terraform apply

# Output will show the ALB DNS name - this is your API endpoint!
# Example: coding-agent-alb-123456789.us-east-1.elb.amazonaws.com
```

## 🔗 Part 3: Integrate Sevalla Backend with Fargate

### In Your Sevalla Backend:

Update your environment variables in Kinsta dashboard:

```bash
# Add to Sevalla environment variables
CODING_AGENT_URL=http://coding-agent-alb-123456789.us-east-1.elb.amazonaws.com
```

### Use the Integration Client:

Your Sevalla backend can use the integration code from `integration_example.py`:

```python
# In your Sevalla backend
from integration_example import CodingAgentClient

# Initialize with Fargate endpoint
client = CodingAgentClient(
    base_url="http://coding-agent-alb-123456789.us-east-1.elb.amazonaws.com"
)

# Submit a job
job = client.submit_fix("https://github.com/owner/repo/issues/123")
print(f"Job ID: {job['job_id']}")

# Check status
status = client.get_job_status(job["job_id"])
```

## 🔒 Part 4: Security Enhancements

### Add API Authentication:

Update `backend.py` to require an API key:

```python
# backend.py - add this
from fastapi import Header, HTTPException
import os

API_KEY = os.getenv("API_KEY", "your-secret-key")

async def verify_api_key(x_api_key: str = Header()):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.post("/fix-issue", dependencies=[Depends(verify_api_key)])
async def fix_issue(...):
    # ... existing code
```

Add API_KEY to Secrets Manager and update task definition.

### In Sevalla Backend:

```python
client = CodingAgentClient(
    base_url="http://coding-agent-alb-xyz.elb.amazonaws.com"
)

# Add API key header
import requests
response = requests.post(
    f"{client.base_url}/fix-issue",
    headers={"X-API-Key": os.getenv("CODING_AGENT_API_KEY")},
    json={"issue_url": issue_url}
)
```

## 📊 Part 5: Monitoring & Logging

### View Logs:

```bash
# Via AWS CLI
aws logs tail /ecs/coding-agent --follow

# Or in AWS Console:
# CloudWatch → Log Groups → /ecs/coding-agent
```

### Monitor Metrics:

```bash
# View ECS service metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=coding-agent-service \
  --start-time 2025-11-22T00:00:00Z \
  --end-time 2025-11-22T23:59:59Z \
  --period 3600 \
  --statistics Average
```

## 💰 Cost Estimate

### AWS Fargate Costs (us-east-1):
- **vCPU**: $0.04048 per vCPU per hour
- **Memory**: $0.004445 per GB per hour

**For 2 vCPU, 4 GB RAM, 2 tasks:**
- Per task per hour: (2 × $0.04048) + (4 × $0.004445) = $0.0987/hour
- 2 tasks: $0.1974/hour
- **Monthly (730 hours)**: ~$144/month base

**With auto-scaling (average 4 tasks):**
- ~$288/month

**Additional costs:**
- ALB: ~$23/month
- NAT Gateway: ~$33/month
- Data transfer: Variable

**Total: ~$200-350/month** for production-grade infrastructure

### Sevalla Costs:
- Usage-based pricing for main backend
- Typically $30-100/month depending on usage

**Combined: ~$250-450/month** for complete infrastructure

## 🚀 Deployment Checklist

- [ ] AWS CLI configured
- [ ] ECR repository created
- [ ] Docker image built and pushed to ECR
- [ ] Secrets created in Secrets Manager
- [ ] Terraform applied successfully
- [ ] ALB DNS name saved
- [ ] Sevalla environment variables updated
- [ ] API authentication added
- [ ] CloudWatch alarms configured
- [ ] Test API endpoint from Sevalla backend

## 🎯 Next Steps

1. **Test the setup**: Call your Fargate endpoint from Sevalla
2. **Add HTTPS**: Use ACM certificate + Route53 for custom domain
3. **Add monitoring**: CloudWatch dashboards and alarms
4. **Cost optimization**: Review and adjust task count/size
5. **Backup strategy**: Document disaster recovery

---

**You now have a production-grade coding agent on AWS Fargate, callable from your Sevalla backend!** 🚀
