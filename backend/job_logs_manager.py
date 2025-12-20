"""
In-memory job logs manager for real-time log viewing.

Stores logs in memory while jobs are running, then archives to Blob on completion.
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID
from threading import Lock

logger = logging.getLogger(__name__)

# Global in-memory storage for active job logs
# Format: {job_id: [log_line1, log_line2, ...]}
_job_logs: Dict[UUID, List[str]] = {}
_logs_lock = Lock()


def append_log(job_id: UUID, message: str) -> None:
    """
    Append a log message to a job's in-memory log buffer.

    Args:
        job_id: UUID of the job
        message: Log message to append
    """
    with _logs_lock:
        if job_id not in _job_logs:
            _job_logs[job_id] = []
        _job_logs[job_id].append(message)


def get_logs(job_id: UUID) -> List[str]:
    """
    Get all logs for a job from memory.

    Args:
        job_id: UUID of the job

    Returns:
        List of log messages (may be empty if job not found or no logs)
    """
    with _logs_lock:
        return _job_logs.get(job_id, []).copy()


def clear_logs(job_id: UUID) -> Optional[List[str]]:
    """
    Remove and return logs for a job from memory.

    Used after archiving to Blob to free memory.

    Args:
        job_id: UUID of the job

    Returns:
        List of log messages that were removed, or None if not found
    """
    with _logs_lock:
        return _job_logs.pop(job_id, None)


def get_all_active_jobs() -> List[UUID]:
    """
    Get list of all job IDs that currently have logs in memory.

    Returns:
        List of job UUIDs
    """
    with _logs_lock:
        return list(_job_logs.keys())
