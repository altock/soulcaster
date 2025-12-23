# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Soulcaster** is a feedback triage and automated fix generation system. It ingests bug reports from Reddit, Sentry, GitHub issues, Splunk, DataDog, and PostHog, clusters similar feedback using embeddings, and triggers a coding agent to generate fixes and open PRs.

**Flow**: Feedback Sources → Clustered Issues → Dashboard Triage → Coding Agent → GitHub PR

## Architecture

Two main components sharing Upstash Redis:

1. **Backend** (`/backend`) - FastAPI service for ingestion, clustering, and agent orchestration
2. **Dashboard** (`/dashboard`) - Next.js 15 (App Router) web UI for triage and management

### Tech Stack

- **Backend**: FastAPI, Pydantic, redis-py, Upstash REST, Gemini embeddings, E2B sandboxes
- **Dashboard**: Next.js, TypeScript, Tailwind, NextAuth (GitHub OAuth), Prisma (PostgreSQL)
- **Storage**: Upstash Redis + Upstash Vector for embeddings
- **LLM**: Gemini (`gemini-embedding-001` for embeddings, `gemini-2.5-flash` for summaries)

## Development Commands

**Quick Start:**
```bash
just                # Show all available commands
just install        # Install all dependencies
just dev-backend    # Run backend (localhost:8000)
just dev-dashboard  # Run dashboard (localhost:3000)
```

### Backend

```bash
just dev-backend                  # Run with uv
just test-backend                 # Run all tests
just install-backend              # Install dependencies

# Run specific test file
cd backend && uv run pytest tests/test_store.py -v

# Run single test by name
cd backend && uv run pytest -v -k "test_add_feedback_item"

# Manual commands
cd backend && uv sync
cd backend && uv run uvicorn main:app --reload --port 8000
```

### Dashboard

```bash
just dev-dashboard                # Run dev server
just test-dashboard               # Run all tests
just install-dashboard            # Install dependencies

# Manual commands
cd dashboard && npm install
cd dashboard && npx prisma migrate dev    # Setup/migrate database
cd dashboard && npx prisma generate       # Regenerate Prisma client
cd dashboard && npm run dev
cd dashboard && npm run build
cd dashboard && npm run lint
cd dashboard && npm run type-check
```

## Key Files

**Backend**:
- `backend/main.py` - FastAPI routes (all `/ingest/*`, `/clusters`, `/feedback`, `/jobs`, `/cluster-jobs`)
- `backend/store.py` - Redis/in-memory storage abstraction
- `backend/models.py` - Pydantic models (`FeedbackItem`, `IssueCluster`, `AgentJob`, `ClusterJob`)
- `backend/clustering_runner.py` - Async clustering job runner with Redis locks
- `backend/clustering.py` - Embedding generation and similarity calculations
- `backend/vector_store.py` - Upstash Vector wrapper for ANN search
- `backend/limits.py` - Free tier quota limits (1500 issues, 20 jobs per user)

**Dashboard**:
- `dashboard/lib/auth.ts` - NextAuth configuration
- `dashboard/lib/github.ts` - GitHub API client
- `dashboard/app/api/clusters/*/route.ts` - Cluster management endpoints
- `dashboard/prisma/schema.prisma` - Database schema (auth, projects)

## Redis Data Model

```
feedback:{id}              - Hash: feedback item data
feedback:created:{proj}    - Sorted set: feedback IDs by timestamp for project
feedback:unclustered:{proj}- Set: IDs pending clustering
cluster:{id}               - Hash: cluster data
cluster:items:{id}         - Set: feedback IDs in cluster
clusters:all:{proj}        - Set: all cluster IDs for project
job:{id}                   - Hash: agent job data
cluster_job:{id}           - Hash: clustering job data
```

## Clustering Algorithm

Uses in-memory batch clustering to avoid Upstash Vector eventual consistency issues:

1. Generate embeddings via Gemini API for `title + body`
2. Query Upstash Vector for existing similar items (read-only)
3. In-memory clustering: compare batch items against each other + existing DB items
4. If similarity ≥ 0.72 AND existing cluster → join that cluster
5. If similar batch items → group into new cluster
6. Batch upsert all items to Vector DB at once (single write)
7. Persist clusters to Redis

## Free Tier Limits

- **1500 max feedback items** per user (across all projects)
- **20 successful coding jobs** per user
- Enforced in `backend/limits.py`, checked at ingestion and job creation

## Environment Variables

Use a single `.env` file in the project root:

```bash
cp .env.example .env

# Required:
ENVIRONMENT=development
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
UPSTASH_VECTOR_REST_URL=
UPSTASH_VECTOR_REST_TOKEN=
GEMINI_API_KEY=
GITHUB_ID=                    # GitHub OAuth client ID
GITHUB_SECRET=                # GitHub OAuth client secret
E2B_API_KEY=
KILOCODE_TEMPLATE_NAME=kilo-sandbox-v-0-1-dev
BLOB_READ_WRITE_TOKEN=
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=              # Generate: openssl rand -base64 32
DATABASE_URL=postgresql://...
BACKEND_URL=http://localhost:8000
```

## API Endpoints

**Backend** (`:8000`):
- `POST /ingest/reddit` - Reddit posts
- `POST /ingest/sentry` - Sentry webhooks
- `POST /ingest/splunk/webhook` - Splunk alerts
- `POST /ingest/datadog/webhook` - DataDog alerts
- `POST /ingest/posthog/webhook` - PostHog events
- `POST /ingest/manual` - Manual feedback
- `POST /ingest/github/sync` - Sync GitHub issues for project
- `GET /feedback` - List feedback (`?project_id=`, `?source=`, `?limit=`)
- `GET /clusters`, `GET /clusters/{id}` - List/detail clusters
- `POST /clusters/{id}/start_fix` - Trigger fix generation
- `POST /cluster-jobs` - Trigger backend clustering job
- `GET /cluster-jobs/{id}` - Get clustering job status
- `POST /jobs`, `GET /jobs/{id}`, `PATCH /jobs/{id}` - Agent job management

**Dashboard** (`:3000/api`):
- `POST /api/clusters/cleanup` - Merge duplicate clusters
- `GET /api/clusters/jobs` - List clustering jobs
- `POST /api/ingest/github/sync` - Trigger GitHub sync
- `GET /api/feedback` - Proxy to backend

## GitHub Authentication

- Users sign in via GitHub OAuth (required)
- Access token stored in encrypted NextAuth session
- PRs created from user's account (not a bot)
- Scopes: `repo`, `read:user`

## Testing Data Reset

```bash
just dev-reset        # Reset dev data (with confirmation)
just dev-reset-force  # Reset without confirmation
```

Only works when `ENVIRONMENT=development` to prevent accidental prod data loss.
