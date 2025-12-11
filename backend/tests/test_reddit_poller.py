import unittest
from unittest.mock import MagicMock, patch

import requests

from reddit_poller import RedditPoller, fetch_reddit_posts


def make_response(json_payload=None, status=200, headers=None):
    """Helper to build a mock requests.Response."""
    response = MagicMock()
    response.status_code = status
    response.headers = headers or {}
    response.json.return_value = json_payload or {"data": {"children": []}}
    if status >= 400 and status not in (429, 403):
        response.raise_for_status.side_effect = requests.HTTPError(f"{status} error")
    else:
        response.raise_for_status.return_value = None
    return response


class TestRedditPoller(unittest.TestCase):
    def test_fetch_reddit_posts_normalizes_and_dedupes(self):
        session = MagicMock()
        payload = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "Bug in the app",
                            "selftext": "It crashes on launch",
                            "url": "https://example.com",
                            "author": "user1",
                            "created_utc": 1698400800.0,
                            "score": 10,
                            "num_comments": 2,
                            "subreddit": "testsub",
                            "permalink": "/r/testsub/comments/abc123/bug/",
                        }
                    }
                ]
            }
        }
        session.get.side_effect = [
            make_response(payload, headers={"ETag": "etag-a"}),
            make_response(payload, headers={"ETag": "etag-b"}),
        ]

        poller = RedditPoller(session=session, sleep_fn=lambda _: None, sorts=["new", "hot"])
        posts = poller.fetch_reddit_posts(["testsub"])

        assert session.get.call_count == 2  # one per sort
        assert len(posts) == 1  # duplicate id filtered
        post = posts[0]
        assert post["id"] == "abc123"
        assert post["subreddit"] == "testsub"
        assert post["title"] == "Bug in the app"

    def test_backoff_on_rate_limit(self):
        session = MagicMock()
        sleep = MagicMock()
        payload = {"data": {"children": []}}
        session.get.side_effect = [
            make_response(payload, status=429),
            make_response(payload, status=200),
        ]

        poller = RedditPoller(session=session, sleep_fn=sleep)
        poller.fetch_reddit_posts(["testsub"])

        assert session.get.call_count == 2  # retried after 429
        assert sleep.call_count >= 1

    @patch("reddit_poller.requests.post")
    def test_poll_once_posts_sent_to_backend(self, mock_post):
        session = MagicMock()
        payload = {
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "Bug in the app",
                            "selftext": "It crashes on launch",
                            "url": "https://example.com",
                            "author": "user1",
                            "created_utc": 1698400800.0,
                            "score": 10,
                            "num_comments": 2,
                            "subreddit": "feedback",
                            "permalink": "/r/feedback/comments/abc123/bug/",
                        }
                    }
                ]
            }
        }
        session.get.return_value = make_response(payload)
        mock_post.return_value = make_response({}, status=200)

        poller = RedditPoller(session=session, sleep_fn=lambda _: None)
        poller.poll_once(["feedback"], backend_url="http://localhost:8000")

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0].endswith("/ingest/reddit")
        body = kwargs["json"]
        assert body["source"] == "reddit"
        assert body["external_id"] == "abc123"
        assert body["metadata"]["subreddit"] == "feedback"


class TestModuleHelpers(unittest.TestCase):
    @patch("reddit_poller.requests.Session.get")
    def test_fetch_reddit_posts_helper_uses_defaults(self, mock_get):
        mock_get.return_value = make_response({"data": {"children": []}})
        posts = fetch_reddit_posts(["nosub"])
        assert isinstance(posts, list)


if __name__ == "__main__":
    unittest.main()
