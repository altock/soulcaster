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
    Create a `.env` file in this directory with the following variables:
    
    **Required**:
    ```bash
    # LLM Provider (use one)
    GEMINI_API_KEY=your_api_key_here
    # OR
    MINIMAX_API_KEY=your_minimax_key
    
    # GitHub (for creating branches and PRs)
    GH_TOKEN=ghp_your_token_with_repo_scope
    GIT_USER_EMAIL=your@email.com
    GIT_USER_NAME=Your Name
    ```
    
    **Optional** (for job tracking):
    ```bash
    BACKEND_URL=http://localhost:8000  # Backend API for status updates
    JOB_ID=uuid-here  # Auto-passed when triggered from dashboard
    ```

    The script will automatically configure Kilo to use the specified provider (Gemini or Minimax).

    For more details on provider configuration, see the [Kilo Provider Configuration Guide](https://github.com/Kilo-Org/kilocode/blob/ed3e401d7ab153bab5619219ed69ca62badfcef0/cli/docs/PROVIDER_CONFIGURATION.md).

2.  **Dependencies**:
    This project uses `uv` for dependency management. The dependencies are defined in `pyproject.toml`.

## Usage

To run the issue fixer, use `uv run`. This will automatically create a virtual environment and install the necessary dependencies (`python-dotenv`) if they are missing.

### Basic Usage

```bash
uv run fix_issue.py <issue_url>
```

**Example:**

```bash
uv run fix_issue.py https://github.com/owner/repo/issues/123
```

### With Job Tracking

When triggered from the dashboard, a job ID is automatically provided:

```bash
uv run fix_issue.py <issue_url> --job-id <uuid>
```

This enables the agent to report status updates, logs, and PR URLs back to the backend for tracking in the dashboard.

## How it Works

1.  **Parse Issue URL**: Extracts owner, repo, and issue number
2.  **Setup Provider**: Configures Kilo CLI with Gemini or Minimax
3.  **Clone Repository**: Uses `gh repo clone` to get the codebase
4.  **Fetch Issue Details**: Retrieves title and body via GitHub API
5.  **Create Branch**: Creates `fix/issue-<number>` branch
6.  **Generate Fix**: Runs `kilocode` with the issue context to:
    - Analyze the codebase
    - Identify relevant files
    - Generate code patches
    - Apply changes
7.  **Commit & Push**: Commits changes with descriptive message
8.  **Create PR**: Opens pull request using `gh pr create`
9.  **Report Status**: Updates job status in backend (if job ID provided)

The agent operates in an isolated directory and cleans up after itself. When run from Fargate, it executes in a fresh container environment.

## Docker Usage

You can also run the agent in a Docker container.

### 1. Build the Image

```bash
docker build -t coding-agent .
```

### 2. Run the Container

Pass env variables using .env file locally.

```bash
docker run -it \
  --env-file .env \
  coding-agent https://github.com/owner/repo/issues/123
```

**Environment Variables:**
- `GEMINI_API_KEY` or `MINIMAX_API_KEY`: Your LLM API key (required)
- `GH_TOKEN`: GitHub Personal Access Token with `repo` scope (required). Create one at [https://github.com/settings/tokens](https://github.com/settings/tokens)
- `GIT_USER_EMAIL`: Email for git commits (required)
- `GIT_USER_NAME`: Name for git commits (required)
- `BACKEND_URL`: Backend API URL for job tracking (optional)
- `JOB_ID`: Job UUID for status reporting (optional, auto-provided from dashboard)
- `KILO_API_MODEL_ID`: Gemini model to use (optional, defaults to `gemini-2.5-flash-preview-04-17`)

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

To deploy the coding agent to AWS Fargate and trigger it from your Next.js dashboard:

1. **Deploy to AWS Fargate**: Follow the step-by-step guide in [`FARGATE_DEPLOYMENT.md`](./FARGATE_DEPLOYMENT.md)
2. **Configure Dashboard**: Add AWS credentials and ECS configuration to your Vercel environment variables
3. **Trigger Tasks**: Use the `/api/trigger-agent` endpoint to run tasks on-demand

See [`FARGATE_DEPLOYMENT.md`](./FARGATE_DEPLOYMENT.md) for complete instructions.
