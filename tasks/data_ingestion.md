# Data Ingestion Plan

This plan outlines the steps to implement the data ingestion layer for the FeedbackAgent, following a Test Driven Development (TDD) approach.

## 1. Environment & Project Structure
- [ ] Create `backend` directory
- [ ] Create `backend/requirements.txt` with dependencies:
    - `fastapi`
    - `uvicorn`
    - `pydantic`
    - `praw` (Reddit)
    - `pytest`
    - `httpx` (for testing)
- [ ] Install dependencies
- [ ] Create `backend/__init__.py`

## 2. Domain Models
- [ ] Create `backend/models.py`
- [ ] Define `FeedbackItem` Pydantic model:
    - `id`: UUID
    - `source`: Literal["reddit", "sentry", "manual"]
    - `external_id`: Optional[str]
    - `title`: str
    - `body`: str
    - `metadata`: Dict
    - `created_at`: datetime

## 3. In-Memory Store
- [ ] Create `backend/store.py`
- [ ] Implement a simple in-memory store (list or dict) to hold `FeedbackItem`s.
- [ ] Add helper functions to add and retrieve items.

## 4. API Endpoints (TDD)
### 4.1 Reddit Ingestion
- [ ] Create `backend/tests/test_ingestion.py`
- [ ] **Test**: Write a test case for `POST /ingest/reddit` with a valid payload. Expect 200 OK and item in store.
- [ ] **Implement**: Create `backend/main.py` and implement `POST /ingest/reddit`.
- [ ] **Refactor**: Ensure code is clean.

### 4.2 Sentry Ingestion
- [ ] **Test**: Add a test case to `backend/tests/test_ingestion.py` for `POST /ingest/sentry` with a sample Sentry webhook payload.
- [ ] **Implement**: Add `POST /ingest/sentry` endpoint to `backend/main.py`. Parse Sentry JSON to `FeedbackItem`.
- [ ] **Refactor**: Shared normalization logic if needed.

### 4.3 Manual/Text Blob Ingestion
- [ ] **Test**: Add a test case for `POST /ingest/manual` (or generic text).
- [ ] **Implement**: Add endpoint for raw text input.

## 5. Reddit Poller (TDD)
- [ ] Create `backend/tests/test_reddit_poller.py`
- [ ] **Test**: Mock PRAW `reddit.subreddit(...).stream.submissions` and `comments`. Verify that:
    - Keywords are filtered.
    - Data is normalized to `FeedbackItem` structure.
    - `POST` request is sent to the API.
- [ ] **Implement**: Create `backend/reddit_poller.py`.
    - Setup PRAW with env vars.
    - Implement polling loop.
    - Implement filtering logic.
    - Implement API posting.

## 6. Integration Verification
- [ ] Run all tests: `pytest backend/tests`
- [ ] Manual verification (optional): Run server and curl endpoints.
