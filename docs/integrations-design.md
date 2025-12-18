# Integrations Design Spec

## Overview

This document specifies the next wave of integrations for Soulcaster: **Datadog**, **PostHog**, **Sentry** (enhanced), and **Splunk**. Each integration follows the established patterns from the existing GitHub and Reddit integrations.

---

## Integration Architecture

All integrations follow a unified pattern:

```text
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   External API  │────▶│  Ingestion Route │────▶│  FeedbackItem   │
│   (webhook/poll)│     │  POST /ingest/*  │     │  (normalized)   │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                        ┌──────────────────┐              │
                        │  Vector Cluster  │◀─────────────┘
                        │  (Gemini + UVec) │
                        └──────────────────┘
```

### Common Interface

Each integration implements:

1. **Ingestion endpoint**: `POST /ingest/{source}` or webhook handler
2. **Normalization function**: `{source}_event_to_feedback_item(event) -> FeedbackItem`
3. **Deduplication**: Using `(source, external_id, project_id)` key
4. **Configuration**: Per-project settings stored in Redis
5. **Tests**: Following TDD - tests written before implementation

---

## 1. Datadog Integration

### Purpose
Ingest Datadog alerts (monitors, APM errors, log alerts) as feedback items for clustering and automated fixes.

### Data Flow

```text
Datadog Monitor Alert
       │
       ▼
POST /ingest/datadog/webhook
       │
       ▼
Validate payload signature (optional)
       │
       ▼
Normalize to FeedbackItem
       │
       ▼
Dedup by (alert_id + timestamp bucket)
       │
       ▼
Store & trigger clustering
```

### Webhook Payload (Datadog → Soulcaster)

Datadog sends webhooks with configurable templates. We'll use the default JSON payload:

```json
{
  "id": "1234567890",
  "title": "[Triggered] CPU > 90% on web-server-1",
  "body": "Monitor 'High CPU Usage' triggered...",
  "alert_type": "error",
  "priority": "normal",
  "tags": ["env:production", "service:api"],
  "date": 1680000000,
  "org": {"id": "abc123", "name": "Acme Corp"},
  "snapshot": "https://p.datadoghq.com/..."
}
```

### FeedbackItem Mapping

```python
def datadog_event_to_feedback_item(event: dict, project_id: str) -> FeedbackItem:
    return FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="datadog",
        external_id=f"{event['id']}-{event['date'] // 3600}",  # Dedup per hour
        title=event.get("title", "Datadog Alert"),
        body=event.get("body", ""),
        raw_text=f"{event.get('title', '')} {event.get('body', '')}",
        metadata={
            "alert_type": event.get("alert_type"),
            "priority": event.get("priority"),
            "tags": event.get("tags", []),
            "org_id": event.get("org", {}).get("id"),
            "snapshot_url": event.get("snapshot"),
        },
        created_at=datetime.fromtimestamp(event.get("date", time.time())),
    )
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ingest/datadog/webhook` | POST | Receive Datadog webhook alerts |
| `/config/datadog/monitors` | GET/POST | Configure which monitors to track |

### Configuration (Redis)

```text
config:datadog:{project_id}:webhook_secret  → Optional signing secret
config:datadog:{project_id}:monitors        → List of monitor IDs to track (or "*" for all)
config:datadog:{project_id}:tags_filter     → Tags to include/exclude
```

### TDD Test Cases

```python
# test_datadog_integration.py

def test_datadog_webhook_creates_feedback_item():
    """Webhook payload creates a new FeedbackItem with correct mapping."""

def test_datadog_webhook_deduplicates_by_hour():
    """Same alert within an hour creates only one FeedbackItem."""

def test_datadog_webhook_rejects_invalid_signature():
    """Invalid signature returns 401."""

def test_datadog_tags_stored_in_metadata():
    """Tags from alert are preserved in metadata."""

def test_datadog_monitor_filter_applied():
    """Only configured monitors create feedback items."""
```

---

## 2. PostHog Integration

### Purpose
Ingest PostHog session replay errors, exception events, and action triggers as feedback items.

### Data Flow

PostHog supports webhooks via **Actions** or direct API polling for events:

```text
PostHog Action Webhook  ─────┐
                              ▼
                   POST /ingest/posthog/webhook
                              │
                              ▼
PostHog Events API ────▶ Poll /ingest/posthog/sync
                              │
                              ▼
                     Normalize to FeedbackItem
```

### Webhook Payload (PostHog Action)

```json
{
  "hook": {"id": "...", "event": "action_performed"},
  "data": {
    "event": "$exception",
    "distinct_id": "user-123",
    "properties": {
      "$exception_message": "TypeError: Cannot read property 'foo' of undefined",
      "$exception_stack_trace_raw": "...",
      "$session_id": "session-abc",
      "$current_url": "https://app.example.com/dashboard"
    },
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### FeedbackItem Mapping

```python
def posthog_event_to_feedback_item(event: dict, project_id: str) -> FeedbackItem:
    props = event.get("properties", {})
    exception_msg = props.get("$exception_message", "")
    stack_trace = props.get("$exception_stack_trace_raw", "")

    return FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="posthog",
        external_id=f"{event.get('uuid', event.get('distinct_id'))}-{event.get('timestamp', '')}",
        title=exception_msg[:200] or f"PostHog: {event.get('event', 'Unknown')}",
        body=f"{exception_msg}\n\n{stack_trace}",
        raw_text=f"{exception_msg} {stack_trace}",
        metadata={
            "event_type": event.get("event"),
            "distinct_id": event.get("distinct_id"),
            "session_id": props.get("$session_id"),
            "current_url": props.get("$current_url"),
            "browser": props.get("$browser"),
            "os": props.get("$os"),
        },
        created_at=datetime.fromisoformat(event.get("timestamp", datetime.now().isoformat())),
    )
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ingest/posthog/webhook` | POST | Receive PostHog action webhooks |
| `/ingest/posthog/sync` | POST | Pull events from PostHog API |
| `/config/posthog/events` | GET/POST | Configure which events to track |

### Configuration (Redis)

```text
config:posthog:{project_id}:api_key         → PostHog personal API key
config:posthog:{project_id}:project_id      → PostHog project ID
config:posthog:{project_id}:event_types     → List: ["$exception", "$error", ...]
config:posthog:{project_id}:last_synced     → ISO timestamp
```

### TDD Test Cases

```python
# test_posthog_integration.py

def test_posthog_webhook_creates_feedback_item():
    """Webhook payload creates FeedbackItem with exception details."""

def test_posthog_exception_extracts_stack_trace():
    """Stack trace is preserved in body."""

def test_posthog_sync_fetches_new_events():
    """Sync pulls events since last_synced timestamp."""

def test_posthog_event_type_filter():
    """Only configured event types are ingested."""

def test_posthog_session_id_in_metadata():
    """Session replay ID is preserved for linking."""
```

---

## 3. Sentry Integration (Enhanced)

### Current State
Basic webhook handling exists in `backend/main.py`. This enhancement adds:
- Webhook signature verification
- Issue grouping awareness
- Stack trace normalization
- Source map support

### Enhanced Data Flow

```text
Sentry Issue Webhook
       │
       ▼
POST /ingest/sentry (existing)
       │
       ▼
Verify signature (NEW)
       │
       ▼
Extract grouped issue ID (NEW)
       │
       ▼
Normalize stack trace (NEW)
       │
       ▼
FeedbackItem with enriched metadata
```

### Enhanced Webhook Handling

```python
def verify_sentry_signature(request: Request, secret: str) -> bool:
    """Verify Sentry webhook signature using HMAC-SHA256."""
    signature = request.headers.get("sentry-hook-signature")
    body = await request.body()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)

def sentry_event_to_feedback_item(event: dict, project_id: str) -> FeedbackItem:
    # Enhanced: Use issue short_id for better deduplication
    issue_id = event.get("data", {}).get("issue", {}).get("short_id")
    event_id = event.get("data", {}).get("event", {}).get("event_id")

    # Enhanced: Extract normalized stack trace
    stack_trace = extract_sentry_stacktrace(event)

    return FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="sentry",
        external_id=issue_id or event_id,  # Prefer issue grouping
        title=extract_sentry_title(event),
        body=extract_sentry_body(event),
        raw_text=f"{extract_sentry_title(event)} {stack_trace}",
        metadata={
            "issue_id": issue_id,
            "event_id": event_id,
            "level": event.get("level"),
            "platform": event.get("platform"),
            "release": event.get("release"),
            "environment": event.get("environment"),
            "tags": event.get("tags", {}),
            "stack_trace": stack_trace,
        },
        created_at=datetime.now(),
    )
```

### Configuration (Redis)

```text
config:sentry:{project_id}:webhook_secret   → Client secret for verification
config:sentry:{project_id}:environments     → List of envs to track ["production", "staging"]
config:sentry:{project_id}:levels           → List of levels ["error", "fatal"]
```

### TDD Test Cases

```python
# test_sentry_enhanced.py

def test_sentry_signature_verification():
    """Valid signature passes, invalid rejects with 401."""

def test_sentry_uses_issue_short_id_for_dedup():
    """Multiple events for same issue create one FeedbackItem."""

def test_sentry_stack_trace_normalized():
    """Stack frames are extracted and formatted."""

def test_sentry_environment_filter():
    """Only configured environments are ingested."""

def test_sentry_level_filter():
    """Only configured levels (error/fatal) are ingested."""
```

---

## 4. Splunk Integration

### Purpose
Ingest Splunk alerts from saved searches and real-time alerts as feedback items.

### Data Flow

```text
Splunk Saved Search Alert
       │
       ▼
POST /ingest/splunk/webhook
       │
       ▼
Parse alert payload
       │
       ▼
Normalize to FeedbackItem
       │
       ▼
Store & trigger clustering
```

### Webhook Payload (Splunk Alert Action)

Splunk's webhook action sends:

```json
{
  "result": {
    "_raw": "2024-01-15 10:30:00 ERROR [api] Request failed: connection timeout",
    "_time": "1705315800",
    "host": "web-server-1",
    "source": "/var/log/api.log",
    "sourcetype": "api_logs"
  },
  "sid": "scheduler__admin__search__1705315800",
  "search_name": "API Error Rate > 5%",
  "app": "search",
  "owner": "admin",
  "results_link": "https://splunk.example.com/app/search?sid=..."
}
```

### FeedbackItem Mapping

```python
def splunk_alert_to_feedback_item(alert: dict, project_id: str) -> FeedbackItem:
    result = alert.get("result", {})
    search_name = alert.get("search_name", "Splunk Alert")
    raw_log = result.get("_raw", "")

    return FeedbackItem(
        id=uuid4(),
        project_id=project_id,
        source="splunk",
        external_id=alert.get("sid", str(uuid4())),
        title=f"[Splunk] {search_name}",
        body=raw_log,
        raw_text=f"{search_name} {raw_log}",
        metadata={
            "search_name": search_name,
            "sid": alert.get("sid"),
            "host": result.get("host"),
            "source": result.get("source"),
            "sourcetype": result.get("sourcetype"),
            "results_link": alert.get("results_link"),
            "app": alert.get("app"),
        },
        created_at=datetime.fromtimestamp(int(result.get("_time", time.time()))),
    )
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ingest/splunk/webhook` | POST | Receive Splunk alert webhooks |
| `/config/splunk/searches` | GET/POST | Configure which saved searches to track |

### Configuration (Redis)

```text
config:splunk:{project_id}:webhook_token    → Token for basic auth
config:splunk:{project_id}:searches         → List of saved search names to track
config:splunk:{project_id}:sourcetypes      → Sourcetypes to include
```

### TDD Test Cases

```python
# test_splunk_integration.py

def test_splunk_webhook_creates_feedback_item():
    """Alert payload creates FeedbackItem with log data."""

def test_splunk_search_name_in_title():
    """Search name is prefixed to title."""

def test_splunk_raw_log_preserved():
    """Raw log line is preserved in body."""

def test_splunk_results_link_in_metadata():
    """Splunk results link is preserved for drill-down."""

def test_splunk_search_filter():
    """Only configured saved searches are ingested."""
```

---

## Implementation Order

Each integration will be developed in a separate git worktree following TDD:

| Order | Integration | Complexity | Dependencies |
|-------|-------------|------------|--------------|
| 1 | Sentry Enhanced | Low | Existing code to refactor |
| 2 | Datadog | Medium | New webhook handler |
| 3 | PostHog | Medium | Webhook + optional polling |
| 4 | Splunk | Medium | New webhook handler |

### Worktree Strategy

```bash
# Create worktrees for parallel development
git worktree add ../soulcaster-sentry-enhanced -b integration/sentry-enhanced
git worktree add ../soulcaster-datadog -b integration/datadog
git worktree add ../soulcaster-posthog -b integration/posthog
git worktree add ../soulcaster-splunk -b integration/splunk
```

---

## Shared Infrastructure

### Source Type Enum

Update `backend/models.py`:

```python
class FeedbackSource(str, Enum):
    REDDIT = "reddit"
    SENTRY = "sentry"
    GITHUB = "github"
    MANUAL = "manual"
    DATADOG = "datadog"
    POSTHOG = "posthog"
    SPLUNK = "splunk"
```

**Note**: The actual implementation uses `Literal['reddit', 'sentry', 'manual', 'github', 'splunk', 'posthog', 'datadog']` instead of an enum class. Literals are simpler and integrate better with Pydantic validation, providing the same type safety without the additional complexity of enum classes.

### Generic Webhook Handler

```python
# backend/webhooks.py

class WebhookHandler:
    """Base class for webhook integrations."""

    def __init__(self, source: str, secret_key: Optional[str] = None):
        self.source = source
        self.secret_key = secret_key

    async def verify_signature(self, request: Request) -> bool:
        """Override in subclass for signature verification."""
        return True

    async def parse_payload(self, request: Request) -> dict:
        """Parse and validate webhook payload."""
        return await request.json()

    @abstractmethod
    def to_feedback_item(self, payload: dict, project_id: str) -> FeedbackItem:
        """Convert webhook payload to FeedbackItem."""
        pass
```

---

## Dashboard Updates

### Integration Settings Page

Add `/settings/integrations` page with:

- Toggle for each integration (enabled/disabled)
- Configuration fields per integration
- Webhook URL display with copy button
- Test webhook button

### Integration Status Dashboard

Add to main dashboard:

- Integration health indicators
- Last sync timestamp per source
- Event count by source (24h rolling)

---

## Success Criteria

For each integration:

1. All TDD test cases pass
2. Webhook receives real data from service
3. FeedbackItems appear in dashboard
4. Clustering groups similar errors correctly
5. No duplicate items for same underlying issue
6. Configuration persists across restarts
