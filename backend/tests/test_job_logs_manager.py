"""Tests for job_logs_manager module."""

import threading
from uuid import uuid4

import pytest

from job_logs_manager import append_log, get_logs, clear_logs, get_all_active_jobs


class TestJobLogsManager:
    """Tests for in-memory job logs manager."""

    def test_append_and_get_logs(self):
        """
        Verify that appended log lines for a job are stored and retrieved in order.
        
        Also confirms the logs are initially empty and clears stored logs during cleanup.
        """
        job_id = uuid4()

        # Initially empty
        assert get_logs(job_id) == []

        # Append logs
        append_log(job_id, "Line 1\n")
        append_log(job_id, "Line 2\n")

        logs = get_logs(job_id)
        assert logs == ["Line 1\n", "Line 2\n"]

        # Cleanup
        clear_logs(job_id)

    def test_get_logs_returns_copy(self):
        """Test that get_logs returns a copy, not the original list."""
        job_id = uuid4()
        append_log(job_id, "Original\n")

        logs = get_logs(job_id)
        logs.append("Modified\n")  # Modify the returned list

        # Original should be unchanged
        assert get_logs(job_id) == ["Original\n"]

        # Cleanup
        clear_logs(job_id)

    def test_clear_logs(self):
        """Test clearing logs from memory."""
        job_id = uuid4()
        append_log(job_id, "Line 1\n")

        # Clear and get returned logs
        cleared = clear_logs(job_id)
        assert cleared == ["Line 1\n"]

        # Should be empty now
        assert get_logs(job_id) == []

        # Clearing again returns None
        assert clear_logs(job_id) is None

    def test_clear_nonexistent_job(self):
        """Test clearing logs for a job that doesn't exist."""
        job_id = uuid4()
        assert clear_logs(job_id) is None

    def test_get_all_active_jobs(self):
        """Test getting all active job IDs."""
        job1 = uuid4()
        job2 = uuid4()

        append_log(job1, "Log 1\n")
        append_log(job2, "Log 2\n")

        active = get_all_active_jobs()
        assert job1 in active
        assert job2 in active

        # Cleanup
        clear_logs(job1)
        clear_logs(job2)

    def test_thread_safety(self):
        """Test that concurrent access is thread-safe."""
        job_id = uuid4()
        num_threads = 10
        logs_per_thread = 100

        def append_logs():
            for i in range(logs_per_thread):
                append_log(job_id, f"Log {threading.current_thread().name}-{i}\n")

        threads = [
            threading.Thread(target=append_logs, name=f"Thread-{i}")
            for i in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        logs = get_logs(job_id)
        assert len(logs) == num_threads * logs_per_thread

        # Cleanup
        clear_logs(job_id)

    def test_multiple_jobs_isolated(self):
        """Test that different jobs have isolated logs."""
        job1 = uuid4()
        job2 = uuid4()

        append_log(job1, "Job 1 log\n")
        append_log(job2, "Job 2 log\n")

        assert get_logs(job1) == ["Job 1 log\n"]
        assert get_logs(job2) == ["Job 2 log\n"]

        # Clearing one doesn't affect the other
        clear_logs(job1)
        assert get_logs(job1) == []
        assert get_logs(job2) == ["Job 2 log\n"]

        # Cleanup
        clear_logs(job2)