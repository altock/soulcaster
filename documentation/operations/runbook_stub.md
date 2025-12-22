# Operational Runbook (Stub)

This is a living document for on-call engineers handling common alerts and incidents.

## 1. Incident Management Process

1. **Acknowledge:** Mark the alert as "Investigating" in PagerDuty/Slack.
2. **Triaging:** Determine severity.
   - **SEV-1 (Critical):** Service down, data loss, or inability to create PRs.
   - **SEV-2 (Major):** High latency, specific feature broken (e.g., Reddit ingest).
   - **SEV-3 (Minor):** Non-urgent bug or cosmetic issue.
3. **Mitigate:** Focus on restoring service first, root cause second.
4. **Communicate:** Update stakeholders every 30 mins for SEV-1.

## 2. Common Alerts & Playbooks

### Alert: "Backend Health Check Failed"
- **Severity:** SEV-1
- **Symptoms:** Dashboard shows "Network Error", API returns 502/503.
- **Investigation:**
  1. Check Backend Logs: `tail` logs or check AWS/Vercel log stream.
  2. Look for "Connection Refused" (DB down) or OOM kills.
  3. Verify Redis connection.
- **Mitigation:**
  - Restart Backend Service.
  - Check Upstash Status Page.

### Alert: "Agent Job Failure Spike"
- **Severity:** SEV-2
- **Symptoms:** > 50% of jobs failing.
- **Investigation:**
  1. Check specific failure reasons in Dashboard -> Cluster -> Jobs.
  2. Common causes:
     - `GH_TOKEN` expired or rate-limited.
     - E2B Sandbox template broken (e.g., `apt-get` failure).
     - OpenAI/Gemini API outage.
- **Mitigation:**
  - If rate-limited: Rotate token or wait.
  - If API outage: Switch LLM provider in env vars if possible.

### Alert: "Reddit Poller Lag"
- **Severity:** SEV-3
- **Symptoms:** No new items for > 2 hours.
- **Investigation:**
  1. Check `backend/reddit_poller.py` logs.
  2. Verify Reddit API access (public JSON endpoints).
- **Mitigation:**
  - Restart the poller process.
  - Check if subreddit became private/banned.

## 3. Useful Commands

**Restart Backend (Local):**
```bash
pkill uvicorn
uvicorn backend.main:app --reload
```

**Check Redis Keys (Production):**
```bash
# Requires UPSTASH_REDIS_REST_URL and TOKEN
curl $UPSTASH_REDIS_REST_URL/dbsize -H "Authorization: Bearer $UPSTASH_REDIS_REST_TOKEN"
```

**Manually Trigger GitHub Sync:**
```bash
curl -X POST "http://localhost:8000/ingest/github/sync/owner/repo?project_id=..."