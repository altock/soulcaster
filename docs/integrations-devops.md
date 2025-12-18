# Integrations DevOps Setup Guide

This guide covers how to configure each external data source integration, including API credentials, webhook setup, costs, and operational concerns.

---

## Quick Reference

| Integration | Setup Effort | Monthly Cost | Rate Limits | Auth Method |
|-------------|--------------|--------------|-------------|-------------|
| Datadog | Medium | Free (webhook) | None for webhooks | Webhook signature |
| PostHog | Low | Free tier available | 10k events/mo free | API key |
| Sentry | Low | Already configured | 10k events/mo free | Webhook signature |
| Splunk | High | Requires license | N/A (self-hosted) | Token auth |

---

## 1. Datadog Setup

### Prerequisites
- Datadog account with Admin access
- At least one monitor configured

### Step 1: Create Webhook Integration

1. Go to **Integrations → Webhooks**
2. Click **+ New**
3. Configure:
   - **Name**: `soulcaster`
   - **URL**: `https://your-backend.com/ingest/datadog/webhook?project_id=YOUR_PROJECT_ID`
   - **Payload**: Use default JSON or customize:
   ```json
   {
     "id": "$ID",
     "title": "$EVENT_TITLE",
     "body": "$EVENT_MSG",
     "alert_type": "$ALERT_TYPE",
     "priority": "$PRIORITY",
     "tags": "$TAGS",
     "date": "$DATE",
     "org": {"id": "$ORG_ID", "name": "$ORG_NAME"},
     "snapshot": "$SNAPSHOT"
   }
   ```
4. Save

### Step 2: Attach Webhook to Monitors

1. Edit each monitor you want to track
2. In **Notify your team** section, add: `@webhook-soulcaster`
3. Save monitor

### Step 3: Configure Environment Variables

```bash
# .env (backend)
DATADOG_WEBHOOK_SECRET=<optional-signing-secret>
```

### Operational Concerns

| Concern | Details |
|---------|---------|
| **Cost** | Webhooks are free. No API calls from Soulcaster to Datadog. |
| **Rate Limits** | No webhook rate limits. Alert storms can spike ingestion. |
| **Latency** | Webhooks fire within seconds of alert trigger. |
| **Reliability** | Datadog retries failed webhooks 3 times. |
| **Signature** | Optional HMAC verification. Set shared secret in webhook config. |

### Troubleshooting

```bash
# Test webhook locally
curl -X POST http://localhost:8000/ingest/datadog/webhook?project_id=test \
  -H "Content-Type: application/json" \
  -d '{"id":"123","title":"[Test] Alert","body":"Test alert","alert_type":"error","date":1705315800}'
```

---

## 2. PostHog Setup

### Prerequisites
- PostHog Cloud account or self-hosted instance
- Project with events flowing

### Option A: Webhook via Actions (Recommended)

1. Go to **Data Management → Actions**
2. Create new action for exceptions:
   - **Match events**: `$exception`
   - Or create custom action matching your error events
3. In **Action details**, enable **Webhook**:
   - **URL**: `https://your-backend.com/ingest/posthog/webhook?project_id=YOUR_PROJECT_ID`
   - **Method**: POST
   - **Headers**: `Content-Type: application/json`

### Option B: API Polling (for historical data)

1. Go to **Settings → Project → Project API Key**
2. Copy the project API key
3. Get your project ID from the URL: `app.posthog.com/project/YOUR_PROJECT_ID`

### Environment Variables

```bash
# .env (backend)
POSTHOG_API_KEY=phx_xxxxxxxxxxxxx          # Personal API key (for polling)
POSTHOG_PROJECT_ID=12345                    # Your project ID
POSTHOG_HOST=https://app.posthog.com       # Or self-hosted URL
```

### Redis Configuration

```bash
# Per-project config (set via API)
# POST /config/posthog/events?project_id=xxx
# Body: {"event_types": ["$exception", "$error", "custom_error"]}
```

### Operational Concerns

| Concern | Details |
|---------|---------|
| **Cost** | Free tier: 1M events/mo. Webhooks don't count against quota. |
| **Rate Limits** | API: 10 requests/second. Webhooks unlimited. |
| **Latency** | Webhooks: ~1s. Polling: depends on sync interval. |
| **Data Retention** | Free tier: 1 year. Affects historical sync. |
| **Session Replay** | Link preserved in metadata for debugging. |

### Troubleshooting

```bash
# Test webhook
curl -X POST http://localhost:8000/ingest/posthog/webhook?project_id=test \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "event": "$exception",
      "distinct_id": "user-123",
      "properties": {"$exception_message": "Test error"},
      "timestamp": "2024-01-15T10:30:00Z"
    }
  }'

# Test API polling (requires API key)
curl -X POST http://localhost:8000/ingest/posthog/sync?project_id=test
```

---

## 3. Sentry Setup (Enhanced)

### Current State
Basic Sentry integration exists. This enhances it with signature verification.

### Step 1: Configure Webhook

1. Go to **Settings → Developer Settings → Webhooks**
2. Or use Integration Platform:
   - **Settings → Integrations → Internal Integrations**
   - Create new internal integration
3. Add webhook:
   - **URL**: `https://your-backend.com/ingest/sentry?project_id=YOUR_PROJECT_ID`
   - **Events**: `issue`, `error`

### Step 2: Get Client Secret

1. After creating integration, copy the **Client Secret**
2. This is used for signature verification

### Environment Variables

```bash
# .env (backend)
SENTRY_WEBHOOK_SECRET=<client-secret>      # For signature verification
SENTRY_DSN=<optional>                       # Only if sending errors to Sentry
```

### Redis Configuration

```bash
# Per-project config
config:sentry:{project_id}:webhook_secret  → Client secret
config:sentry:{project_id}:environments    → ["production", "staging"]
config:sentry:{project_id}:levels          → ["error", "fatal"]
```

### Signature Verification

Sentry signs webhooks with HMAC-SHA256:

```python
import hmac
import hashlib

def verify_sentry_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
```

### Operational Concerns

| Concern | Details |
|---------|---------|
| **Cost** | Free: 5k errors/mo. Team: $26/mo for 50k. |
| **Rate Limits** | Webhooks: 100/minute per organization. |
| **Deduplication** | Sentry groups issues. Use `short_id` for dedup. |
| **Environments** | Filter by environment to reduce noise. |
| **Signature** | Required for production. Verify all webhooks. |

### Troubleshooting

```bash
# Test webhook (no signature)
curl -X POST http://localhost:8000/ingest/sentry?project_id=test \
  -H "Content-Type: application/json" \
  -d '{
    "action": "created",
    "data": {
      "issue": {"id": "123", "short_id": "PROJ-123"},
      "event": {"event_id": "abc", "title": "Test error"}
    }
  }'

# Verify existing integration
curl https://sentry.io/api/0/projects/{org}/{project}/hooks/ \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN"
```

---

## 4. Splunk Setup

### Prerequisites
- Splunk Enterprise or Splunk Cloud
- Admin access to configure alerts
- Network access from Splunk to your backend

### Step 1: Create Webhook Alert Action

1. Create or edit a saved search
2. Add alert action: **Webhook**
3. Configure:
   - **URL**: `https://your-backend.com/ingest/splunk/webhook?project_id=YOUR_PROJECT_ID`
   - **HTTP Method**: POST

### Step 2: Configure Authentication (Optional)

If using token auth:

1. Generate a random token: `openssl rand -hex 32`
2. Add to Splunk webhook URL as query param:
   - `https://backend.com/ingest/splunk/webhook?project_id=xxx&token=YOUR_TOKEN`
3. Configure backend to validate token

### Environment Variables

```bash
# .env (backend)
SPLUNK_WEBHOOK_TOKEN=<random-token>        # For basic auth
```

### Redis Configuration

```bash
# Per-project config
config:splunk:{project_id}:webhook_token   → Token for auth
config:splunk:{project_id}:searches        → ["Error Rate Alert", "Latency Spike"]
config:splunk:{project_id}:sourcetypes     → ["api_logs", "app_errors"]
```

### Splunk Webhook Payload

Default payload from saved search alert:

```json
{
  "result": {
    "_raw": "<raw log line>",
    "_time": "1705315800",
    "host": "server-1",
    "source": "/var/log/app.log",
    "sourcetype": "app_logs"
  },
  "sid": "scheduler__admin__search__xxx",
  "search_name": "API Errors > 10",
  "results_link": "https://splunk.internal/app/search?sid=..."
}
```

### Operational Concerns

| Concern | Details |
|---------|---------|
| **Cost** | Splunk license required. Webhooks free. |
| **Rate Limits** | Depends on Splunk deployment. Typically unlimited. |
| **Network** | Splunk must reach your backend (firewall rules). |
| **Payload Size** | Limited to single result. Use multi-value for more. |
| **Authentication** | No native signing. Use token in URL or header. |

### Self-Hosted Considerations

```bash
# If Splunk is on-prem and backend is cloud:
# Option 1: Expose webhook endpoint publicly with auth
# Option 2: Use Splunk HTTP Event Collector (HEC) reverse
# Option 3: Deploy worker inside network that forwards to cloud
```

### Troubleshooting

```bash
# Test webhook
curl -X POST "http://localhost:8000/ingest/splunk/webhook?project_id=test&token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "result": {"_raw": "ERROR: test failure", "_time": "1705315800"},
    "search_name": "Test Alert",
    "sid": "test-123"
  }'

# From Splunk, test webhook connectivity
| makeresults | eval test="hello" | sendalert webhook
```

---

## Environment Variable Summary

### Backend (.env)

```bash
# Existing
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
GEMINI_API_KEY=
GITHUB_TOKEN=

# Sentry (enhanced)
SENTRY_WEBHOOK_SECRET=<client-secret>

# Datadog
DATADOG_WEBHOOK_SECRET=<optional>

# PostHog
POSTHOG_API_KEY=phx_xxxxxxxxxxxxx
POSTHOG_PROJECT_ID=12345
POSTHOG_HOST=https://app.posthog.com

# Splunk
SPLUNK_WEBHOOK_TOKEN=<random-token>
```

### Dashboard (.env.local)

No additional variables needed. Dashboard proxies to backend.

---

## Webhook Security Checklist

- [ ] Use HTTPS for all webhook endpoints
- [ ] Verify signatures where supported (Sentry, Datadog)
- [ ] Use token auth for services without signing (Splunk)
- [ ] Rate limit webhook endpoints (100/min recommended)
- [ ] Log all webhook payloads for debugging (redact secrets)
- [ ] Set up alerting for webhook failures

---

## Monitoring & Alerting

### Recommended Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Webhook success rate | Application logs | < 95% |
| Ingestion latency | Application logs | > 5s p99 |
| Dedup hit rate | Redis metrics | Monitor for spikes |
| Clustering queue depth | Redis metrics | > 1000 pending |

### Health Check Endpoints

```bash
# Backend health
GET /health

# Per-integration status (future)
GET /integrations/status
```

---

## Cost Projections

### Free Tier Limits

| Service | Free Tier | Overage Cost |
|---------|-----------|--------------|
| Sentry | 5k errors/mo | $0.000290/event |
| PostHog | 1M events/mo | Pay-as-you-go |
| Datadog | Webhooks free | N/A |
| Splunk | Requires license | Varies |

### Upstash Costs (Storage)

| FeedbackItems/mo | Redis Storage | Vector Storage | Monthly Cost |
|------------------|---------------|----------------|--------------|
| 1,000 | ~10 MB | ~50 MB | ~$5 |
| 10,000 | ~100 MB | ~500 MB | ~$20 |
| 100,000 | ~1 GB | ~5 GB | ~$100 |

---

## Rollout Checklist

For each integration:

- [ ] Create environment variables in production
- [ ] Deploy backend with new endpoint
- [ ] Configure webhook in external service
- [ ] Send test event
- [ ] Verify FeedbackItem created
- [ ] Verify clustering works
- [ ] Enable for production events
- [ ] Monitor for 24h
- [ ] Document any issues
