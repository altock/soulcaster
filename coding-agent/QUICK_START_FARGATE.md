# Quick Start: Fargate + Sevalla Setup

## 🎯 Goal

Deploy your coding agent to AWS Fargate and integrate it with your Sevalla backend.

## ⏱️ Estimated Time: 45-60 minutes

## 📋 Prerequisites Checklist

- [ ] AWS Account with admin access
- [ ] AWS CLI installed (`brew install awscli`)
- [ ] Docker installed and running
- [ ] Sevalla account at kinsta.com
- [ ] Terraform installed (`brew install terraform`)
- [ ] GitHub tokens ready

## 🚀 Part 1: Deploy Coding Agent to AWS Fargate (30 min)

### Step 1: Configure AWS CLI (2 min)

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Region: us-east-1
# Format: json
```

### Step 2: Create ECR and Push Image (10 min)

```bash
# Create ECR repository
aws ecr create-repository --repository-name coding-agent --region us-east-1

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push
cd /Users/nagakarumuri/Documents/Hackathon/coding-agent
docker build -t coding-agent .
docker tag coding-agent:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/coding-agent:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/coding-agent:latest
```

### Step 3: Store Secrets (2 min)

```bash
aws secretsmanager create-secret \
  --name coding-agent/codex-api-key \
  --secret-string "YOUR_CODEX_API_KEY" \
  --region us-east-1

aws secretsmanager create-secret \
  --name coding-agent/github-token \
  --secret-string "YOUR_GITHUB_TOKEN" \
  --region us-east-1
```

### Step 4: Deploy with Terraform (15 min)

```bash
cd terraform
terraform init
terraform plan
terraform apply

# SAVE THIS OUTPUT - your API endpoint
terraform output alb_dns_name
# Example: coding-agent-alb-123456789.us-east-1.elb.amazonaws.com
```

### Step 5: Test the Endpoint (1 min)

```bash
# Replace with your ALB DNS name
export ALB_URL="http://coding-agent-alb-xyz.us-east-1.elb.amazonaws.com"

# Health check
curl $ALB_URL/

# Submit test job
curl -X POST $ALB_URL/fix-issue \
  -H "Content-Type: application/json" \
  -d '{"issue_url": "https://github.com/naga-k/bad-ux-mart/issues/5"}'
```

## 🔗 Part 2: Connect Sevalla Backend (15 min)

### Step 1: Add Environment Variables in Kinsta Dashboard

1. Go to https://my.kinsta.com/applications
2. Select your application
3. Settings → Environment variables
4. Add:
   ```
   CODING_AGENT_URL=http://coding-agent-alb-xyz.us-east-1.elb.amazonaws.com
   ```

### Step 2: Add Integration Code to Your Sevalla Backend

Copy the integration code from `integration_example.py`:

```python
import os
import requests

def trigger_issue_fix(issue_url: str):
    """Call the coding agent from your Sevalla backend"""
    response = requests.post(
        f"{os.getenv('CODING_AGENT_URL')}/fix-issue",
        json={"issue_url": issue_url}
    )
    return response.json()

# Usage
job = trigger_issue_fix("https://github.com/owner/repo/issues/123")
print(f"Job ID: {job['job_id']}")
```

### Step 3: Deploy Your Backend

```bash
# Sevalla auto-deploys on git push
git add .
git commit -m "Add coding agent integration"
git push origin main
```

### Step 4: Test End-to-End

From your Sevalla backend, trigger a job and verify it creates a PR on GitHub.

## ✅ Verification Checklist

- [ ] Fargate tasks are running (check AWS ECS console)
- [ ] ALB health checks passing
- [ ] Test API call returns job ID
- [ ] Sevalla environment variables configured
- [ ] Integration code deployed
- [ ] End-to-end test successful (issue → PR)

## 📊 Monitor Your Infrastructure

### AWS CloudWatch

```bash
# View logs
aws logs tail /ecs/coding-agent --follow

# Check task status
aws ecs describe-services \
  --cluster coding-agent-cluster \
  --services coding-agent-service
```

### Sevalla Dashboard

- my.kinsta.com/applications → Your app → Analytics
- Check CPU, RAM, request metrics

## 💰 Cost Tracking

### Set Up Billing Alerts

1. AWS Console → Billing → Budgets
2. Create budget: $400/month
3. Add email alerts at 80%, 100%

### Expected Costs

- **AWS Fargate**: ~$200-300/month
- **Sevalla**: ~$30-100/month
- **Total**: ~$250-400/month

## 🔒 Security Best Practices

### Add API Authentication (Recommended)

1. Create API key in Secrets Manager:
   ```bash
   aws secretsmanager create-secret \
     --name coding-agent/api-key \
     --secret-string "$(openssl rand -base64 32)"
   ```

2. Update `backend.py` to require API key (see AWS_FARGATE_DEPLOYMENT.md)

3. Add API key to Sevalla environment variables

### Enable HTTPS (Production)

1. Request ACM certificate for your domain
2. Add HTTPS listener to ALB
3. Update Sevalla to use HTTPS URL

## 🆘 Troubleshooting

### Fargate tasks not starting?

```bash
# Check task logs
aws logs tail /ecs/coding-agent --follow

# Common issues:
# - Image not found → check ECR push
# - Secrets not accessible → check IAM permissions
# - Health check failing → check / endpoint returns 200
```

### Sevalla can't reach Fargate?

```bash
# Test from your local machine
curl http://your-alb-url.elb.amazonaws.com/

# Check security groups allow port 80
# Check ALB is internet-facing
```

## 📚 Documentation

- **Full Deployment**: [AWS_FARGATE_DEPLOYMENT.md](./AWS_FARGATE_DEPLOYMENT.md)
- **Architecture**: [ARCHITECTURE_FARGATE_SEVALLA.md](./ARCHITECTURE_FARGATE_SEVALLA.md)
- **Sevalla Setup**: [SEVALLA_DEPLOYMENT.md](./SEVALLA_DEPLOYMENT.md)
- **Terraform**: [terraform/main.tf](./terraform/main.tf)

## 🎉 You're Done!

Your coding agent is now running on production-grade AWS infrastructure, callable from your Sevalla backend!

**Next steps:**
- Set up CloudWatch dashboards
- Configure auto-scaling thresholds
- Add custom domain with HTTPS
- Set up CI/CD for automated deployments
