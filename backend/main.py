from fastapi import FastAPI
from pydantic import BaseModel
from .models import FeedbackItem
from .store import add_feedback_item

app = FastAPI()

from uuid import uuid4
from datetime import datetime, timezone

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/ingest/reddit")
def ingest_reddit(item: FeedbackItem):
    add_feedback_item(item)
    return {"status": "ok"}

@app.post("/ingest/sentry")
def ingest_sentry(payload: dict):
    event_id = payload.get("event_id")
    title = payload.get("message") or "Sentry Issue"
    
    # Construct body from exception
    body = ""
    exception = payload.get("exception", {}).get("values", [])
    if exception:
        exc = exception[0]
        exc_type = exc.get("type", "Error")
        exc_value = exc.get("value", "")
        body += f"{exc_type}: {exc_value}\n\nStacktrace:\n"
        for frame in exc.get("stacktrace", {}).get("frames", [])[:3]:
            body += f"  {frame.get('filename')}:{frame.get('lineno')}\n"
    
    item = FeedbackItem(
        id=uuid4(),
        source="sentry",
        external_id=event_id,
        title=title,
        body=body,
        metadata=payload,
        created_at=datetime.now(timezone.utc)
    )
    add_feedback_item(item)
    return {"status": "ok"}

class ManualIngestRequest(BaseModel):
    text: str

@app.post("/ingest/manual")
def ingest_manual(request: ManualIngestRequest):
    item = FeedbackItem(
        id=uuid4(),
        source="manual",
        title=request.text[:80],
        body=request.text,
        metadata={},
        created_at=datetime.now(timezone.utc)
    )
    add_feedback_item(item)
    return {"status": "ok"}
