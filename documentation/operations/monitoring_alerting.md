# Monitoring and Alerting Plan

This document outlines the baseline strategy for observing the Soulcaster platform (Dashboard, Backend, Agent Runner) and alerting on critical issues.

## 1. Objectives
- **Detect** outages and performance degradation before users do.
- **Diagnose** root causes quickly using logs and traces.
- **Recover** automatically where possible, or page the right human.

## 2. Key Metrics (Golden Signals)

We focus on the "Four Golden Signals" for our primary services.

### A. Backend (FastAPI)
- **Latency:** P95 response time for `/ingest/*` and `/cluster-jobs/*`.
- **Traffic:** Requests per second (RPS) grouped by endpoint.
- **Errors:** HTTP 5xx rate; Unhandled exceptions (Sentry).
- **Saturation:** Worker utilization (uvicorn workers), Reddit API rate limit remaining.

### B. Dashboard (Next.js)
- **Latency:** Page load time (LCP), API route duration.
- **Errors:** 5xx on `/api/*` routes, client-side React crashes.
- **Traffic:** Active users, session duration.

### C. Coding Agent (E2B Sandbox / Runner)
- **Job Success Rate:** Percentage of jobs ending in `success` vs `failed`.
- **Job Duration:** Time from `pending` to `success`.
- **E2B Saturation:** Concurrent sandbox usage vs limits.
- **Failure Categories:** "PR creation failed", "Sandbox timeout", "Linter error".

### D. Storage (Upstash Redis & Vector)
- **Connectivity:** Connection error rate.
- **Latency:** Command duration.
- **Saturation:** Storage usage vs plan limits.

## 3. Tooling Stack

| Component | Tool | Purpose |
|-----------|------|---------|
| **Application Errors** | **Sentry** | Exception tracking (Backend Python + Dashboard JS). |
| **Logs** | **Vercel / AWS / Stdout** | Structured logging for debugging. |
| **Metrics** | **Datadog** (Proposed) | Aggregated metrics for latency/traffic (via client integration). |
| **Product Analytics** | **PostHog** | User flows and feature usage (e.g., "Generate Fix" clicks). |
| **Infrastructure** | **Upstash Console** | Redis/Vector health and usage monitoring. |

## 4. Alerting Rules (Baseline)

### Priority 1 (Page Immediate)
These indicate the system is unusable for a significant portion of users.
- **Backend Down:** `/health` probe failing for > 2 minutes.
- **High Error Rate:** Backend or Dashboard 5xx rate > 5% for 5 minutes.
- **Agent Failure Spike:** > 50% of agent jobs failing in the last 15 minutes.
- **Redis Connection Loss:** Persistent connection failures to Upstash.

### Priority 2 (Notify / Ticket)
These indicate degradation or impending issues.
- **High Latency:** P95 API latency > 2s for 15 minutes.
- **Reddit Poller Lag:** No new items ingested for > 2 hours (indicates stuck poller).
- **E2B Quota Warning:** Approaching 80% of monthly sandbox hours.
- **Sandbox Timeout:** Single job running longer than 15 minutes.

## 5. Implementation Status

### Existing
- [x] Sentry SDK in Backend (`backend/sentry_client.py`).
- [x] Basic Logging in Backend (standard python logging).
- [x] Job Status Tracking in Redis (`job:{id}`).

### To Be Implemented
- [ ] **Health Check Endpoint:** Add `/health` to FastAPI backend.
- [ ] **Structured Logging:** Configure JSON logging for production.
- [ ] **Metric Export:** Wire up Datadog or similar for latency histograms.
- [ ] **Poller Heartbeat:** Mechanism to track if the Reddit poller loop is alive.