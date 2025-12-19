# Soulcaster Productionization Design (Product Hunt beta)

## Goal and guardrails
- Ship a resilient “good enough” loop for Product Hunt/early users while keeping costs and complexity low.
- Preserve hackathon speed but remove single points of failure, tighten data contracts, and reduce trust surface for tokens.
- Bias to managed services (Vercel, Upstash, ECS Fargate) and small-footprint code changes; defer deep re-architecture until traction.

## Current snapshot (as built in hackathon)
- **Ingestion API (backend/main.py)**: FastAPI with Reddit/Sentry/manual ingest, naive source-based clustering, cluster/job endpoints, optional Redis (backend/store.py) or in-memory store. Reddit poller (`backend/reddit_poller.py`) pushes normalized posts to `/ingest/reddit`.
- **Dashboard + clustering (dashboard/)**: Next.js app on Vercel; reads/writes Redis directly (`dashboard/lib/redis.ts`). Manual feedback goes straight to Redis. Clustering runs inside Next API routes using Gemini embeddings/summaries (`dashboard/lib/clustering.ts`, `/api/clusters/run`), producing cluster hashes/sets in Redis. UI shows clusters/feedback and can trigger fixes.
- **Agent trigger/runner**: Next API `/api/trigger-agent` starts an ECS Fargate task that runs the Python coding agent (`coding-agent/fix_issue.py`), which shells out to `gh` + Kilocode and optionally updates backend job status via `/jobs/{id}`.
- **Data store**: Upstash Redis (documented in `documentation/db_design.md`) holds feedback, clusters, config. Backend can also use Redis via redis-py or Upstash REST; otherwise falls back to in-memory (non-durable).
- **Observability/security**: Minimal logging, no auth, secrets via env vars, no audit trail. Tests exist only for backend ingestion/poller and some dashboard clustering utilities.

## Gaps and risks
- **Split-brain logic**: Clustering lives in Next/Node with Gemini; backend also auto-clusters by source. Data contracts diverge between Python models and TS types; dashboard bypasses backend for most reads/writes.
- **Durability**: In-memory fallback loses data; Redis has no backup/TTL strategy; no migrations or schema validation. No dead-lettering for failed clustering/agent runs.
- **Access and safety**: No auth; dashboard and APIs are open to the internet. Tokens (GitHub, AWS, Gemini) are long-lived with broad scope; no per-user isolation.
- **Reliability**: Background work is ad-hoc (manual poll trigger, no scheduler), limited error handling/retries/rate limits. Agent runtime depends on local `gh`/kilocode behavior and shelling out inside Fargate.
- **Observability**: No tracing/metrics; logs scattered across FastAPI, Next API routes, and Fargate tasks. Hard to correlate a feedback item → cluster → PR.
- **Platform fit**: Frontend does Redis writes; backend cluster endpoints and dashboard cluster endpoints may drift. No CI/CD gates, lint/format not enforced in pipelines.

## Target architecture (lean, PH-ready)
- **Single data API**: Make FastAPI the authoritative read/write surface for feedback, clusters, jobs, and config. Dashboard becomes a thin client hitting the API; remove direct Redis writes from Next. Keep Redis as primary store for now to stay serverless-friendly, but harden schema and idempotency.
- **Background workers**:
  - *Ingestion*: Keep Reddit poller as a scheduled task (Render/Cloud Run cron or ECS scheduled task) writing to the API (not Redis directly).
  - *Clustering*: Move Gemini embedding + summarization into a Python or Node worker invoked via queue/cron (e.g., Redis queue or lightweight SQS). Persist clustering results through the API/store to avoid split logic.
  - *Agent*: Keep Fargate on-demand tasks; create jobs via backend (`/jobs`) and stream logs/status back to the store.
- **Store**: Standardize on Redis schema from `documentation/db_design.md`, add backups/export, and enforce idempotent writes (dedupe keys, status transitions). Add a minimal Postgres later only for audit/logs if traction appears.
- **Security and auth**: Basic token-based auth or Vercel middleware for dashboard/API. Scope GitHub tokens to a sandbox repo; keep AWS creds in Secrets Manager. Add signed webhooks for Sentry when enabled.
- **Deploy**:
  - FastAPI on Render/Railway/Fly with health checks and autosleep disabled during launches.
  - Next on Vercel (read-only, calls backend).
  - Redis Upstash (prod vs staging instances).
  - Fargate task definition with Secrets Manager refs and CloudWatch logs.
- **Observability**: Structured logs with request IDs across services; minimal metrics (ingest rate, clustering latency, PR success/fail) via OpenTelemetry-lite or a hosted collector (Axiom/Grafana Cloud). Dead-letter queue for failed clustering/agent jobs.

## Proposed data flow (target)
1. Reddit poller/Sentry webhook/manual form → FastAPI `/ingest/*` → Redis (dedup by external_id).
2. Scheduler triggers clustering worker → embeds + summarizes → updates clusters/status in Redis via API → emits log/metric.
3. Dashboard fetches `/clusters` and `/clusters/{id}` from FastAPI only; user triggers “start fix” → backend creates job + kicks ECS task (or returns issue URL if already in PR).
4. Agent runs in Fargate → updates `/jobs/{id}` → on success backend updates cluster (status, PR URL); dashboard polls job/cluster.

## Phased path
- **Phase 0 (stabilize hack)**: Add env validation, rate limiting on ingest, dedupe enforcement, align Redis schemas between backend and Next, and add basic auth headers. Keep existing flows.
- **Phase 1 (Product Hunt launch)**: Route all dashboard reads/writes through FastAPI; run clustering via backend worker/cron; add ECS task health/log piping; introduce request IDs + central log sink; document ops runbooks.
- **Phase 2 (post-traction)**: Add Postgres for history/audit, multi-tenant auth, GitHub OAuth, stronger CI (lint/tests), and richer observability.

## Decisions needed
- **LLM stack**: Keep Gemini for embeddings/summaries? Choose generation model for agent (Gemini vs Claude/OpenAI) with budget limits and fallbacks.
- **Queueing/scheduling**: Redis streams vs SQS vs serverless cron for clustering and agent triggers.
- **Persistence**: Stick with Redis-only for launch or add a minimal Postgres for audit/metrics now.
- **Auth**: Simple shared token vs Vercel auth vs GitHub OAuth; how to gate agent triggers.
- **Hosting**: Render/Railway/Fly for FastAPI; confirm Vercel + Upstash regions to minimize latency.
- **GitHub scope**: Sandbox repo vs user-provided; branch naming and TTL for stale branches.
- **Failure policy**: How to surface and retry failed clustering/agent runs; what gets dropped vs retried.
