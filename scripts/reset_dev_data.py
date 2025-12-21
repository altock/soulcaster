#!/usr/bin/env python3
"""
CLI script to reset all data in the DEV Upstash Redis instance.

SAFETY FEATURES:
- ONLY works with DEV credentials
- Refuses to run with PROD URLs
- Requires confirmation before deletion
- Prints summary of deleted keys

Usage:
    python scripts/reset_dev_data.py
    python scripts/reset_dev_data.py --force  # Skip confirmation
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List

# Add backend to path so we can import from it
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_colored(message: str, color: str):
    """
    Prints a message to the terminal using the specified ANSI color code.
    
    Parameters:
        message (str): The text to print.
        color (str): ANSI color code prefix to apply (e.g., Colors.RED, Colors.GREEN).
    """
    print(f"{color}{message}{Colors.END}")


def is_production_url(url: str) -> bool:
    """
    Determine whether a URL appears to point to a production instance.
    
    A URL is considered production if it contains the substrings "prod" or "production" (case-insensitive).
    
    Returns:
        `True` if the URL appears to be a production URL, `False` otherwise.
    """
    if not url:
        return False
    url_lower = url.lower()
    return "prod" in url_lower or "production" in url_lower


def validate_environment() -> tuple[str, str]:
    """
    Ensure required Upstash REST credentials are present and reference a non-production environment.
    
    Checks that UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are set, verifies the REST URL does not appear to be a production URL, and ensures ENVIRONMENT is not set to "production". 
    
    Returns:
        tuple[str, str]: The Upstash REST URL and REST token.
    
    Raises:
        ValueError: If required environment variables are missing, the REST URL appears to be production, or ENVIRONMENT is "production".
    """
    rest_url = os.getenv("UPSTASH_REDIS_REST_URL")
    rest_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")

    if not rest_url or not rest_token:
        raise ValueError(
            "Missing required environment variables:\n"
            "  UPSTASH_REDIS_REST_URL\n"
            "  UPSTASH_REDIS_REST_TOKEN\n\n"
            "Make sure you have a .env file in the project root."
        )

    # Safety check: refuse to run with production URLs
    if is_production_url(rest_url):
        raise ValueError(
            f"PRODUCTION URL DETECTED!\n\n"
            f"This script is designed for DEV only.\n"
            f"URL: {rest_url}\n\n"
            f"Refusing to proceed for safety reasons."
        )

    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        raise ValueError(
            "ENVIRONMENT=production detected!\n\n"
            "This script is designed for DEV only.\n"
            "Change ENVIRONMENT to 'development' or remove it from .env"
        )

    return rest_url, rest_token


def scan_keys(base_url: str, token: str, pattern: str = "*") -> List[str]:
    """
    Return all Redis keys that match the given pattern by scanning the Upstash REST API.
    
    Parameters:
        base_url (str): Upstash REST endpoint URL.
        token (str): Bearer token for Upstash REST API authentication.
        pattern (str): Redis key pattern to match (e.g., "prefix:*"). Defaults to "*".
    
    Returns:
        List[str]: Matching Redis keys.
    """
    keys = []
    cursor = "0"

    while True:
        response = requests.post(
            base_url,
            headers={"Authorization": f"Bearer {token}"},
            json=["SCAN", cursor, "MATCH", pattern, "COUNT", "100"],
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()["result"]

        cursor = result[0]
        keys.extend(result[1])

        if cursor == "0":
            break

    return keys


def delete_keys(base_url: str, token: str, keys: List[str]) -> int:
    """
    Delete multiple Redis keys via the Upstash REST API in batches.
    
    Parameters:
    	keys (List[str]): Redis key names to delete.
    
    Returns:
    	int: Total number of keys deleted.
    """
    if not keys:
        return 0

    # Delete in batches of 100
    batch_size = 100
    deleted = 0

    for i in range(0, len(keys), batch_size):
        batch = keys[i:i + batch_size]
        response = requests.post(
            base_url,
            headers={"Authorization": f"Bearer {token}"},
            json=["DEL"] + batch,
            timeout=10,
        )
        response.raise_for_status()
        deleted += response.json()["result"]

    return deleted


def reset_vector_db():
    """
    Reset the Upstash Vector database by deleting all stored embeddings.
    
    If vector REST credentials are missing the function prints a warning and returns without taking action.
    Raises a ValueError if the configured vector URL appears to be a production URL to prevent accidental deletion.
    
    Raises:
        ValueError: If the vector URL looks like a production endpoint.
    """
    vector_url = os.getenv("UPSTASH_VECTOR_REST_URL")
    vector_token = os.getenv("UPSTASH_VECTOR_REST_TOKEN")

    if not vector_url or not vector_token:
        print_colored("⚠️  Upstash Vector credentials not found, skipping vector reset", Colors.YELLOW)
        return

    if is_production_url(vector_url):
        raise ValueError(
            f"PRODUCTION VECTOR URL DETECTED: {vector_url}\n"
            "Refusing to proceed."
        )

    try:
        # Upstash Vector API: DELETE /reset
        response = requests.post(
            f"{vector_url.rstrip('/')}/reset",
            headers={"Authorization": f"Bearer {vector_token}"},
            timeout=10,
        )
        response.raise_for_status()
        print_colored("✅ Vector database reset successfully", Colors.GREEN)
    except Exception as e:
        print_colored(f"⚠️  Failed to reset vector database: {e}", Colors.YELLOW)


def main():
    """
    Run the CLI to safely reset development data in Upstash-backed Redis and optionally reset the vector database.
    
    Parses CLI flags `--force` (skip confirmation) and `--skip-vector` (skip vector reset), validates that DEV credentials/URLs are being used, scans for predefined Redis key patterns, prompts for explicit confirmation unless forced, deletes found keys in batches, and optionally resets the Upstash Vector store.
    
    Returns:
        int: Exit code where `0` indicates success and `1` indicates an aborted operation or an error (including safety-check failures).
    """
    parser = argparse.ArgumentParser(description="Reset DEV data in Upstash Redis")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )
    parser.add_argument(
        "--skip-vector",
        action="store_true",
        help="Skip resetting the vector database"
    )
    args = parser.parse_args()

    print_colored("=" * 60, Colors.BOLD)
    print_colored("  Soulcaster DEV Data Reset Tool", Colors.BOLD)
    print_colored("=" * 60, Colors.BOLD)
    print()

    try:
        # Validate environment
        print("🔍 Validating environment...")
        rest_url, rest_token = validate_environment()
        print_colored(f"✅ Using DEV instance: {rest_url}", Colors.GREEN)
        print()

        # Scan for keys
        print("🔍 Scanning for keys to delete...")
        patterns = [
            "feedback:*",
            "cluster:*",
            "clusters:*",
            "job:*",
            "config:*",
            "project:*",
            "user:*",
            "cluster_jobs:*",
            "coding_plan:*",
        ]

        all_keys = []
        for pattern in patterns:
            keys = scan_keys(rest_url, rest_token, pattern)
            all_keys.extend(keys)
            if keys:
                print(f"  Found {len(keys)} keys matching '{pattern}'")

        total_keys = len(all_keys)
        print()
        print_colored(f"📊 Total keys to delete: {total_keys}", Colors.BLUE)
        print()

        if total_keys == 0:
            print_colored("✅ No data to delete. Database is already clean!", Colors.GREEN)
            return 0

        # Confirmation
        if not args.force:
            print_colored("⚠️  WARNING: This will DELETE ALL data from the DEV database!", Colors.YELLOW)
            print()
            response = input(f"Type 'DELETE' to confirm: ")
            if response != "DELETE":
                print_colored("❌ Aborted. No data was deleted.", Colors.RED)
                return 1

        # Delete Redis keys
        print()
        print("🗑️  Deleting Redis keys...")
        deleted = delete_keys(rest_url, rest_token, all_keys)
        print_colored(f"✅ Deleted {deleted} keys from Redis", Colors.GREEN)

        # Delete Vector DB
        if not args.skip_vector:
            print()
            print("🗑️  Resetting vector database...")
            reset_vector_db()

        print()
        print_colored("=" * 60, Colors.GREEN)
        print_colored("  ✅ DEV Data Reset Complete!", Colors.GREEN)
        print_colored("=" * 60, Colors.GREEN)
        return 0

    except ValueError as e:
        print()
        print_colored(f"❌ SAFETY CHECK FAILED:", Colors.RED)
        print_colored(f"   {e}", Colors.RED)
        print()
        return 1
    except Exception as e:
        print()
        print_colored(f"❌ ERROR: {e}", Colors.RED)
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())