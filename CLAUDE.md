# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Soulcaster** is a feedback triage and automated fix generation system. It ingests bug reports from Reddit, Sentry, and GitHub issues, clusters similar feedback using embeddings, and can trigger a coding agent to generate fixes and open PRs.

**Flow**: Reddit/Sentry/GitHub → Clustered Issues → Dashboard Triage → Coding Agent → GitHub PR

## Architecture

Three components that share an Upstash Redis store:

1. **Backend** (`/backend`) - FastAPI service for ingestion and clustering
2. **Dashboard** (`/dashboard`) - Next.js web UI for triage and management
3. **Coding Agent** (`/coding-agent`) - Standalone script that fixes issues via Kilo CLI

### Tech Stack

- **Backend**: FastAPI, Pydantic, redis-py or Upstash REST
- **Dashboard**: Next.js 16 (App Router), TypeScript, Tailwind, `@google/genai` for embeddings
- **Storage**: Upstash Redis (or local Redis) + Upstash Vector for embeddings
- **Embeddings**: Gemini (`gemini-embedding-001`) for server-side clustering
- **Vector DB**: Upstash Vector for efficient similarity search (ANN)
- **LLM Summaries**: Gemini (`gemini-2.5-flash`) for cluster summaries

## Development Commands

### Backend (from project root)

```bash
pip install -r backend/requirements.txt

# Run API server
uvicorn backend.main:app --reload --port 8000

# Run Reddit poller (separate process)
python -m backend.reddit_poller

# Run all tests
pytest backend/tests -v

# Run single test file
pytest backend/tests/test_clusters.py -v

# Run specific test
pytest backend/tests/test_clusters.py::test_list_clusters -v
```

### Dashboard (from `/dashboard`)

```bash
npm install
npm run dev          # Development server (port 3000)
npm run build        # Production build
npm run lint         # ESLint
npm run format       # Prettier
npm run type-check   # TypeScript check
npm test             # Jest tests
npm run test:watch   # Jest watch mode
```

### Coding Agent

```bash
python coding-agent/fix_issue.py <github-issue-url> --job-id <optional-job-id>
```

Requires: `GH_TOKEN`, `GIT_USER_EMAIL`, `GIT_USER_NAME`, and either `GEMINI_API_KEY` or `MINIMAX_API_KEY`.

## Key Files

**Backend**:
- `backend/main.py` - FastAPI routes (`/ingest/*`, `/clusters`, `/feedback`, `/jobs`)
- `backend/store.py` - Redis/in-memory storage abstraction
- `backend/models.py` - Pydantic models (`FeedbackItem`, `IssueCluster`, `AgentJob`)
- `backend/reddit_poller.py` - Reddit ingestion via requests

**Dashboard**:
- `dashboard/lib/clustering.ts` - Legacy centroid-based clustering logic
- `dashboard/lib/vector.ts` - **Vector DB-based clustering** (recommended)
- `dashboard/lib/redis.ts` - Upstash Redis client helpers
- `dashboard/app/api/clusters/run/route.ts` - Legacy clustering endpoint
- `dashboard/app/api/clusters/run-vector/route.ts` - **Vector-based clustering endpoint** (recommended)
- `dashboard/app/clusters/page.tsx` - Cluster list UI

## Redis Data Model

```
feedback:{id}        - Hash: id, source, title, body, metadata, created_at, clustered
feedback:created     - Sorted set: all feedback IDs by timestamp
feedback:unclustered - Set: IDs pending clustering
cluster:{id}         - Hash: id, title, summary, status, centroid, issue_title, etc.
cluster:items:{id}   - Set: feedback IDs in cluster
clusters:all         - Set: all cluster IDs
job:{id}             - Hash: id, cluster_id, status, logs, created_at
```

## Clustering

### Vector-Based Clustering (Recommended)

See `docs/DESIGN_DECISIONS.md` for full rationale on threshold and architecture choices.

**Algorithm** (`lib/vector.ts`):
1. Generate embedding via Gemini API for `title + body`
2. Query Upstash Vector for similar feedback items (top-K ANN search)
3. If top match ≥ 0.72 threshold AND already clustered → join that cluster
4. If top matches ≥ 0.72 but unclustered → create new cluster with all similar items
5. If no matches above threshold → create new single-item cluster
6. Store embedding in Vector DB with cluster assignment metadata
7. Calculate cluster cohesion score (tight/moderate/loose)
8. Generate LLM summary for new/changed clusters

**Key exports** (`lib/vector.ts`):
- `VectorStore` - Upstash Vector client wrapper
- `clusterWithVectorDB()` - Single item clustering
- `processNewFeedbackWithVector()` - Full flow: embed → cluster → store
- `generateFeedbackEmbedding()` - Gemini embedding generation

### Legacy Centroid-Based Clustering

**Algorithm** (`lib/clustering.ts`):
1. Generate embeddings via Gemini API for `title + body`
2. Compare each embedding to existing cluster centroids using cosine similarity
3. If similarity ≥ 0.65: add to cluster, update centroid incrementally
4. Else: create new cluster
5. Generate LLM summary for changed clusters only

**Key classes**:
- `ClusteringBatch` - Optimized batch processing with change tracking
- `cosineSimilarity()`, `calculateCentroid()`, `findBestCluster()` - Pure functions

## Environment Variables

**Backend** (`.env` in project root):
```bash
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
REDDIT_SUBREDDITS=claudeai,programming  # optional
```

**Dashboard** (`.env.local` in `/dashboard`):
```bash
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
UPSTASH_VECTOR_REST_URL=   # For vector-based clustering
UPSTASH_VECTOR_REST_TOKEN= # Get from Upstash console
GEMINI_API_KEY=  # or GOOGLE_GENERATIVE_AI_API_KEY
GITHUB_ID=       # GitHub OAuth (optional)
GITHUB_SECRET=
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=
BACKEND_URL=http://localhost:8000
```

**Coding Agent**:
```bash
GH_TOKEN=
GIT_USER_EMAIL=
GIT_USER_NAME=
GEMINI_API_KEY=  # or MINIMAX_API_KEY
BACKEND_URL=     # for job status updates
```

## API Endpoints

**Backend** (`:8000`):
- `POST /ingest/reddit` - Ingest Reddit feedback
- `POST /ingest/sentry` - Ingest Sentry webhook
- `POST /ingest/manual` - Manual text submission
- `GET /feedback` - List feedback (supports `?source=`, `?limit=`, `?offset=`)
- `GET /clusters` - List all clusters
- `GET /clusters/{id}` - Cluster detail with feedback items
- `POST /clusters/{id}/start_fix` - Mark cluster as "fixing"
- `POST /admin/trigger-poll` - Manually trigger Reddit poll
- `GET/POST /config/reddit/subreddits` - Manage monitored subreddits
- `POST /jobs` - Create agent job
- `PATCH /jobs/{id}` - Update job status/logs

**Dashboard** (`:3000/api`):
- `POST /api/clusters/run` - Run legacy centroid-based clustering
- `POST /api/clusters/run-vector` - **Run vector-based clustering** (recommended, 0.82 threshold)
- `POST /api/clusters/cleanup` - Merge duplicate clusters by centroid similarity
- `POST /api/clusters/reset` - Clear all clusters (debugging)
- `POST /api/trigger-agent` - Trigger coding agent via ECS
# Upstash Redis (required)
UPSTASH_REDIS_REST_URL=https://your-instance.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-token-here

# GitHub OAuth (REQUIRED for beta)
# Create OAuth app at: https://github.com/settings/developers
# Authorization callback URL: http://localhost:3000/api/auth/callback/github
# Scopes requested: repo, read:user
GITHUB_ID=your-github-oauth-client-id
GITHUB_SECRET=your-github-oauth-client-secret

# NextAuth (REQUIRED)
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=generate-with-openssl-rand-base64-32

# Database (REQUIRED)
DATABASE_URL=postgresql://user:password@localhost:5432/soulcaster

# Backend API URL (REQUIRED)
BACKEND_URL=http://localhost:8000

# Reddit API (optional - for automated polling)
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=

# LLM Provider (for Gemini embeddings/clustering)
GEMINI_API_KEY=your-gemini-api-key
```

**Required for Backend** (create `.env` in project root):

```bash
# Redis (same as dashboard)
UPSTASH_REDIS_REST_URL=https://your-instance.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-token-here

# GitHub OAuth (same as dashboard)
GITHUB_ID=your-github-oauth-client-id
GITHUB_SECRET=your-github-oauth-client-secret

# LLM Provider (REQUIRED)
GEMINI_API_KEY=your-gemini-api-key

# E2B Sandbox (REQUIRED for coding agent)
E2B_API_KEY=your-e2b-api-key
KILOCODE_TEMPLATE_NAME=kilo-sandbox-v-0-1-dev

# Coding Agent Runner (default: sandbox_kilo)
CODING_AGENT_RUNNER=sandbox_kilo
```

**How GitHub Authentication Works**:
- Users MUST sign in with GitHub OAuth (required for all environments)
- Access token stored securely in NextAuth session (encrypted)
- Token passed to backend when creating PRs
- PRs created from user's account (e.g., @username)
- No fallback to personal access tokens - OAuth is required
- Future: GitHub App support for bot-based PRs (soulcaster[bot])

## Scope Guardrails (MVP Only)

**What we HAVE built (Dashboard):**
- ✅ Reddit feedback ingestion (manual submission via UI)
- ✅ Feedback list view with source filtering
- ✅ Embedding-based clustering with auto-run
- ✅ Cluster list and detail views
- ✅ Upstash Redis persistence
- ✅ Reddit subreddit configuration UI

**What we are NOT building:**
- No auth/permissions (hardcoded env vars only)
- No multi-repo support
- No automated Reddit polling (manual submission only)
- No coding agent / PR generation
- No robust retries/rate limiting
- No chat UI (click-to-fix only)
- No comprehensive test suite (manual verification)

## Known Limitations (Dashboard)

- Client-side embedding generation (loads Xenova model in browser)
- Simple heuristic summaries (no LLM summarization)
- Full-feedback clustering on each run (no incremental updates)
- No cluster merge/split UI
- No automatic PR merge or cluster closure
- Manual feedback submission only (no automated polling)

## Testing Strategy

Currently: Manual verification only

Future: Write tests for:
- Clustering logic (similarity thresholds, centroid updates)
- FeedbackItem normalization
- Redis data integrity
- API endpoint responses

## Post-Hackathon Future Work

**DO NOT implement these during MVP:**
- Automated Reddit polling with PRAW
- Coding agent with PR generation (PyGithub)
- LLM-based cluster summarization
- Incremental clustering (only process new items)
- Cluster merge/split UI controls
- GitHub OAuth and multi-repo support
- Comprehensive observability and rate limiting
