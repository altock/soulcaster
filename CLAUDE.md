# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Soulcaster** is a feedback triage and automated fix generation system. It ingests bug reports from Reddit, Sentry, and GitHub issues, clusters similar feedback using embeddings, and triggers a coding agent to generate fixes and open PRs.

**Flow**: Reddit/Sentry/GitHub → Clustered Issues → Dashboard Triage → Coding Agent → GitHub PR

## Architecture

Three components sharing Upstash Redis:

1. **Backend** (`/backend`) - FastAPI service for ingestion, clustering, and agent orchestration
2. **Dashboard** (`/dashboard`) - Next.js 16 (App Router) web UI for triage and management

### Tech Stack

- **Backend**: FastAPI, Pydantic, redis-py, Upstash REST, Gemini embeddings, E2B sandboxes
- **Dashboard**: Next.js 16, TypeScript, Tailwind, NextAuth (GitHub OAuth), Prisma (PostgreSQL)
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

### Backend (from project root)

```bash
# Modern (recommended)
just dev-backend                  # Run with uv
just test-backend                 # Run tests
just install-backend              # Install dependencies

# Manual
cd backend && uv sync             # Install dependencies
cd backend && uv run uvicorn main:app --reload --port 8000
cd backend && uv run pytest -v    # All tests
```

### Dashboard (from `/dashboard`)

```bash
# Modern (recommended)
just dev-dashboard                # Run dev server
just test-dashboard               # Run tests
just install-dashboard            # Install dependencies

# Manual
npm install
npx prisma migrate dev            # Setup/migrate database
npx prisma generate               # Regenerate Prisma client
npm run dev                       # Development server (port 3000)
npm run build                     # Production build
npm run lint                      # ESLint
npm run format                    # Prettier
npm run type-check                # TypeScript check
npm test                          # Jest tests
```

## Key Files

**Backend**:
- `backend/main.py` - FastAPI routes (`/ingest/*`, `/clusters`, `/feedback`, `/jobs`, `/cluster-jobs`)
- `backend/store.py` - Redis/in-memory storage abstraction
- `backend/models.py` - Pydantic models (`FeedbackItem`, `IssueCluster`, `AgentJob`)

**Dashboard**:
- `dashboard/lib/vector.ts` - Vector DB-based clustering (recommended)
- `dashboard/lib/clustering.ts` - Legacy centroid-based clustering
- `dashboard/lib/redis.ts` - Upstash Redis client helpers
- `dashboard/app/api/clusters/run-vector/route.ts` - Vector clustering endpoint
- `dashboard/prisma/schema.prisma` - Database schema (auth, projects)

## Redis Data Model

```
feedback:{id}        - Hash: id, source, title, body, metadata, created_at, clustered
feedback:created     - Sorted set: all feedback IDs by timestamp
feedback:unclustered - Set: IDs pending clustering
cluster:{id}         - Hash: id, title, summary, status, centroid, issue_title
cluster:items:{id}   - Set: feedback IDs in cluster
clusters:all         - Set: all cluster IDs
job:{id}             - Hash: id, cluster_id, status, logs, created_at
```

## Clustering Algorithm (Vector-Based)

1. Generate embedding via Gemini API for `title + body`
2. Query Upstash Vector for similar feedback items (top-K ANN search)
3. If top match ≥ 0.72 threshold AND already clustered → join that cluster
4. If top matches ≥ 0.72 but unclustered → create new cluster with all similar items
5. If no matches above threshold → create new single-item cluster
6. Store embedding in Vector DB with cluster assignment metadata
7. Generate LLM summary for new/changed clusters

## Environment Variables

**Unified Configuration**: Use a single `.env` file in the project root for both backend AND dashboard.

```bash
# Copy .env.example to .env and fill in your values
cp .env.example .env

# Required variables (see .env.example for full documentation):
ENVIRONMENT=development                              # development | production
UPSTASH_REDIS_REST_URL=https://your-dev-redis.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-dev-redis-token
UPSTASH_VECTOR_REST_URL=https://your-dev-vector.upstash.io
UPSTASH_VECTOR_REST_TOKEN=your-dev-vector-token
GEMINI_API_KEY=your-gemini-api-key
GITHUB_ID=your-github-oauth-client-id              # GitHub OAuth for dashboard
GITHUB_SECRET=your-github-oauth-client-secret
GITHUB_TOKEN=ghp_your-personal-access-token        # For agent operations
E2B_API_KEY=your-e2b-api-key                       # E2B sandbox provisioning
KILOCODE_TEMPLATE_NAME=kilo-sandbox-v-0-1-dev
BLOB_READ_WRITE_TOKEN=your-vercel-blob-token       # Job log archival
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-nextauth-secret               # Generate: openssl rand -base64 32
DATABASE_URL=postgresql://user:password@localhost:5432/soulcaster
BACKEND_URL=http://localhost:8000
```

**Why unified .env?**
- Single source of truth for all credentials
- No duplicate configuration between backend/dashboard
- Next.js automatically reads from parent `.env` files
- Easier dev vs prod environment management
- Safety checks in `scripts/reset_dev_data.py` respect `ENVIRONMENT` variable

## API Endpoints

**Backend** (`:8000`):
- `POST /ingest/reddit|sentry|manual` - Ingest feedback
- `GET /feedback` - List feedback (`?source=`, `?limit=`, `?offset=`)
- `GET /clusters`, `GET /clusters/{id}` - List/detail clusters
- `POST /clusters/{id}/start_fix` - Mark cluster as "fixing"
- `POST /cluster-jobs` - Trigger backend clustering job
- `POST /jobs`, `PATCH /jobs/{id}` - Manage agent jobs

**Dashboard** (`:3000/api`):
- `POST /api/clusters/run-vector` - Run vector-based clustering
- `POST /api/clusters/cleanup` - Merge duplicate clusters

## GitHub Authentication

- Users sign in via GitHub OAuth (required)
- Access token stored in encrypted NextAuth session
- PRs created from user's account (not a bot)
- Scopes: `repo`, `read:user`
