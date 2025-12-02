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

- **AI-Powered Clustering**: Uses embedding-based similarity to group related feedback into issue clusters

- **Automated Fix Generation**: LLM-powered coding agent that:
  - Analyzes clustered issues
  - Selects relevant files to modify
  - Generates code patches
  - Opens GitHub pull requests

- **Web Dashboard**: Next.js dashboard for reviewing clusters, triggering fixes, and managing feedback

## Architecture

The system consists of three main components:

1. **Backend (FastAPI)**: Python service handling ingestion, clustering, and agent orchestration
2. **Dashboard (Next.js)**: Web interface for triage and management
3. **Coding Agent**: Standalone service that generates fixes and opens PRs

## Prerequisites

- Python 3.12+
- Node.js 18+
- Redis instance (Upstash recommended for serverless)
- PostgreSQL database
- GitHub account with repository access
- LLM API key (Gemini recommended)

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
- `GEMINI_API_KEY` or `GOOGLE_GENERATIVE_AI_API_KEY` - For embeddings and LLM operations
- `GITHUB_TOKEN` - GitHub personal access token with repo permissions

**Dashboard** (`.env.local`):
- `UPSTASH_REDIS_REST_URL` - Same Redis credentials
- `UPSTASH_REDIS_REST_TOKEN` - Same Redis token
- `GITHUB_ID` - GitHub OAuth app client ID
- `GITHUB_SECRET` - GitHub OAuth app client secret
- `NEXTAUTH_URL` - Your app URL (e.g., `http://localhost:3000`)
- `NEXTAUTH_SECRET` - Random secret for NextAuth (generate with `openssl rand -base64 32`)
- `DATABASE_URL` - PostgreSQL connection string

### Optional Variables

- `REDDIT_SUBREDDITS` - Comma-separated list of subreddits to monitor (e.g., `"claudeai,programming"`)
- `GITHUB_OWNER` - Default GitHub repository owner
- `GITHUB_REPO` - Default GitHub repository name
- `BACKEND_URL` - Backend API URL (defaults to `http://localhost:8000`)

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

1. **Ingestion**: The system continuously monitors configured sources (Reddit, Sentry, GitHub) for new feedback
2. **Clustering**: New feedback items are embedded and compared against existing clusters using cosine similarity
3. **Triage**: Clusters are displayed in the dashboard with AI-generated summaries
4. **Fix Generation**: When a developer clicks "Generate Fix", the coding agent:
   - Analyzes the cluster context
   - Identifies relevant files to modify
   - Generates code patches using an LLM
   - Validates syntax
   - Opens a GitHub PR
5. **Review**: Developers review and merge the PR as normal

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read the project guidelines and submit pull requests for any improvements.

## Support

For issues, questions, or contributions, please open an issue on GitHub.
