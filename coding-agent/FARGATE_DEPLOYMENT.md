# AWS Fargate Deployment Guide

## 🎯 Architecture

Your Next.js dashboard triggers Fargate tasks on-demand via AWS ECS API:

```
┌─────────────────────────────────┐
│   Next.js Dashboard (Vercel)   │
│   /api/trigger-agent/route.ts  │
└──────────────┬──────────────────┘
               │
               │ AWS SDK: RunTaskCommand
               ▼
┌─────────────────────────────────┐
│      AWS ECS Fargate            │
│                                 │
│  ┌──────────────────────────┐  │
│  │  Fargate Task (on-demand)│  │
│  │  coding-agent container  │  │
│  │  - Pulls from ECR        │  │
│  │  - Gets secrets          │  │
│  │  - Fixes issue           │  │
│  │  - Creates PR            │  │
│  │  - Exits                 │  │
│  └──────────────────────────┘  │
│                                 │
│  VPC (Public Subnets)           │
│  + Security Groups              │
└─────────────────────────────────┘
               │
               ▼
         ┌─────────┐
         │ GitHub  │
         └─────────┘
```

## 📋 Prerequisites

- AWS Account with admin access
- AWS CLI installed (`brew install awscli`)
- Docker installed and running
- Terraform installed (`brew install terraform`)
- GitHub Personal Access Token with `repo` scope

## 🚀 Deployment Steps

### 1. Configure AWS CLI (2 min)

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Region: us-east-1
# Format: json

# Verify IAM permissions
aws iam attach-user-policy \
  --user-name YOUR_USERNAME \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
```

### 2. Create ECR Repository and Push Image (10 min)

```bash
# Create ECR repository
aws ecr create-repository --repository-name coding-agent --region us-east-1

# Get your AWS account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

# Build for AMD64 (required for Fargate)
cd coding-agent
docker build --platform linux/amd64 -t coding-agent .

# Tag and push
docker tag coding-agent:latest ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/coding-agent:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/coding-agent:latest
```

**Note**: The `--platform linux/amd64` flag is **required** if you're on Apple Silicon (M1/M2/M3).

### 3. Store Secrets in AWS Secrets Manager (2 min)

```bash
# Store Gemini API Key
aws secretsmanager create-secret \
  --name coding-agent/gemini-api-key \
  --secret-string "YOUR_GEMINI_API_KEY" \
  --region us-east-1

# Store GitHub Token
aws secretsmanager create-secret \
  --name coding-agent/github-token \
  --secret-string "YOUR_GITHUB_TOKEN" \
  --region us-east-1

# Store Git User Email
aws secretsmanager create-secret \
  --name coding-agent/git-user-email \
  --secret-string "your.email@example.com" \
  --region us-east-1

# Store Git User Name
aws secretsmanager create-secret \
  --name coding-agent/git-user-name \
  --secret-string "Your Name" \
  --region us-east-1
```

**Important**: These secrets are automatically injected as environment variables into your Fargate tasks:
- `coding-agent/gemini-api-key` → `GEMINI_API_KEY`
- `coding-agent/github-token` → `GH_TOKEN`
- `coding-agent/git-user-email` → `GIT_USER_EMAIL`
- `coding-agent/git-user-name` → `GIT_USER_NAME`

### 4. Deploy Infrastructure with Terraform (3 min)

```bash
cd terraform

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply (creates all AWS resources)
terraform apply
# Type 'yes' when prompted

# Save these outputs - you'll need them for your dashboard
terraform output ecs_cluster_name
terraform output ecs_task_definition
terraform output subnet_ids
terraform output security_group_id
terraform output aws_region
```

**What Terraform Creates:**
- VPC with 2 public subnets (no NAT Gateway for cost savings)
- Internet Gateway
- Security Group (allows outbound traffic only)
- ECS Cluster
- ECS Task Definition (references your ECR image and secrets)
- IAM roles with Secrets Manager permissions
- CloudWatch Log Group

### 5. Configure Dashboard Environment Variables

Add these to your Vercel/Next.js dashboard environment variables:

```env
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=<your_access_key_id>
AWS_SECRET_ACCESS_KEY=<your_secret_access_key>

# ECS Configuration (from terraform output)
ECS_CLUSTER_NAME=coding-agent-cluster
ECS_TASK_DEFINITION=coding-agent-task
ECS_SUBNET_IDS=subnet-xxx,subnet-yyy
ECS_SECURITY_GROUP_IDS=sg-xxx
```

**Note**: `assignPublicIp` should be set to `'ENABLED'` in your `trigger-agent/route.ts` since tasks run in public subnets.

### 6. Test the Integration

Trigger a task from your dashboard:

```bash
curl -X POST https://your-dashboard.vercel.app/api/trigger-agent \
  -H "Content-Type: application/json" \
  -d '{"issue_url": "https://github.com/owner/repo/issues/123"}'
```

Expected response:
```json
{
  "success": true,
  "message": "Agent triggered successfully",
  "taskArn": "arn:aws:ecs:us-east-1:557690581930:task/coding-agent-cluster/..."
}
```

## 📊 Monitoring

### View Task Logs

```bash
# List running/recent tasks
aws ecs list-tasks --cluster coding-agent-cluster --region us-east-1

# Get task details
aws ecs describe-tasks \
  --cluster coding-agent-cluster \
  --tasks <task-arn> \
  --region us-east-1

# View logs in real-time
aws logs tail /ecs/coding-agent --follow --region us-east-1
```

### CloudWatch Metrics

- Go to AWS Console → CloudWatch → Log Groups → `/ecs/coding-agent`
- View task execution logs, errors, and Kilo output

## 💰 Cost Estimate

Optimized for hackathon/temporary usage:

| Resource | Cost |
|----------|------|
| **Secrets Manager** | ~$1.60/month (4 secrets) |
| **CloudWatch Logs** | ~$0.50/month (7-day retention) |
| **Fargate Tasks** | ~$0.04/hour × usage (2 vCPU, 4 GB) |
| **ECR Storage** | ~$0.10/GB/month |
| **VPC/Subnets** | Free |
| **Internet Gateway** | Free |

**Estimated Total**: ~$3-10/month depending on usage

**Note**: No NAT Gateway ($32/month saved) because tasks use public subnets with direct internet access.

## 🔒 Security

✅ **Security Group**: Blocks all inbound traffic, allows outbound only  
✅ **Secrets Manager**: All API keys encrypted at rest  
✅ **IAM Roles**: Least-privilege permissions  
✅ **Public IPs**: Temporary, assigned only during task execution  
✅ **CloudWatch Logs**: 7-day retention for audit trail  

## 🆘 Troubleshooting

### Task fails to start

```bash
# Check task logs
aws logs tail /ecs/coding-agent --follow

# Common issues:
# - Image not found → verify ECR push
# - Secrets not accessible → check IAM permissions
# - Network issues → verify security group allows outbound
```

### Task runs but doesn't create PR

```bash
# View detailed logs
aws logs get-log-events \
  --log-group-name /ecs/coding-agent \
  --log-stream-name <stream-name>

# Common issues:
# - GH_TOKEN invalid → update secret
# - Git config missing → verify GIT_USER_EMAIL/NAME secrets
# - Kilo configuration → check GEMINI_API_KEY secret
```

### Terraform errors

```bash
# If resources already exist
terraform import aws_ecs_cluster.main coding-agent-cluster

# If you need to start fresh
terraform destroy
terraform apply

# View current state
terraform show
```

## 🎯 Updating Your Code

When you update `fix_issue.py` or `Dockerfile`:

```bash
# 1. Rebuild image
docker build --platform linux/amd64 -t coding-agent .

# 2. Push to ECR
docker tag coding-agent:latest ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/coding-agent:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/coding-agent:latest

# 3. Force new deployment (optional - ECS will use latest on next RunTask)
aws ecs update-service \
  --cluster coding-agent-cluster \
  --service coding-agent-service \
  --force-new-deployment
```

**Note**: Since you're using on-demand tasks (not a service), the next RunTask call will automatically use the latest image.

## 🧹 Cleanup

When you're done with the hackathon:

```bash
# Delete all AWS resources
cd terraform
terraform destroy
# Type 'yes' when prompted

# Delete secrets
aws secretsmanager delete-secret --secret-id coding-agent/gemini-api-key --region us-east-1 --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id coding-agent/github-token --region us-east-1 --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id coding-agent/git-user-email --region us-east-1 --force-delete-without-recovery
aws secretsmanager delete-secret --secret-id coding-agent/git-user-name --region us-east-1 --force-delete-without-recovery

# Delete ECR repository
aws ecr delete-repository --repository-name coding-agent --region us-east-1 --force
```

---

**You're done!** Your coding agent is now running on AWS Fargate, triggered on-demand from your Next.js dashboard. 🎉
