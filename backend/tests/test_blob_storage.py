"""Tests for blob_storage module."""

import sys
from unittest.mock import patch, MagicMock
from uuid import uuid4

import pytest


class TestUploadJobLogsToBlob:
    """Tests for upload_job_logs_to_blob function."""

    def test_upload_success(self):
        """Test successful upload to Vercel Blob."""
        from blob_storage import upload_job_logs_to_blob

        job_id = uuid4()
        logs = "Test log content\nLine 2\n"
        expected_url = f"https://blob.vercel-storage.com/logs/{job_id}.txt"

        mock_put = MagicMock(return_value={"url": expected_url})
        mock_vercel_blob = MagicMock()
        mock_vercel_blob.put = mock_put

        with patch("blob_storage.BLOB_TOKEN", "test-token"):
            with patch.dict(sys.modules, {"vercel_blob": mock_vercel_blob}):
                result = upload_job_logs_to_blob(job_id, logs)

                assert result == expected_url
                mock_put.assert_called_once_with(
                    f"logs/{job_id}.txt",
                    logs.encode("utf-8"),
                    {"access": "public", "token": "test-token"},
                )

    def test_upload_without_token_raises(self):
        """Test that upload fails when BLOB_TOKEN is not set."""
        from blob_storage import upload_job_logs_to_blob

        job_id = uuid4()

        with patch("blob_storage.BLOB_TOKEN", None):
            with pytest.raises(ValueError, match="BLOB_READ_WRITE_TOKEN"):
                upload_job_logs_to_blob(job_id, "test logs")

    def test_upload_with_empty_token_raises(self):
        """Test that upload fails when BLOB_TOKEN is empty string."""
        from blob_storage import upload_job_logs_to_blob

        job_id = uuid4()

        with patch("blob_storage.BLOB_TOKEN", ""):
            with pytest.raises(ValueError, match="BLOB_READ_WRITE_TOKEN"):
                upload_job_logs_to_blob(job_id, "test logs")

    def test_upload_handles_api_error(self):
        """Test that API errors are propagated."""
        from blob_storage import upload_job_logs_to_blob

        job_id = uuid4()

        mock_put = MagicMock(side_effect=Exception("API Error"))
        mock_vercel_blob = MagicMock()
        mock_vercel_blob.put = mock_put

        with patch("blob_storage.BLOB_TOKEN", "test-token"):
            with patch.dict(sys.modules, {"vercel_blob": mock_vercel_blob}):
                with pytest.raises(Exception, match="API Error"):
                    upload_job_logs_to_blob(job_id, "test logs")

    def test_upload_with_unicode_content(self):
        """Test upload with unicode characters in logs."""
        from blob_storage import upload_job_logs_to_blob

        job_id = uuid4()
        logs = "Test with émojis 🚀 and ñ characters\n"
        expected_url = f"https://blob.vercel-storage.com/logs/{job_id}.txt"

        mock_put = MagicMock(return_value={"url": expected_url})
        mock_vercel_blob = MagicMock()
        mock_vercel_blob.put = mock_put

        with patch("blob_storage.BLOB_TOKEN", "test-token"):
            with patch.dict(sys.modules, {"vercel_blob": mock_vercel_blob}):
                result = upload_job_logs_to_blob(job_id, logs)

                assert result == expected_url
                # Verify UTF-8 encoding was used
                call_args = mock_put.call_args[0]
                assert call_args[1] == logs.encode("utf-8")


class TestFetchJobLogsFromBlob:
    """Tests for fetch_job_logs_from_blob function."""

    def test_fetch_success(self):
        """Test successful fetch from Vercel Blob."""
        from blob_storage import fetch_job_logs_from_blob

        blob_url = "https://blob.vercel-storage.com/logs/test.txt"
        expected_content = "Log line 1\nLog line 2\n"

        mock_response = MagicMock()
        mock_response.text = expected_content
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get", return_value=mock_response) as mock_get:
            result = fetch_job_logs_from_blob(blob_url)

            assert result == expected_content
            mock_get.assert_called_once_with(blob_url, timeout=30)

    def test_fetch_handles_404(self):
        """Test that 404 errors are propagated."""
        from blob_storage import fetch_job_logs_from_blob

        blob_url = "https://blob.vercel-storage.com/logs/nonexistent.txt"

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")

        with patch("requests.get", return_value=mock_response):
            with pytest.raises(Exception, match="404"):
                fetch_job_logs_from_blob(blob_url)

    def test_fetch_handles_timeout(self):
        """Test that timeout errors are propagated."""
        from blob_storage import fetch_job_logs_from_blob

        blob_url = "https://blob.vercel-storage.com/logs/test.txt"

        with patch("requests.get", side_effect=Exception("Connection timed out")):
            with pytest.raises(Exception, match="timed out"):
                fetch_job_logs_from_blob(blob_url)


class TestDeleteJobLogsFromBlob:
    """Tests for delete_job_logs_from_blob function."""

    def test_delete_success(self):
        """Test successful deletion from Vercel Blob."""
        from blob_storage import delete_job_logs_from_blob

        blob_url = "https://blob.vercel-storage.com/logs/test.txt"

        mock_delete = MagicMock()
        mock_vercel_blob = MagicMock()
        mock_vercel_blob.delete = mock_delete

        with patch("blob_storage.BLOB_TOKEN", "test-token"):
            with patch.dict(sys.modules, {"vercel_blob": mock_vercel_blob}):
                result = delete_job_logs_from_blob(blob_url)

                assert result is True
                mock_delete.assert_called_once_with(blob_url, {"token": "test-token"})

    def test_delete_without_token_returns_false(self):
        """Test that delete returns False when BLOB_TOKEN is not set."""
        from blob_storage import delete_job_logs_from_blob

        blob_url = "https://blob.vercel-storage.com/logs/test.txt"

        with patch("blob_storage.BLOB_TOKEN", None):
            result = delete_job_logs_from_blob(blob_url)
            assert result is False

    def test_delete_handles_api_error(self):
        """Test that API errors return False instead of raising."""
        from blob_storage import delete_job_logs_from_blob

        blob_url = "https://blob.vercel-storage.com/logs/test.txt"

        mock_delete = MagicMock(side_effect=Exception("API Error"))
        mock_vercel_blob = MagicMock()
        mock_vercel_blob.delete = mock_delete

        with patch("blob_storage.BLOB_TOKEN", "test-token"):
            with patch.dict(sys.modules, {"vercel_blob": mock_vercel_blob}):
                result = delete_job_logs_from_blob(blob_url)
                assert result is False
