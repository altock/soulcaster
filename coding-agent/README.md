# Coding Agent

This tool automates the process of fixing GitHub issues using the Kilo CLI.

## Prerequisites

Before running the tool, ensure you have the following installed:

1.  **uv**: A fast Python package installer and resolver.
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
2.  **GitHub CLI (`gh`)**: Required for cloning repos and interacting with issues/PRs.
    *   Install: [https://cli.github.com/](https://cli.github.com/)
    *   Authenticate: `gh auth login`
3.  **Kilo CLI (`kilocode`)**: The AI coding assistant.
    ```bash
    npm install -g @kilocode/cli
    ```
4.  **Git**: Version control system.

## Setup

1.  **Environment Variables**:
    Create a `.env` file in this directory and add your Gemini API key:
    ```bash
    GEMINI_API_KEY=your_api_key_here
    ```

    The script will automatically configure Kilo to use the Gemini provider.

    For more details on provider configuration, see the [Kilo Provider Configuration Guide](https://github.com/Kilo-Org/kilocode/blob/ed3e401d7ab153bab5619219ed69ca62badfcef0/cli/docs/PROVIDER_CONFIGURATION.md).

2.  **Dependencies**:
    This project uses `uv` for dependency management. The dependencies are defined in `pyproject.toml`.

## Usage

To run the issue fixer, use `uv run`. This will automatically create a virtual environment and install the necessary dependencies (`python-dotenv`) if they are missing.

```bash
uv run fix_issue.py <issue_url>
```

**Example:**

```bash
uv run fix_issue.py https://github.com/owner/repo/issues/123
```

## How it Works

1.  Parses the GitHub issue URL.
2.  Clones the repository using `gh repo clone`.
3.  Fetches the issue details (title and body).
4.  Creates a new branch `fix/issue-<number>`.
5.  Runs `kilocode` with the issue description to generate a fix.
6.  Commits the changes.
7.  Pushes the branch to the remote repository.
8.  Creates a Pull Request using `gh pr create`.

## Docker Usage

You can also run the agent in a Docker container.

### 1. Build the Image

```bash
docker build -t coding-agent .
```

### 2. Run the Container

You need to pass your `GEMINI_API_KEY` and a `GH_TOKEN` (GitHub Personal Access Token) so the agent can clone repos and create PRs.

```bash
docker run -it \
  -e GEMINI_API_KEY=your_api_key_here \
  -e GH_TOKEN=your_github_token_here \
  coding-agent https://github.com/owner/repo/issues/123
```

**Note:**
*   `GH_TOKEN`: Create a Personal Access Token (Classic) with `repo` scope at [https://github.com/settings/tokens](https://github.com/settings/tokens).
*   Replace `your_api_key_here` with your actual Gemini API key.
*   Replace `your_github_token_here` with your GitHub token.
*   Replace the URL with the actual issue you want to fix.

## AWS Fargate Deployment

For production deployment, you can run this agent on AWS Fargate.

### 1. Create ECR Repository

```bash
aws ecr create-repository --repository-name coding-agent --region us-east-1
```

### 2. Build and Push Image

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Build and Tag
docker build -t coding-agent .
docker tag coding-agent:latest <YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/coding-agent:latest

# Push
docker push <YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/coding-agent:latest
```

### 3. Deploy Infrastructure

We use Terraform to provision the VPC, ALB, and Fargate Service.

1.  Navigate to the `terraform` directory (create it if it doesn't exist and add the `main.tf` from `AWS_FARGATE_DEPLOYMENT.md`).
2.  Run:
    ```bash
    terraform init
    terraform apply
    ```

For a detailed step-by-step guide, including setting up secrets and integrating with your backend, see [AWS_FARGATE_DEPLOYMENT.md](AWS_FARGATE_DEPLOYMENT.md).
