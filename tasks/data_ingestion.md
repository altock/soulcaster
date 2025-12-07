# Data Ingestion Plan

This plan outlines the steps to implement the data ingestion layer for the FeedbackAgent, following a Test Driven Development (TDD) approach.

## 1. Environment & Project Structure
- [x] Create `backend` directory  
- [x] Create `backend/requirements.txt` with dependencies:  
    - `fastapi`
    - `uvicorn`
    - `pydantic`
    - `praw` (Reddit)
    - `pytest`
    - `httpx` (for testing)
- [x] Install dependencies  
 
- [x] Create `backend/__init__.py`  
 

## 2. Domain Models
- [x] Create `backend/models.py`  
- [x] Define `FeedbackItem` Pydantic model:  
    - `id`: UUID
    - `source`: Literal["reddit", "sentry", "manual"]
    - `external_id`: Optional[str]
    - `title`: str
    - `body`: str
    - `metadata`: Dict
    - `created_at`: datetime

## 3. In-Memory Store
- [x] Create `backend/store.py`  
- [x] Implement a simple in-memory store (list or dict) to hold `FeedbackItem`s.  
- [x] Add helper functions to add and retrieve items.  

## 4. API Endpoints (TDD)
### 4.1 Reddit Ingestion
- [x] Create `backend/tests/test_ingestion.py`  
- [x] **Test**: Write a test case for `POST /ingest/reddit` with a valid payload. Expect 200 OK and item in store.  
- [x] **Implement**: Create `backend/main.py` and implement `POST /ingest/reddit`.  
- [x] **Refactor**: Ensure code is clean.  

### 4.2 Sentry Ingestion
- [x] **Test**: Add a test case to `backend/tests/test_ingestion.py` for `POST /ingest/sentry` with a sample Sentry webhook payload.  
- [x] **Implement**: Add `POST /ingest/sentry` endpoint to `backend/main.py`. Parse Sentry JSON to `FeedbackItem`.  
- [x] **Refactor**: Shared normalization logic if needed.  

### 4.3 Manual/Text Blob Ingestion
- [x] **Test**: Add a test case for `POST /ingest/manual` (or generic text).  
- [x] **Implement**: Add endpoint for raw text input.  

## 5. Reddit Poller (TDD)
- [x] Create `backend/tests/test_reddit_poller.py`  
- [~] **Test**: Mock PRAW `reddit.subreddit(...).stream.submissions` and `comments`. Verify that:  
  _Partially done – tests mock HTTP JSON listings instead of PRAW streams, matching the current JSON-based poller design._
    - Keywords are filtered.
    - Data is normalized to `FeedbackItem` structure.
    - `POST` request is sent to the API.
- [x] **Implement**: Create `backend/reddit_poller.py`.  
  _Done – a JSON-based poller replaced the original PRAW design and handles throttling, backoff, normalization, and API posting._
    - Setup PRAW with env vars.  
      _Superseded – no PRAW; env is used for JSON polling config instead._
    - Implement polling loop.  
      _Done – `run_forever` and helpers call `poll_once` on an interval._
    - Implement filtering logic.  
      _Done – posts are deduped and normalized; keyword filtering is simplified compared to the original PRAW concept._
    - Implement API posting.  
      _Done – poller posts to `/ingest/reddit` or uses an in-process ingest callback for admin triggers._

## 6. Integration Verification
- [~] Run all tests: `pytest backend/tests`  
  _Partially done – tests are present and used during development; this task reflects a recurring validation step rather than a one-time deliverable._
- [~] Manual verification (optional): Run server and curl endpoints.  
  _Partially done – manual verification has been performed in practice, but not rigorously tracked as a formal checklist item._
