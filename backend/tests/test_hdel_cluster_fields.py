"""Test for PR #151: Fix stale error messages in job clusters.

This test verifies that when a cluster has a field set to None,
the RedisStore properly deletes that field from the Redis hash
instead of leaving stale values.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from models import IssueCluster


class TestHdelClusterFields:
    """Test that None-valued fields are properly deleted from Redis."""

    def test_upstash_rest_client_hdel_method(self):
        """Test that UpstashRESTClient.hdel method works correctly."""
        from store import UpstashRESTClient

        # Create client with mock
        with patch.object(UpstashRESTClient, '_cmd') as mock_cmd:
            mock_cmd.return_value = 1  # Simulates successful deletion
            client = UpstashRESTClient("http://fake-url", "fake-token")

            # Test hdel with fields
            result = client.hdel("test_key", "field1", "field2")

            mock_cmd.assert_called_once_with("HDEL", "test_key", "field1", "field2")
            assert result == 1

    def test_upstash_rest_client_hdel_empty_fields(self):
        """Test that hdel returns 0 when no fields are provided."""
        from store import UpstashRESTClient

        client = UpstashRESTClient.__new__(UpstashRESTClient)
        # Test with no fields - should return 0 without calling _cmd
        result = client.hdel("test_key")
        assert result == 0

    def test_redis_store_hdel_helper(self):
        """Test that RedisStore._hdel properly delegates to the client."""
        from store import RedisStore

        # Test with Upstash REST mode
        mock_client = MagicMock()
        store = RedisStore.__new__(RedisStore)
        store.mode = "upstash"
        store.client = mock_client

        store._hdel("test_key", "field1", "field2")

        mock_client.hdel.assert_called_once_with("test_key", "field1", "field2")

    def test_redis_store_hdel_with_redis_mode(self):
        """Test that _hdel works in redis mode too."""
        from store import RedisStore

        mock_client = MagicMock()
        store = RedisStore.__new__(RedisStore)
        store.mode = "redis"
        store.client = mock_client

        store._hdel("test_key", "field1", "field2")

        mock_client.hdel.assert_called_once_with("test_key", "field1", "field2")

    def test_add_cluster_clears_none_fields(self):
        """Test that add_cluster deletes fields that are None in the cluster model.

        This is the key test for PR #151 - when a cluster's error_message is set to None
        (e.g., after a successful job), the old error_message should be deleted from Redis.
        """
        from store import RedisStore

        # Create a mock store
        mock_client = MagicMock()
        mock_client.hgetall.return_value = {}

        store = RedisStore.__new__(RedisStore)
        store.mode = "upstash"
        store.client = mock_client

        # Create a cluster with error_message set to None (simulating a successful job)
        now = datetime.now(timezone.utc)
        cluster = IssueCluster(
            id=str(uuid4()),
            project_id="test-project",
            title="Test Cluster",
            summary="Test summary",
            feedback_ids=["f1", "f2"],
            status="fixed",
            created_at=now,
            updated_at=now,
            error_message=None,  # This should trigger hdel
            github_pr_url="https://github.com/test/repo/pull/1",
        )

        # Call add_cluster
        store.add_cluster(cluster)

        # Verify that hdel was called for error_message (which is None)
        hdel_calls = [call for call in mock_client.hdel.call_args_list]
        assert len(hdel_calls) > 0, "hdel should be called for None fields"

        # Check that error_message was in the deleted fields
        deleted_fields = []
        for call in hdel_calls:
            deleted_fields.extend(call[0][1:])  # Skip the key, get the fields

        assert "error_message" in deleted_fields, "error_message should be deleted when None"

    def test_stale_error_message_cleared_on_success(self):
        """Integration-style test: verify error_message is cleared after success.

        Scenario:
        1. A cluster has error_message = "Connection failed"
        2. A new job succeeds and updates the cluster with error_message = None
        3. The old error_message should be deleted from Redis
        """
        from store import RedisStore

        mock_client = MagicMock()
        mock_client.hgetall.return_value = {}

        store = RedisStore.__new__(RedisStore)
        store.mode = "upstash"
        store.client = mock_client

        now = datetime.now(timezone.utc)
        project_id = "test-project"
        cluster_id = str(uuid4())

        # First, save cluster with an error
        cluster_with_error = IssueCluster(
            id=cluster_id,
            project_id=project_id,
            title="Test Cluster",
            summary="Test summary",
            feedback_ids=[],
            status="failed",
            created_at=now,
            updated_at=now,
            error_message="Connection failed",
        )
        store.add_cluster(cluster_with_error)

        # Verify hset was called with error_message
        hset_call = mock_client.hset.call_args
        assert "error_message" in hset_call[0][1], "error_message should be set"

        # Reset mock
        mock_client.reset_mock()

        # Now update cluster with success (error_message = None)
        cluster_success = IssueCluster(
            id=cluster_id,
            project_id=project_id,
            title="Test Cluster",
            summary="Test summary",
            feedback_ids=[],
            status="fixed",
            created_at=now,
            updated_at=now,
            error_message=None,  # Error cleared
            github_pr_url="https://github.com/test/repo/pull/1",
        )
        store.add_cluster(cluster_success)

        # Verify hdel was called to remove error_message
        hdel_calls = mock_client.hdel.call_args_list
        assert len(hdel_calls) > 0, "hdel should be called to clear error_message"

        all_deleted_fields = []
        for call in hdel_calls:
            all_deleted_fields.extend(call[0][1:])

        assert "error_message" in all_deleted_fields, \
            "error_message should be deleted when cluster is updated with None"
