from typing import Dict, List
from uuid import UUID
from .models import FeedbackItem

# In-memory storage
feedback_items: Dict[UUID, FeedbackItem] = {}

def add_feedback_item(item: FeedbackItem) -> FeedbackItem:
    feedback_items[item.id] = item
    return item

def get_feedback_item(item_id: UUID) -> FeedbackItem | None:
    return feedback_items.get(item_id)

def get_all_feedback_items() -> List[FeedbackItem]:
    return list(feedback_items.values())

def clear_feedback_items():
    feedback_items.clear()
