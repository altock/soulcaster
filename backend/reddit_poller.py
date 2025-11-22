import praw
import requests
import os
from datetime import datetime, timezone

from uuid import uuid4

KEYWORDS = ["bug", "broken", "error", "crash", "doesn't work", "feature"]

def process_submission(submission):
    title = submission.title
    body = submission.selftext
    text_to_check = (title + " " + body).lower()
    
    if any(keyword in text_to_check for keyword in KEYWORDS):
        payload = {
            "id": str(uuid4()),
            "source": "reddit",
            "external_id": str(submission.id),
            "title": title,
            "body": body[:10000], # Truncate if too long
            "metadata": {
                "subreddit": str(submission.subreddit),
                "permalink": submission.permalink,
                "author": str(submission.author),
                "created_utc": submission.created_utc
            },
            "created_at": datetime.fromtimestamp(submission.created_utc, timezone.utc).isoformat()
        }
        try:
            requests.post("http://localhost:8000/ingest/reddit", json=payload)
        except Exception as e:
            print(f"Failed to post to backend: {e}")

def poll_reddit():
    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent="FeedbackAgent/0.1"
    )
    subreddit_name = os.getenv("REDDIT_SUBREDDIT", "all")
    subreddit = reddit.subreddit(subreddit_name)
    
    print(f"Polling r/{subreddit_name}...")
    for submission in subreddit.stream.submissions(skip_existing=True):
        process_submission(submission)
