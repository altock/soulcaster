from datetime import datetime
from typing import Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel

class FeedbackItem(BaseModel):
    id: UUID
    source: Literal["reddit", "sentry", "manual"]
    external_id: Optional[str] = None
    title: str
    body: str
    metadata: Dict = {}
    created_at: datetime
