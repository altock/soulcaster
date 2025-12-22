# Backup and Restore Strategy

This document defines the strategy for protecting data in the Soulcaster platform and restoring service in disaster scenarios.

## 1. Data Inventory

| Data Store | Type | Content | Criticality | Recovery RTO/RPO |
|------------|------|---------|-------------|------------------|
| **Upstash Redis** | Primary DB | User feedback, Clusters, Job history, Config. | **High** | RPO: 24h, RTO: 4h |
| **Upstash Vector** | Derived | Text embeddings for clustering. | **Medium** | RPO: N/A (Re-computable) |
| **GitHub** | Code | Source code, Issues, PRs. | **High** | Managed by GitHub |
| **Local Memory** | Cache | Fallback store (dev only). | Low | N/A |

## 2. Backup Strategy

### A. Redis (Primary Data)
- **Automated:** Rely on Upstash's daily automated backups (if enabled on paid plan).
- **Manual (Break-Glass):**
  - **Script:** `backend/scripts/backup_redis.py` (Proposed).
  - **Process:** Iterates over all keys (`SCAN`), serializes to JSON lines, saves to S3/Local.
  - **Frequency:** Ad-hoc before major migrations.

### B. Vector (Embeddings)
- **Strategy:** Treat as ephemeral/derivative.
- **Reasoning:** Embeddings can be re-generated from the raw `FeedbackItem` text stored in Redis.
- **Backup:** None required if Redis is secured.

## 3. Restore Procedures

### Scenario A: Accidental Data Deletion (Redis)
1. **Identify Scope:** Did we lose a specific project or everything?
2. **Restore Source:**
   - **Upstash Console:** Use "Restore Backup" feature to roll back to the previous day's snapshot.
   - **Manual Import:** If restoring from JSON dump, run `python backend/scripts/restore_redis.py <dump_file>`.
3. **Verify:** Check key counts and ensure the dashboard loads.

### Scenario B: Vector Index Corruption
1. **Symptom:** "Clustering failed" errors or zero results in vector search.
2. **Action:** Trigger a full re-index.
   - **Script:** `backend/scripts/reindex_vectors.py` (Proposed).
   - **Logic:**
     1. Flush Vector Index.
     2. Iterate all `FeedbackItem`s in Redis.
     3. Re-generate embeddings via Gemini API.
     4. Upsert to Upstash Vector.

### Scenario C: GitHub Connection Loss
1. **Symptom:** "Invalid Token" or 401/403 errors on Ingest/PR creation.
2. **Action:**
   - Rotate GitHub App private key or OAuth Client Secret.
   - Update `GITHUB_SECRET` / `GITHUB_TOKEN` in `.env` (Backend & Dashboard).
   - Redeploy services.

## 4. Disaster Recovery (Region Failure)
Since we rely on serverless providers (Vercel, Upstash, E2B), region failures are largely managed by them.
- **Upstash:** Check status page. If critical, contact support or switch region (requires restoring from backup).
- **Vercel:** Check status page. Multi-region deployment available on Enterprise.