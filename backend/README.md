# FeedbackAgent Backend - Data Ingestion Layer

This is the data ingestion layer for FeedbackAgent, built with FastAPI and following TDD principles.

## Features

- **Multi-source ingestion**: Reddit, Sentry, and manual text feedback
- **In-memory storage**: Simple dict-based storage for MVP (will be replaced with database)
- **Reddit polling**: Background service that reads subreddits via Reddit's public JSON feed (no OAuth)
- **Full test coverage**: Comprehensive test suite with edge cases

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

```bash
# Start the FastAPI server
cd backend
uvicorn main:app --reload

# Server will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

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

### Ingestion Endpoints

#### POST /ingest/reddit
Ingest feedback from Reddit (called by reddit_poller).

**Request Body**:
```json
{
  "id": "uuid",
  "source": "reddit",
  "external_id": "t3_12345",
  "title": "Bug found in feature X",
  "body": "Detailed description...",
  "metadata": {
    "subreddit": "programming",
    "permalink": "/r/programming/...",
    "author": "username"
  },
  "created_at": "2023-10-27T10:00:00Z"
}
```

#### POST /ingest/sentry
Ingest error reports from Sentry webhook.

**Request Body**: Standard Sentry webhook payload

#### POST /ingest/manual
Ingest manually submitted text feedback.

**Request Body**:
```json
{
  "text": "The login button doesn't work on mobile"
}
```

### Reddit Config
- **GET** `/config/reddit/subreddits` - Returns active subreddit list (Redis-backed; falls back to env/default).
- **POST** `/config/reddit/subreddits` - Set subreddit list globally. Body: `{"subreddits": ["claudeai", "yoursub"]}`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDDIT_SUBREDDITS` | Subreddit(s) to monitor (comma-separated). `REDDIT_SUBREDDIT` is also supported for backward compatibility. | `"all"` |
| `REDDIT_SORTS` | Listing sorts to pull (`new`, `hot`, `top`) | `"new"` |
| `REDDIT_POLL_INTERVAL_SECONDS` | How often to poll Reddit | `300` |
| `BACKEND_URL` | URL of the ingestion API | `http://localhost:8000` |
| `REDIS_URL` / `UPSTASH_REDIS_URL` | Redis connection string (enables Redis store) | _unset (in-memory)_ |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | Upstash REST credentials (used if Redis URL is not set) | _unset (in-memory)_ |

## Development Notes

- This is an MVP implementation with in-memory storage
- Follow TDD: write tests before implementation
- All code includes comprehensive docstrings
- Error handling implemented for production resilience

## Next Steps

From the task plan (tasks/data_ingestion.md):
- ✅ Environment & Project Structure
- ✅ Domain Models
- ✅ In-Memory Store
- ✅ API Endpoints (TDD)
- ✅ Reddit Poller (TDD)
- ✅ Integration Verification

Ready to integrate with the Brain layer (clustering and triage)!
