# Soulcaster Backend

FastAPI-based backend service for the Soulcaster self-healing development loop system. Handles multi-source feedback ingestion, AI-powered clustering, job tracking, and multi-tenant project management.

## Features

- **Multi-source ingestion**: Reddit, Sentry, GitHub Issues, and manual text feedback
- **Redis storage**: Upstash Redis (REST API) with fallback to in-memory for development
- **AI-powered clustering**: Automatic feedback clustering using Gemini embeddings and cosine similarity
- **Reddit polling**: Background service that reads subreddits via Reddit's public JSON feed (no OAuth)
- **Job tracking**: Monitor coding agent fix generation jobs with status, logs, and PR links
- **Multi-tenant projects**: Support for multiple users and projects with proper isolation
- **Full test coverage**: Comprehensive test suite with pytest

## Project Structure

```
backend/
├── __init__.py
├── models.py           # Pydantic data models (FeedbackItem)
├── store.py           # In-memory storage layer
├── main.py            # FastAPI application and endpoints
├── reddit_poller.py   # Reddit polling service
├── requirements.txt   # Python dependencies
├── tests/
│   ├── test_ingestion.py      # Tests for API endpoints
│   └── test_reddit_poller.py  # Tests for Reddit poller
└── README.md
```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Running the Server

### Local Development

```bash
# Start the FastAPI server
cd backend
uvicorn main:app --reload

# Server will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Production Deployment

For platforms like Sevalla, Railway, Render, etc.:

**Settings:**
- Build path: `./backend/`
- Start command: `uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}`
- Health probe: GET `/` (recommended)

The `${PORT}` variable is injected by most platforms and defaults to 8080. The app will bind to whatever port the platform expects.

## Running the Reddit Poller

The Reddit poller runs as a separate background process:

```bash
# Set environment variables (examples)
export REDDIT_SUBREDDITS="claudeai"               # keep small list to avoid rate limits
export REDDIT_SORTS="new,hot,top"                # optional, defaults to "new"
export REDDIT_POLL_INTERVAL_SECONDS=300          # optional, defaults to 300s
export BACKEND_URL="http://localhost:8000"       # where to send ingested items

# Run the poller (uses Reddit's public JSON endpoints; no OAuth needed)
python -m reddit_poller

## Enabling Redis (optional, Upstash-friendly)
- By default the store is in-memory. Set `REDIS_URL` (or `UPSTASH_REDIS_URL`) to enable Redis via redis-py.
- If you only have the Upstash REST creds, set `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN`; the store will use the REST API.
- Key patterns and ops are documented in `documentation/db_design.md`.
```

## Running Tests

```bash
# Run all tests
pytest backend/tests -v

# Run specific test file
pytest backend/tests/test_ingestion.py -v

# Run with coverage
pytest backend/tests --cov=backend --cov-report=term-missing
```

## API Endpoints

### Health Check
- **GET** `/` - Returns service status

### User & Project Management
- **POST** `/users` - Create a new user
  - Body: `{"email": "user@example.com", "name": "User Name"}`
- **GET** `/projects?user_id=<uuid>` - List projects for a user
- **POST** `/projects` - Create a new project
  - Body: `{"name": "My Project", "user_id": "<uuid>"}`

### Ingestion Endpoints

All ingestion endpoints support optional `?project_id=<uuid>` query parameter for multi-tenant isolation.

- **POST** `/ingest/reddit?project_id=<uuid>` - Ingest Reddit feedback (called by poller)
- **POST** `/ingest/sentry?project_id=<uuid>` - Ingest Sentry error reports via webhook
- **POST** `/ingest/manual?project_id=<uuid>` - Manually submit feedback
  - Body: `{"text": "Bug description", "title": "Optional title"}`

### Feedback Management
- **GET** `/feedback?project_id=<uuid>` - List all feedback items with optional filters:
  - `source`: Filter by source (reddit, sentry, manual)
  - `cluster_id`: Filter by cluster
  - `limit` and `offset`: Pagination
- **GET** `/feedback/{item_id}?project_id=<uuid>` - Get specific feedback item
- **GET** `/stats?project_id=<uuid>` - Get aggregate statistics

### Clustering
- **GET** `/clusters?project_id=<uuid>` - List all issue clusters
- **GET** `/clusters/{cluster_id}?project_id=<uuid>` - Get cluster details with feedback items
- **POST** `/clusters/{cluster_id}/start_fix?project_id=<uuid>` - Trigger coding agent for a cluster

### Jobs (Coding Agent Tracking)
- **GET** `/jobs?project_id=<uuid>` - List all agent jobs
- **POST** `/jobs?project_id=<uuid>` - Create a new job
  - Body: `{"cluster_id": "cluster-id", "project_id": "<uuid>"}`
- **PATCH** `/jobs/{job_id}?project_id=<uuid>` - Update job status
  - Body: `{"status": "success", "pr_url": "https://...", "logs": "..."}`
- **GET** `/jobs/{job_id}?project_id=<uuid>` - Get job details
- **GET** `/clusters/{cluster_id}/jobs?project_id=<uuid>` - Get jobs for a cluster

### Reddit Configuration
- **GET** `/config/reddit/subreddits?project_id=<uuid>` - Get subreddit list for project
- **POST** `/config/reddit/subreddits?project_id=<uuid>` - Set subreddit list
  - Body: `{"subreddits": ["claudeai", "programming"]}`
- **POST** `/reddit/poll?project_id=<uuid>` - Trigger immediate poll

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST API URL (recommended) | _unset (in-memory)_ |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST API token | _unset (in-memory)_ |
| `REDIS_URL` / `UPSTASH_REDIS_URL` | Alternative Redis connection string (via redis-py) | _unset (in-memory)_ |
| `GEMINI_API_KEY` / `GOOGLE_GENERATIVE_AI_API_KEY` | Google Gemini API key for embeddings (required for clustering) | _unset_ |
| `REDDIT_SUBREDDITS` | Subreddit(s) to monitor (comma-separated). `REDDIT_SUBREDDIT` also supported. | `"all"` |
| `REDDIT_SORTS` | Listing sorts to pull (`new`, `hot`, `top`) | `"new"` |
| `REDDIT_POLL_INTERVAL_SECONDS` | How often to poll Reddit | `300` |
| `BACKEND_URL` | URL of the ingestion API (for reddit poller) | `http://localhost:8000` |
| `GITHUB_TOKEN` | GitHub personal access token (optional, for higher API limits) | _unset_ |
| `E2B_API_KEY` | E2B API key (required for `sandbox_kilo` runner) | _unset_ |
| `KILOCODE_TEMPLATE_NAME` | E2B template name for Kilo sandbox | _unset_ |
| `KILOCODE_TEMPLATE_ID` | E2B template ID (fallback when name not set) | `base` |

## Development Notes

- Storage: Defaults to in-memory for development; use Redis for production
- Testing: Follow TDD principles; write tests before implementation
- Code style: Black + Ruff formatting, comprehensive docstrings
- Multi-tenancy: All endpoints support optional `project_id` query parameter
- Clustering: Automatic on ingestion when Gemini API key is configured
- Error handling: Production-ready with comprehensive error responses

## Key Implementation Details

### Data Models
- `FeedbackItem`: Normalized feedback from any source (Reddit, Sentry, GitHub, manual)
- `IssueCluster`: Groups of semantically similar feedback items
- `AgentJob`: Tracks coding agent fix generation tasks
- `User` and `Project`: Multi-tenant user and project management

### Storage Layer (`store.py`)
- Redis-backed with Upstash REST API support
- In-memory fallback for development
- Key patterns documented in `documentation/db_design.md`
- Automatic JSON serialization/deserialization

### Clustering Algorithm
- Embeds feedback text using Gemini (`text-embedding-004`)
- Compares against existing clusters using cosine similarity
- Threshold: 0.75 for automatic cluster assignment
- Creates new cluster if no match found
- Generates AI summaries and titles for clusters
