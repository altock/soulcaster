"""
Vercel Blob Storage client for archiving job logs.

This module provides functions to upload, fetch, and delete job logs
from Vercel Blob storage.
"""

import os
import logging
from uuid import UUID
from typing import Optional

logger = logging.getLogger(__name__)

# Get Vercel Blob token from environment
BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN") or os.getenv("soulcaster_agent_logs_dev_READ_WRITE_TOKEN")


def upload_job_logs_to_blob(job_id: UUID, logs: str) -> str:
    """
    Upload job logs to Vercel Blob storage.

    Args:
        job_id: UUID of the job
        logs: Complete log content as string

    Returns:
        str: URL of the uploaded blob

    Raises:
        Exception: If upload fails
    """
    if not BLOB_TOKEN:
        raise ValueError("BLOB_READ_WRITE_TOKEN environment variable not set")

    try:
        from vercel_blob import put

        response = put(
            f"logs/{job_id}.txt",
            logs.encode("utf-8"),
            {
                "access": "public",
                "token": BLOB_TOKEN,
            },
        )
        blob_url = response["url"]
        logger.info(f"Uploaded logs for job {job_id} to Blob: {blob_url}")
        return blob_url

    except ImportError:
        logger.exception("vercel_blob package not installed")
        raise ImportError("vercel_blob package not installed. Run: pip install vercel-blob") from None
    except Exception:
        logger.exception(f"Failed to upload logs to Blob for job {job_id}")
        raise


def fetch_job_logs_from_blob(blob_url: str) -> str:
    """
    Fetch job logs from Vercel Blob storage.

    Args:
        blob_url: URL of the blob to fetch

    Returns:
        str: Log content

    Raises:
        Exception: If fetch fails
    """
    try:
        import requests

        response = requests.get(blob_url, timeout=30)
        response.raise_for_status()
        return response.text

    except Exception:
        logger.exception(f"Failed to fetch logs from Blob at {blob_url}")
        raise


def delete_job_logs_from_blob(blob_url: str) -> bool:
    """
    Delete job logs from Vercel Blob storage.

    Args:
        blob_url: URL of the blob to delete

    Returns:
        bool: True if deletion succeeded, False otherwise
    """
    if not BLOB_TOKEN:
        logger.warning("BLOB_READ_WRITE_TOKEN not set, cannot delete blob")
        return False

    try:
        from vercel_blob import delete

        delete(blob_url, {"token": BLOB_TOKEN})
        logger.info(f"Deleted blob at {blob_url}")
        return True

    except ImportError:
        logger.error("vercel_blob package not installed")
        return False
    except Exception as e:
        logger.warning(f"Failed to delete blob at {blob_url}: {e}")
        return False
