#!/usr/bin/env python3
"""
Reset dev environment: clears Redis, Vector DB, and Postgres.

SAFETY FEATURES:
- Loads credentials from .env
- Refuses to run with PROD URLs or ENVIRONMENT=production
- Requires confirmation before deletion

Usage:
    python scripts/reset_dev_data.py
    python scripts/reset_dev_data.py --force  # Skip confirmation
"""

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

# Load environment from .env.local (project root)

project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env.local")
load_dotenv(project_root / ".env")  # Fallback


class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_colored(message: str, color: str):
    print(f"{color}{message}{Colors.END}")


def is_production_url(url: str) -> bool:
    if not url:
        return False
    url_lower = url.lower()
    return "prod" in url_lower or "production" in url_lower


def validate_environment():
    """Ensure we're using DEV credentials, not production."""
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        raise ValueError(
            "ENVIRONMENT=production detected!\n"
            "This script is for DEV only. Set ENVIRONMENT=development"
        )

    redis_url = os.getenv("UPSTASH_REDIS_REST_URL", "")
    vector_url = os.getenv("UPSTASH_VECTOR_REST_URL", "")

    if is_production_url(redis_url) or is_production_url(vector_url):
        raise ValueError(
            "PRODUCTION URL DETECTED!\n"
            "This script is for DEV only. Check your .env file."
        )

    return True


def flush_redis():
    """Flush all Redis data."""
    print("🗑️  Flushing Redis...")

    redis_url = os.getenv("UPSTASH_REDIS_REST_URL")
    redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")

    if not redis_url or not redis_token:
        print_colored("   ⚠️  Redis credentials not found, skipping", Colors.YELLOW)
        return False

    try:
        response = requests.post(
            f"{redis_url}/FLUSHALL",
            headers={"Authorization": f"Bearer {redis_token}"},
            timeout=10,
        )
        if response.status_code == 200:
            print_colored("   ✓ Redis flushed successfully", Colors.GREEN)
            return True
        else:
            print_colored(f"   ✗ Redis flush failed: {response.status_code}", Colors.RED)
            return False
    except Exception as e:
        print_colored(f"   ✗ Redis flush failed: {e}", Colors.RED)
        return False


def reset_vector_db():
    """Reset the Upstash Vector database."""
    print("🗑️  Resetting Vector DB...")

    vector_url = os.getenv("UPSTASH_VECTOR_REST_URL")
    vector_token = os.getenv("UPSTASH_VECTOR_REST_TOKEN")

    if not vector_url or not vector_token:
        print_colored("   ⚠️  Vector credentials not found, skipping", Colors.YELLOW)
        return False

    try:
        response = requests.post(
            f"{vector_url.rstrip('/')}/reset",
            headers={"Authorization": f"Bearer {vector_token}"},
            timeout=10,
        )
        if response.status_code == 200:
            print_colored("   ✓ Vector DB reset successfully", Colors.GREEN)
            return True
        else:
            print_colored(f"   ✗ Vector reset failed: {response.status_code}", Colors.RED)
            return False
    except Exception as e:
        print_colored(f"   ✗ Vector reset failed: {e}", Colors.RED)
        return False


def reset_postgres():
    """Delete all users/projects from PostgreSQL."""
    print("🗑️  Resetting Postgres...")

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print_colored("   ⚠️  DATABASE_URL not found, skipping", Colors.YELLOW)
        return False

    try:
        import psycopg2
    except ImportError:
        print_colored("   ⚠️  psycopg2 not installed, skipping Postgres reset", Colors.YELLOW)
        return False

    try:
        parsed = urlparse(database_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            dbname=parsed.path.lstrip('/'),
            sslmode='require'
        )

        cursor = conn.cursor()

        # Get existing tables
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        tables = [row[0] for row in cursor.fetchall()]

        # Delete in order respecting FK constraints
        delete_order = ["Session", "Account", "Project", "User"]
        total_deleted = 0

        for table in delete_order:
            actual_table = table if table in tables else table.lower()
            if actual_table in tables:
                cursor.execute(f'DELETE FROM "{actual_table}"')
                deleted = cursor.rowcount
                total_deleted += deleted
                if deleted > 0:
                    print(f"      Deleted {deleted} rows from {actual_table}")

        conn.commit()
        cursor.close()
        conn.close()

        print_colored(f"   ✓ Postgres reset successfully ({total_deleted} rows)", Colors.GREEN)
        return True

    except Exception as e:
        print_colored(f"   ✗ Postgres reset failed: {e}", Colors.RED)
        return False


def main():
    parser = argparse.ArgumentParser(description="Reset DEV environment")
    parser.add_argument("--force", action="store_true", help="Skip confirmation")
    parser.add_argument("--skip-postgres", action="store_true", help="Skip Postgres reset")
    args = parser.parse_args()

    print_colored("=" * 50, Colors.BOLD)
    print_colored("  DEV ENVIRONMENT RESET", Colors.BOLD)
    print_colored("=" * 50, Colors.BOLD)
    print()

    # Safety check
    try:
        validate_environment()
        print_colored("✓ Environment validated (DEV mode)", Colors.GREEN)
        print()
    except ValueError as e:
        print_colored(f"❌ SAFETY CHECK FAILED: {e}", Colors.RED)
        return 1

    # Confirmation
    if not args.force:
        print_colored("⚠️  This will DELETE ALL data from Redis, Vector DB, and Postgres!", Colors.YELLOW)
        print()
        response = input("Type 'DELETE' to confirm: ")
        if response != "DELETE":
            print_colored("❌ Aborted.", Colors.RED)
            return 1
        print()

    # Reset all stores
    results = []
    results.append(("Redis", flush_redis()))
    print()
    results.append(("Vector DB", reset_vector_db()))
    print()
    if not args.skip_postgres:
        results.append(("Postgres", reset_postgres()))
        print()

    # Summary
    print_colored("=" * 50, Colors.BOLD)
    print("SUMMARY")
    print_colored("=" * 50, Colors.BOLD)
    for name, success in results:
        status = "✓" if success else "✗"
        color = Colors.GREEN if success else Colors.RED
        print_colored(f"  {status} {name}", color)

    all_success = all(r[1] for r in results)
    print()
    if all_success:
        print_colored("🎉 Dev environment reset complete!", Colors.GREEN)
    else:
        print_colored("⚠️  Some operations failed. Check output above.", Colors.YELLOW)

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
