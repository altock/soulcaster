# Soulcaster

A self-healing development loop system that automatically ingests bug reports from multiple sources, clusters them using AI, and generates code fixes that are opened as GitHub pull requests.

**Flow**: Reddit/Sentry/GitHub Issues → Clustered Issues → Human Triage Dashboard → One-Click Fix → GitHub PR

## Overview

Soulcaster is an open-source feedback triage and automated fix generation system. It monitors multiple sources for bug reports and user feedback, intelligently clusters similar issues together, and uses AI to generate code fixes that can be reviewed and merged via GitHub PRs.

### Key Features

- **Multi-Source Ingestion**: Automatically collects feedback from:
  - Reddit (via polling configured subreddits)
  - Sentry (via webhooks)
  - GitHub Issues (via manual sync or webhooks)
  - Manual feedback submission

- **AI-Powered Clustering**: Uses embedding-based similarity (via Gemini) to group related feedback into issue clusters with automatic deduplication

- **Multi-Tenant Projects**: Support for multiple projects per user with project-level isolation for feedback and clusters

- **Authentication & Authorization**: GitHub OAuth integration via NextAuth for secure access control

- **Automated Fix Generation**: LLM-powered coding agent that:
  - Analyzes clustered issues
  - Selects relevant files to modify
  - Generates code patches
  - Opens GitHub pull requests
  - Can run locally or on AWS Fargate

- **Job Tracking**: Monitor agent fix generation jobs with status updates, logs, and PR links

- **Web Dashboard**: Next.js dashboard for:
  - Reviewing clusters and feedback
  - Managing multiple projects
  - Triggering fixes with one click
  - Configuring Reddit sources per project
  - Viewing PRs and job status

## Architecture

The system consists of three main components:

1. **Backend (FastAPI)**: Python service handling ingestion, clustering, and agent orchestration
2. **Dashboard (Next.js)**: Web interface for triage and management
3. **Coding Agent**: Standalone service that generates fixes and opens PRs

## Prerequisites

- Python 3.12+
- Node.js 20+
- Redis instance (Upstash recommended for serverless)
- PostgreSQL database (for dashboard authentication and project management only)
- GitHub account with repository access
- LLM API key (Gemini recommended for embeddings and fix generation)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/altock/soulcaster.git
cd soulcaster
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your configuration (see Configuration section)
```

### 3. Dashboard Setup

```bash
cd dashboard
npm install

# Setup Database
npx prisma migrate dev

# Copy environment variables
cp .env.example .env.local
# Edit .env.local with your configuration
```

### 4. Start Services

**Backend** (from project root):
```bash
uvicorn backend.main:app --reload
```

**Reddit Poller** (optional, from project root):
```bash
python -m backend.reddit_poller
```

**Dashboard** (from dashboard directory):
```bash
npm run dev
```

The dashboard will be available at `http://localhost:3000` and the backend API at `http://localhost:8000`.

## Configuration

See `.env.example` for all available environment variables. Key configuration includes:

### Required Variables

**Backend** (`.env`):
- `UPSTASH_REDIS_REST_URL` - Redis REST API URL (Upstash)
- `UPSTASH_REDIS_REST_TOKEN` - Redis REST API token
- `GEMINI_API_KEY` or `GOOGLE_GENERATIVE_AI_API_KEY` - For embeddings and LLM operations (required for clustering)
- `GITHUB_TOKEN` - GitHub personal access token with repo permissions (optional, for higher API limits)

**Dashboard** (`.env.local`):
- `UPSTASH_REDIS_REST_URL` - Same Redis credentials
- `UPSTASH_REDIS_REST_TOKEN` - Same Redis token
- `GEMINI_API_KEY` or `GOOGLE_GENERATIVE_AI_API_KEY` - For embeddings (clustering runs in dashboard)
- `GITHUB_ID` - GitHub OAuth app client ID
- `GITHUB_SECRET` - GitHub OAuth app client secret
- `NEXTAUTH_URL` - Your app URL (e.g., `http://localhost:3000`)
- `NEXTAUTH_SECRET` - Random secret for NextAuth (generate with `openssl rand -base64 32`)
- `DATABASE_URL` - PostgreSQL connection string for NextAuth and projects
- `GITHUB_TOKEN` - Optional GitHub token for higher API limits when syncing issues

**Coding Agent** (`.env` in `coding-agent/`):
- `GEMINI_API_KEY` or `MINIMAX_API_KEY` - LLM provider for fix generation
- `GH_TOKEN` - GitHub token with repo scope (for creating branches and PRs)
- `GIT_USER_EMAIL` - Email for git commits
- `GIT_USER_NAME` - Name for git commits
- `BACKEND_URL` - Backend API URL for status reporting (optional)
- `JOB_ID` - Job ID for tracking (optional, auto-passed when triggered from dashboard)

### Optional Variables

**Backend**:
- `REDDIT_SUBREDDITS` - Comma-separated list of subreddits to monitor (e.g., `"claudeai,programming"`)
- `REDDIT_SORTS` - Listing sorts to pull (`new`, `hot`, `top`) - defaults to `"new"`
- `REDDIT_POLL_INTERVAL_SECONDS` - How often to poll Reddit - defaults to `300`
- `REDIS_URL` or `UPSTASH_REDIS_URL` - Alternative Redis connection string (if not using REST API)

**Dashboard**:
- `BACKEND_URL` - Backend API URL (defaults to `http://localhost:8000`)
- `GITHUB_OWNER` - Default GitHub repository owner (for new issues)
- `GITHUB_REPO` - Default GitHub repository name (for new issues)
- AWS configuration (for Fargate agent deployment):
  - `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
  - `ECS_CLUSTER_NAME`, `ECS_TASK_DEFINITION`
  - `ECS_SUBNET_IDS`, `ECS_SECURITY_GROUP_IDS`

## Development

### Running Tests

**Backend**:
```bash
pytest backend/tests -q --cov=backend
```

**Dashboard**:
```bash
npm run test --prefix dashboard
```

### Code Style

**Backend**:
```bash
black backend && ruff backend
```

**Dashboard**:
```bash
npm run lint --prefix dashboard
```

## Deployment

### Backend Deployment (Sevalla, Railway, Render, etc.)

**Platform Settings:**
- Build path: `./backend/`
- Start command: `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}`
- Health probe: `GET /` (recommended for readiness checks)

**Environment Variables:**
Configure all required variables from the Configuration section above (Redis, Gemini API key, etc.).

### Dashboard Deployment (Vercel recommended)

Vercel is recommended for the Next.js dashboard. Set the root directory to `dashboard/` and configure all required environment variables.

**Note**: When deploying the backend with build path `./backend/`, the working directory is already inside the backend folder, so use `main:app` (not `backend.main:app`) in the uvicorn command.

## Project Structure

```
soulcaster/
├── backend/           # FastAPI backend service
│   ├── main.py        # API endpoints
│   ├── models.py      # Data models
│   ├── store.py       # Redis storage layer
│   ├── reddit_poller.py  # Reddit polling service
│   └── tests/         # Backend tests
├── dashboard/         # Next.js dashboard
│   ├── app/           # Next.js app router pages
│   ├── components/     # React components
│   ├── lib/           # Utility libraries
│   └── __tests__/     # Dashboard tests
├── coding-agent/      # Standalone coding agent service
└── documentation/     # Additional documentation
```

## How It Works

1. **Setup**: Create a project in the dashboard and configure your GitHub repository
2. **Ingestion**: The system monitors configured sources (Reddit, Sentry, GitHub) for new feedback
   - Reddit: Background poller checks configured subreddits periodically
   - GitHub: Manual sync or webhook integration
   - Sentry: Webhook integration
   - Manual: Direct submission via dashboard
3. **Clustering**: New feedback items are:
   - Embedded using Gemini's text-embedding models
   - Compared against existing clusters using cosine similarity
   - Automatically assigned to matching clusters or create new ones
4. **Triage**: Clusters are displayed in the dashboard with:
   - AI-generated summaries and titles
   - Feedback count and source breakdown
   - Links to original feedback items
5. **Fix Generation**: When you click "Generate Fix":
   - A job is created and tracked
   - The coding agent (local or Fargate) is triggered
   - Agent analyzes the cluster context and generates code patches
   - Creates a branch and opens a GitHub PR
   - Job status updates with logs and PR link
6. **Review**: Review and merge the PR through GitHub as normal

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read the project guidelines and submit pull requests for any improvements.

## Support

For issues, questions, or contributions, please open an issue on GitHub.
