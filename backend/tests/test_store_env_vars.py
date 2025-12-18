"""Tests for environment variable handling in store.py, specifically quote-stripping."""

import os
from unittest.mock import MagicMock, patch

import pytest

from store import _redis_client_from_env, _strip_quotes, _upstash_rest_client_from_env


class TestStripQuotes:
    """Test the _strip_quotes helper function."""

    def test_strips_double_quotes(self):
        """Test that double quotes are stripped from both ends."""
        assert _strip_quotes('"https://example.com"') == "https://example.com"
        assert _strip_quotes('"value"') == "value"

    def test_strips_single_quotes(self):
        """Test that single quotes are stripped from both ends."""
        assert _strip_quotes("'https://example.com'") == "https://example.com"
        assert _strip_quotes("'value'") == "value"

    def test_strips_mixed_quotes(self):
        """Test that quotes are stripped even if mixed."""
        # If value has double quotes, strip them
        assert _strip_quotes('"value"') == "value"
        # If value has single quotes, strip them
        assert _strip_quotes("'value'") == "value"
        # If value has both outer quotes, both are stripped (strips from both ends)
        assert _strip_quotes('"\'value\'"') == "value"  # Outer double quotes stripped, then outer single quotes

    def test_handles_no_quotes(self):
        """Test that values without quotes are unchanged."""
        assert _strip_quotes("https://example.com") == "https://example.com"
        assert _strip_quotes("value") == "value"

    def test_handles_none(self):
        """Test that None is handled correctly."""
        assert _strip_quotes(None) is None

    def test_handles_empty_string(self):
        """Test that empty strings are handled correctly."""
        assert _strip_quotes("") == ""
        assert _strip_quotes('""') == ""
        assert _strip_quotes("''") == ""

    def test_handles_quotes_in_middle(self):
        """Test that quotes in the middle are not stripped."""
        assert _strip_quotes('"value with "quotes" inside"') == 'value with "quotes" inside'
        assert _strip_quotes("'value with 'quotes' inside'") == "value with 'quotes' inside"


class TestRedisClientFromEnv:
    """Test _redis_client_from_env with quoted and unquoted URLs."""

    @patch("store.redis")
    def test_handles_unquoted_url(self, mock_redis):
        """Test that unquoted URLs work correctly."""
        mock_redis.from_url.return_value = MagicMock()
        
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379"}):
            result = _redis_client_from_env()
            assert result is not None
            mock_redis.from_url.assert_called_once_with("redis://localhost:6379", decode_responses=True)

    @patch("store.redis")
    def test_handles_quoted_double_quotes(self, mock_redis):
        """Test that URLs with double quotes are stripped."""
        mock_redis.from_url.return_value = MagicMock()
        
        with patch.dict(os.environ, {"REDIS_URL": '"redis://localhost:6379"'}):
            result = _redis_client_from_env()
            assert result is not None
            mock_redis.from_url.assert_called_once_with("redis://localhost:6379", decode_responses=True)

    @patch("store.redis")
    def test_handles_quoted_single_quotes(self, mock_redis):
        """Test that URLs with single quotes are stripped."""
        mock_redis.from_url.return_value = MagicMock()
        
        with patch.dict(os.environ, {"REDIS_URL": "'redis://localhost:6379'"}):
            result = _redis_client_from_env()
            assert result is not None
            mock_redis.from_url.assert_called_once_with("redis://localhost:6379", decode_responses=True)

    @patch("store.redis")
    def test_handles_upstash_redis_url(self, mock_redis):
        """Test that UPSTASH_REDIS_URL is used when REDIS_URL is not set."""
        mock_redis.from_url.return_value = MagicMock()
        
        with patch.dict(os.environ, {"UPSTASH_REDIS_URL": '"redis://upstash.example.com:6379"'}):
            result = _redis_client_from_env()
            assert result is not None
            mock_redis.from_url.assert_called_once_with("redis://upstash.example.com:6379", decode_responses=True)

    @patch("store.redis")
    def test_handles_quoted_upstash_url(self, mock_redis):
        """Test that quoted Upstash URLs are handled correctly."""
        mock_redis.from_url.return_value = MagicMock()
        url = '"https://busy-barnacle-42832.upstash.io"'
        
        with patch.dict(os.environ, {"UPSTASH_REDIS_URL": url}):
            result = _redis_client_from_env()
            assert result is not None
            # Verify the quotes were stripped
            mock_redis.from_url.assert_called_once_with("https://busy-barnacle-42832.upstash.io", decode_responses=True)

    def test_returns_none_when_no_redis_url(self):
        """Test that None is returned when no Redis URL is set."""
        with patch.dict(os.environ, {}, clear=True):
            result = _redis_client_from_env()
            assert result is None

    def test_returns_none_when_redis_not_available(self):
        """Test that None is returned when redis module is not available."""
        with patch("store.redis", None):
            with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379"}):
                result = _redis_client_from_env()
                assert result is None


class TestUpstashRestClientFromEnv:
    """Test _upstash_rest_client_from_env with quoted and unquoted URLs/tokens."""

    @patch("store.UpstashRESTClient")
    def test_handles_unquoted_url_and_token(self, mock_client_class):
        """Test that unquoted URL and token work correctly."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        with patch.dict(os.environ, {
            "UPSTASH_REDIS_REST_URL": "https://example.upstash.io",
            "UPSTASH_REDIS_REST_TOKEN": "token123"
        }):
            result = _upstash_rest_client_from_env()
            assert result is not None
            mock_client_class.assert_called_once_with("https://example.upstash.io", "token123")

    @patch("store.UpstashRESTClient")
    def test_handles_quoted_url_and_token(self, mock_client_class):
        """Test that quoted URL and token are stripped correctly."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        with patch.dict(os.environ, {
            "UPSTASH_REDIS_REST_URL": '"https://busy-barnacle-42832.upstash.io"',
            "UPSTASH_REDIS_REST_TOKEN": '"token123"'
        }):
            result = _upstash_rest_client_from_env()
            assert result is not None
            # Verify quotes were stripped from both
            mock_client_class.assert_called_once_with("https://busy-barnacle-42832.upstash.io", "token123")

    @patch("store.UpstashRESTClient")
    def test_handles_single_quoted_url_and_token(self, mock_client_class):
        """Test that single-quoted URL and token are stripped correctly."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        with patch.dict(os.environ, {
            "UPSTASH_REDIS_REST_URL": "'https://example.upstash.io'",
            "UPSTASH_REDIS_REST_TOKEN": "'token123'"
        }):
            result = _upstash_rest_client_from_env()
            assert result is not None
            mock_client_class.assert_called_once_with("https://example.upstash.io", "token123")

    @patch("store.UpstashRESTClient")
    def test_handles_mixed_quoted_values(self, mock_client_class):
        """Test that one quoted and one unquoted value works."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        with patch.dict(os.environ, {
            "UPSTASH_REDIS_REST_URL": '"https://example.upstash.io"',
            "UPSTASH_REDIS_REST_TOKEN": "token123"  # No quotes
        }):
            result = _upstash_rest_client_from_env()
            assert result is not None
            mock_client_class.assert_called_once_with("https://example.upstash.io", "token123")

    def test_returns_none_when_url_missing(self):
        """Test that None is returned when URL is missing."""
        with patch.dict(os.environ, {
            "UPSTASH_REDIS_REST_TOKEN": "token123"
        }, clear=True):
            result = _upstash_rest_client_from_env()
            assert result is None

    def test_returns_none_when_token_missing(self):
        """Test that None is returned when token is missing."""
        with patch.dict(os.environ, {
            "UPSTASH_REDIS_REST_URL": "https://example.upstash.io"
        }, clear=True):
            result = _upstash_rest_client_from_env()
            assert result is None

    def test_returns_none_when_both_missing(self):
        """Test that None is returned when both are missing."""
        with patch.dict(os.environ, {}, clear=True):
            result = _upstash_rest_client_from_env()
            assert result is None
