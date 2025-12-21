"""Tests for E2B sandbox blob storage archival integration."""

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from dotenv import load_dotenv

# Load .env file for real integration tests
load_dotenv()

from models import AgentJob, IssueCluster
from store import add_cluster, add_job, clear_clusters, clear_jobs, get_job, update_job
import job_logs_manager


def setup_function():
    """Clear state before each test."""
    clear_clusters()
    clear_jobs()


def teardown_function():
    """Clear job logs after each test."""
    # Clear any lingering logs
    pass


def _create_test_fixtures(project_id: str):
    """Create test cluster and job fixtures."""
    now = datetime.now(timezone.utc)

    cluster = IssueCluster(
        id=str(uuid4()),
        project_id=project_id,
        title="Test Cluster",
        summary="Test Summary",
        feedback_ids=[],
        status="new",
        github_repo_url="https://github.com/test/repo",
        created_at=now,
        updated_at=now,
    )
    add_cluster(cluster)

    job = AgentJob(
        id=uuid4(),
        project_id=project_id,
        cluster_id=cluster.id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    add_job(job)

    return cluster, job


class TestSandboxBlobArchival:
    """Tests for _archive_logs_to_blob in SandboxKilocodeRunner."""

    @pytest.mark.asyncio
    async def test_archive_logs_success(self, project_context):
        """Test successful log archival to Blob storage."""
        from agent_runner.sandbox import SandboxKilocodeRunner

        pid = project_context["project_id"]
        cluster, job = _create_test_fixtures(pid)

        # Add logs to memory
        job_logs_manager.append_log(job.id, "Log line 1\n")
        job_logs_manager.append_log(job.id, "Log line 2\n")

        expected_blob_url = f"https://blob.vercel-storage.com/logs/{job.id}.txt"

        runner = SandboxKilocodeRunner()

        with patch("agent_runner.sandbox.upload_job_logs_to_blob") as mock_upload:
            with patch("agent_runner.sandbox.update_job") as mock_update:
                mock_upload.return_value = expected_blob_url

                result = await runner._archive_logs_to_blob(job.id)

                assert result is True
                mock_upload.assert_called_once()
                # Verify logs were concatenated correctly
                call_args = mock_upload.call_args[0]
                assert call_args[0] == job.id
                assert "Log line 1" in call_args[1]
                assert "Log line 2" in call_args[1]

                # Verify job was updated with blob_url
                mock_update.assert_called_once()
                update_call_kwargs = mock_update.call_args[1]
                assert update_call_kwargs["blob_url"] == expected_blob_url

        # Verify logs were cleared from memory
        assert job_logs_manager.get_logs(job.id) == []

    @pytest.mark.asyncio
    async def test_archive_logs_no_logs_in_memory(self, project_context):
        """Test archival when no logs exist in memory."""
        from agent_runner.sandbox import SandboxKilocodeRunner

        pid = project_context["project_id"]
        cluster, job = _create_test_fixtures(pid)

        runner = SandboxKilocodeRunner()

        with patch("agent_runner.sandbox.upload_job_logs_to_blob") as mock_upload:
            result = await runner._archive_logs_to_blob(job.id)

            assert result is False
            mock_upload.assert_not_called()

    @pytest.mark.asyncio
    async def test_archive_logs_upload_failure(self, project_context):
        """Test archival when Blob upload fails."""
        from agent_runner.sandbox import SandboxKilocodeRunner

        pid = project_context["project_id"]
        cluster, job = _create_test_fixtures(pid)

        # Add logs to memory
        job_logs_manager.append_log(job.id, "Test log\n")

        runner = SandboxKilocodeRunner()

        with patch("agent_runner.sandbox.upload_job_logs_to_blob") as mock_upload:
            mock_upload.side_effect = Exception("Blob upload failed")

            result = await runner._archive_logs_to_blob(job.id)

            assert result is False

        # Logs should still be in memory after failed archival
        logs = job_logs_manager.get_logs(job.id)
        assert len(logs) > 0

        # Cleanup
        job_logs_manager.clear_logs(job.id)

    @pytest.mark.asyncio
    async def test_archive_logs_update_job_failure(self, project_context):
        """Test archival when job update fails after upload."""
        from agent_runner.sandbox import SandboxKilocodeRunner

        pid = project_context["project_id"]
        cluster, job = _create_test_fixtures(pid)

        # Add logs to memory
        job_logs_manager.append_log(job.id, "Test log\n")

        runner = SandboxKilocodeRunner()

        with patch("agent_runner.sandbox.upload_job_logs_to_blob") as mock_upload:
            with patch("agent_runner.sandbox.update_job") as mock_update:
                mock_upload.return_value = "https://blob.example.com/test.txt"
                mock_update.side_effect = Exception("Database error")

                result = await runner._archive_logs_to_blob(job.id)

                assert result is False

        # Cleanup
        job_logs_manager.clear_logs(job.id)

    @pytest.mark.asyncio
    async def test_archive_logs_with_unicode_content(self, project_context):
        """Test archival with unicode characters in logs."""
        from agent_runner.sandbox import SandboxKilocodeRunner

        pid = project_context["project_id"]
        cluster, job = _create_test_fixtures(pid)

        # Add logs with unicode
        job_logs_manager.append_log(job.id, "Starting fix...\n")
        job_logs_manager.append_log(job.id, "Fixed bug in fünction\n")
        job_logs_manager.append_log(job.id, "Success! \n")

        runner = SandboxKilocodeRunner()

        with patch("agent_runner.sandbox.upload_job_logs_to_blob") as mock_upload:
            with patch("agent_runner.sandbox.update_job"):
                mock_upload.return_value = "https://blob.example.com/test.txt"

                result = await runner._archive_logs_to_blob(job.id)

                assert result is True
                # Verify unicode content was preserved
                call_args = mock_upload.call_args[0]
                assert "fünction" in call_args[1]
                assert "" in call_args[1]


class TestSandboxJobCompletionWithBlob:
    """Tests for full job completion flow including blob archival."""

    @pytest.mark.asyncio
    async def test_successful_job_archives_logs(self, project_context):
        """Test that a successful sandbox job archives logs to Blob."""
        from agent_runner.sandbox import SandboxKilocodeRunner

        pid = project_context["project_id"]
        cluster, job = _create_test_fixtures(pid)

        runner = SandboxKilocodeRunner()
        expected_blob_url = f"https://blob.vercel-storage.com/logs/{job.id}.txt"

        # Mock the sandbox and all its dependencies
        mock_sandbox = AsyncMock()
        mock_sandbox.sandbox_id = "test-sandbox-123"
        mock_sandbox.kill = AsyncMock(return_value=True)

        mock_proc = MagicMock()
        mock_proc.exit_code = 0

        # Mock sandbox.commands.run to add logs and return success
        async def mock_run(*args, **kwargs):
            # Simulate agent writing logs
            on_stdout = kwargs.get("on_stdout")
            if on_stdout:
                on_stdout("Agent starting...\n")
                on_stdout("Work complete.\n")
            return mock_proc

        mock_sandbox.commands.run = mock_run
        mock_sandbox.files.write = MagicMock()

        with patch("agent_runner.sandbox.AsyncSandbox") as mock_sandbox_class:
            with patch("agent_runner.sandbox.upload_job_logs_to_blob") as mock_upload:
                with patch("agent_runner.sandbox.update_job"):
                    with patch("agent_runner.sandbox.get_job") as mock_get_job:
                        with patch("agent_runner.sandbox.update_cluster"):
                            mock_sandbox_class.return_value.__aenter__ = AsyncMock(
                                return_value=mock_sandbox
                            )
                            mock_sandbox_class.return_value.__aexit__ = AsyncMock(
                                return_value=None
                            )
                            mock_upload.return_value = expected_blob_url
                            mock_get_job.return_value = job

                            # Run would normally be called, but we test _archive directly
                            # Add logs that would be written during sandbox run
                            job_logs_manager.append_log(job.id, "Agent starting...\n")
                            job_logs_manager.append_log(job.id, "Work complete.\n")

                            result = await runner._archive_logs_to_blob(job.id)

                            assert result is True
                            mock_upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_failed_job_still_archives_logs(self, project_context):
        """Test that a failed sandbox job still archives logs to Blob."""
        from agent_runner.sandbox import SandboxKilocodeRunner

        pid = project_context["project_id"]
        cluster, job = _create_test_fixtures(pid)

        runner = SandboxKilocodeRunner()

        # Add logs that would be written during a failing sandbox run
        job_logs_manager.append_log(job.id, "Agent starting...\n")
        job_logs_manager.append_log(job.id, "Error occurred!\n")
        job_logs_manager.append_log(job.id, "Job failed.\n")

        with patch("agent_runner.sandbox.upload_job_logs_to_blob") as mock_upload:
            with patch("agent_runner.sandbox.update_job"):
                mock_upload.return_value = "https://blob.example.com/logs.txt"

                result = await runner._archive_logs_to_blob(job.id)

                assert result is True
                # Verify error logs were included
                call_args = mock_upload.call_args[0]
                assert "Error occurred!" in call_args[1]
                assert "Job failed." in call_args[1]


class TestBlobArchivalIntegration:
    """Integration tests for blob archival with real blob_storage module."""

    def test_blob_storage_module_importable(self):
        """Verify blob_storage module can be imported."""
        import blob_storage

        assert hasattr(blob_storage, "upload_job_logs_to_blob")
        assert hasattr(blob_storage, "fetch_job_logs_from_blob")
        assert hasattr(blob_storage, "delete_job_logs_from_blob")

    def test_job_logs_manager_importable(self):
        """Verify job_logs_manager module can be imported."""
        import job_logs_manager

        assert hasattr(job_logs_manager, "append_log")
        assert hasattr(job_logs_manager, "get_logs")
        assert hasattr(job_logs_manager, "clear_logs")

    @pytest.mark.asyncio
    async def test_full_log_lifecycle(self, project_context):
        """Test complete lifecycle: write logs -> archive -> fetch."""
        from agent_runner.sandbox import SandboxKilocodeRunner
        from blob_storage import fetch_job_logs_from_blob

        pid = project_context["project_id"]
        cluster, job = _create_test_fixtures(pid)

        # Write logs to memory
        job_logs_manager.append_log(job.id, "Step 1: Clone repo\n")
        job_logs_manager.append_log(job.id, "Step 2: Apply fix\n")
        job_logs_manager.append_log(job.id, "Step 3: Push changes\n")

        # Verify logs in memory
        logs = job_logs_manager.get_logs(job.id)
        assert len(logs) == 3

        runner = SandboxKilocodeRunner()
        blob_url = "https://blob.example.com/test.txt"
        archived_content = None

        def capture_upload(jid, content):
            nonlocal archived_content
            archived_content = content
            return blob_url

        with patch("agent_runner.sandbox.upload_job_logs_to_blob", side_effect=capture_upload):
            with patch("agent_runner.sandbox.update_job"):
                result = await runner._archive_logs_to_blob(job.id)

                assert result is True

        # Verify logs were archived correctly
        assert archived_content is not None
        assert "Step 1: Clone repo" in archived_content
        assert "Step 2: Apply fix" in archived_content
        assert "Step 3: Push changes" in archived_content

        # Verify logs cleared from memory
        assert job_logs_manager.get_logs(job.id) == []

        # Mock fetching from blob
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.text = archived_content
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            fetched = fetch_job_logs_from_blob(blob_url)
            assert fetched == archived_content


class TestRealBlobIntegration:
    """Integration tests that hit the real Blob API. Skipped if token not set."""

    @pytest.mark.asyncio
    async def test_real_blob_upload_and_fetch(self, project_context):
        """Test actual upload and fetch from Vercel Blob storage."""
        # Check env var directly since module-level BLOB_TOKEN may not have been set
        blob_token = os.getenv("BLOB_READ_WRITE_TOKEN") or os.getenv("soulcaster_agent_logs_dev_READ_WRITE_TOKEN")
        if not blob_token:
            pytest.skip("BLOB_READ_WRITE_TOKEN not set - skipping real Blob test")

        # Reload blob_storage module with token now available
        import importlib
        import blob_storage
        importlib.reload(blob_storage)

        from blob_storage import (
            upload_job_logs_to_blob,
            fetch_job_logs_from_blob,
            delete_job_logs_from_blob,
        )

        pid = project_context["project_id"]
        cluster, job = _create_test_fixtures(pid)

        # Create test log content
        test_logs = f"""=== Test Job {job.id} ===
Timestamp: {datetime.now(timezone.utc).isoformat()}
Step 1: Starting test...
Step 2: Processing data...
Step 3: Completed successfully!
"""

        blob_url = None
        try:
            # Upload to real Blob storage
            blob_url = upload_job_logs_to_blob(job.id, test_logs)

            assert blob_url is not None
            assert "blob" in blob_url.lower() or "vercel" in blob_url.lower()
            assert str(job.id) in blob_url

            # Fetch back from Blob storage
            fetched_content = fetch_job_logs_from_blob(blob_url)

            assert fetched_content == test_logs
            assert "Step 1: Starting test" in fetched_content
            assert "Completed successfully" in fetched_content

        finally:
            # Cleanup: delete the test blob
            if blob_url:
                deleted = delete_job_logs_from_blob(blob_url)
                # Don't fail the test if cleanup fails
                if not deleted:
                    print(f"Warning: Failed to delete test blob at {blob_url}")

    @pytest.mark.asyncio
    async def test_real_sandbox_blob_archival_flow(self, project_context):
        """Test full sandbox -> blob archival flow with real APIs."""
        # Check env var directly since module-level BLOB_TOKEN may not have been set
        blob_token = os.getenv("BLOB_READ_WRITE_TOKEN") or os.getenv("soulcaster_agent_logs_dev_READ_WRITE_TOKEN")
        if not blob_token:
            pytest.skip("BLOB_READ_WRITE_TOKEN not set - skipping real Blob test")

        # Reload blob_storage module with token now available
        import importlib
        import blob_storage
        importlib.reload(blob_storage)

        from agent_runner.sandbox import SandboxKilocodeRunner
        from blob_storage import (
            fetch_job_logs_from_blob,
            delete_job_logs_from_blob,
        )
        from store import get_job as store_get_job, update_job as store_update_job

        pid = project_context["project_id"]
        cluster, job = _create_test_fixtures(pid)

        # Simulate sandbox writing logs to memory
        job_logs_manager.append_log(job.id, "=== Real Integration Test ===\n")
        job_logs_manager.append_log(job.id, f"Job ID: {job.id}\n")
        job_logs_manager.append_log(job.id, "Cloning repository...\n")
        job_logs_manager.append_log(job.id, "Applying fix...\n")
        job_logs_manager.append_log(job.id, "Creating pull request...\n")
        job_logs_manager.append_log(job.id, "Done!\n")

        # Verify logs are in memory
        memory_logs = job_logs_manager.get_logs(job.id)
        assert len(memory_logs) == 6

        runner = SandboxKilocodeRunner()
        blob_url = None

        try:
            # Archive to real Blob storage
            result = await runner._archive_logs_to_blob(job.id)

            assert result is True

            # Memory should be cleared
            assert job_logs_manager.get_logs(job.id) == []

            # Job should have blob_url set
            updated_job = store_get_job(job.id)
            assert updated_job is not None
            blob_url = updated_job.blob_url
            assert blob_url is not None

            # Fetch from Blob and verify content
            fetched = fetch_job_logs_from_blob(blob_url)
            assert "Real Integration Test" in fetched
            assert str(job.id) in fetched
            assert "Creating pull request" in fetched

        finally:
            # Cleanup
            if blob_url:
                delete_job_logs_from_blob(blob_url)
            job_logs_manager.clear_logs(job.id)
