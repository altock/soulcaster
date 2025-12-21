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
    Append a log message to the in-memory buffer for the given job.
    
    Parameters:
        job_id (UUID): Identifier of the job whose log buffer will receive the message.
        message (str): Log line to append to the job's in-memory log list.
    """
    with _logs_lock:
        if job_id not in _job_logs:
            _job_logs[job_id] = []
        _job_logs[job_id].append(message)


def get_logs(job_id: UUID) -> List[str]:
    """
    Retrieve the in-memory log lines for the specified job.
    
    Parameters:
        job_id (UUID): Identifier of the job whose logs to retrieve.
    
    Returns:
        List[str]: Log messages for the job; empty list if no logs are present.
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
    List all job IDs that currently have in-memory logs.
    
    Returns:
        List[UUID]: Job UUIDs that currently have logs stored in memory.
    """
    with _logs_lock:
        return list(_job_logs.keys())