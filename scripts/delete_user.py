#!/usr/bin/env python3
"""
Delete a specific user and all their projects/data from Redis, Vector DB, and Postgres.

PROD-SAFE: Operates on a single user only.

Usage:
    python scripts/delete_user.py <user_id_or_email>
    python scripts/delete_user.py <user_id_or_email> --force
    python scripts/delete_user.py --list  # List all users
"""

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

# Load environment from .env.prod (production credentials)
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env.prod")


class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_colored(message: str, color: str):
    print(f"{color}{message}{Colors.END}")


# =============================================================================
# Redis helpers
# =============================================================================

def get_redis_client():
    """Get Redis REST client info."""
    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        return None, None
    return url, token


def redis_command(url: str, token: str, *args) -> dict:
    """Execute a Redis command via REST API."""
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=list(args),
        timeout=30,
    )
    return response.json()


def redis_scan_keys(url: str, token: str, pattern: str) -> list:
    """Scan for keys matching a pattern."""
    keys = []
    cursor = "0"
    while True:
        result = redis_command(url, token, "SCAN", cursor, "MATCH", pattern, "COUNT", "100")
        if "result" in result:
            cursor = result["result"][0]
            keys.extend(result["result"][1])
            if cursor == "0":
                break
        else:
            break
    return keys


def get_project_redis_keys(project_id: str) -> dict:
    """Get all Redis keys for a project (dry run)."""
    url, token = get_redis_client()
    if not url:
        return {"success": False, "error": "Redis credentials not found", "keys": []}

    patterns = [
        f"feedback:{project_id}:*",
        f"feedback:created:{project_id}",
        f"feedback:source:{project_id}:*",
        f"feedback:external:{project_id}:*",
        f"feedback:unclustered:{project_id}",
        f"cluster:{project_id}:*",
        f"cluster:all:{project_id}",
        f"cluster:lock:{project_id}",
        f"cluster_job:{project_id}:*",
        f"cluster_job:recent:{project_id}",
        f"sentry:config:{project_id}:*",
        f"splunk:config:{project_id}:*",
        f"datadog:config:{project_id}:*",
        f"posthog:config:{project_id}:*",
        f"reddit:subreddits:{project_id}",
        f"datadog:webhook_secret:{project_id}",
        f"datadog:monitors:{project_id}",
    ]

    all_keys = []
    for pattern in patterns:
        if "*" in pattern:
            all_keys.extend(redis_scan_keys(url, token, pattern))
        else:
            result = redis_command(url, token, "EXISTS", pattern)
            if result.get("result") == 1:
                all_keys.append(pattern)

    return {"success": True, "keys": all_keys}


def delete_redis_keys(keys: list) -> dict:
    """Delete specific Redis keys."""
    url, token = get_redis_client()
    if not url or not keys:
        return {"success": True, "deleted_keys": 0}

    batch_size = 100
    deleted = 0
    for i in range(0, len(keys), batch_size):
        batch = keys[i:i + batch_size]
        redis_command(url, token, "DEL", *batch)
        deleted += len(batch)
    return {"success": True, "deleted_keys": deleted}


# =============================================================================
# Vector DB helpers
# =============================================================================

def check_vector_namespace(project_id: str) -> dict:
    """Check if vector namespace exists and get info."""
    url = os.getenv("UPSTASH_VECTOR_REST_URL")
    token = os.getenv("UPSTASH_VECTOR_REST_TOKEN")

    if not url or not token:
        return {"success": False, "error": "Vector credentials not found", "exists": False}

    try:
        # Try to get namespace info
        response = requests.get(
            f"{url.rstrip('/')}/info/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            vector_count = data.get("result", {}).get("vectorCount", 0)
            return {"success": True, "exists": True, "vector_count": vector_count}
        return {"success": True, "exists": False, "vector_count": 0}
    except Exception as e:
        return {"success": False, "error": str(e), "exists": False}


def delete_vector_namespace(project_id: str) -> dict:
    """Delete vector namespace for a project."""
    url = os.getenv("UPSTASH_VECTOR_REST_URL")
    token = os.getenv("UPSTASH_VECTOR_REST_TOKEN")

    if not url or not token:
        return {"success": True}  # Nothing to delete

    try:
        response = requests.post(
            f"{url.rstrip('/')}/delete-namespace/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if response.status_code in [200, 404]:
            return {"success": True}
        return {"success": False, "error": f"Status {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Postgres helpers
# =============================================================================

def get_db_connection():
    """Get Postgres connection."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        return None

    try:
        import psycopg2
    except ImportError:
        return None

    parsed = urlparse(database_url)
    return psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname=parsed.path.lstrip('/'),
        sslmode='require'
    )


def list_users():
    """List all users."""
    conn = get_db_connection()
    if not conn:
        print_colored("Cannot connect to database", Colors.RED)
        return []

    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.email, u.name, COUNT(p.id) as project_count
        FROM "User" u
        LEFT JOIN "Project" p ON p."userId" = u.id
        GROUP BY u.id
        ORDER BY u.id
    ''')
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return users


def get_user_info(user_id_or_email: str) -> dict:
    """Get user details by ID or email."""
    conn = get_db_connection()
    if not conn:
        return {}

    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.email, u.name
        FROM "User" u
        WHERE u.id = %s OR u.email = %s
    ''', (user_id_or_email, user_id_or_email))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row:
        return {"id": row[0], "email": row[1], "name": row[2]}
    return {}


def get_user_projects(user_id: str) -> list:
    """Get all projects for a user."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM "Project" WHERE "userId" = %s', (user_id,))
    projects = cursor.fetchall()
    cursor.close()
    conn.close()
    return projects


def delete_user_postgres(user_id: str) -> dict:
    """Delete user from Postgres (cascades to Account, Session, Project)."""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Cannot connect to database"}

    try:
        cursor = conn.cursor()

        # Clear defaultProjectId references
        cursor.execute('UPDATE "User" SET "defaultProjectId" = NULL WHERE "defaultProjectId" IN (SELECT id FROM "Project" WHERE "userId" = %s)', (user_id,))

        # Delete user (cascades to Account, Session, Project)
        cursor.execute('DELETE FROM "User" WHERE id = %s', (user_id,))
        deleted = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        return {"success": True, "deleted": deleted}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Delete a user and all their data")
    parser.add_argument("user_id", nargs="?", help="User ID or email")
    parser.add_argument("--force", action="store_true", help="Skip confirmation")
    parser.add_argument("--list", action="store_true", help="List all users")
    args = parser.parse_args()

    if args.list:
        print_colored("\nAll Users:", Colors.BOLD)
        print("-" * 80)
        users = list_users()
        if not users:
            print("  No users found")
        for u in users:
            print(f"  {u[0]}")
            print(f"    Email: {u[1]}")
            print(f"    Name: {u[2]}")
            print(f"    Projects: {u[3]}")
            print()
        return 0

    if not args.user_id:
        parser.print_help()
        return 1

    print_colored("=" * 60, Colors.BOLD)
    print_colored("  DELETE USER (PROD)", Colors.BOLD)
    print_colored("=" * 60, Colors.BOLD)
    print()

    # Get user info
    info = get_user_info(args.user_id)
    if not info:
        print_colored(f"User not found: {args.user_id}", Colors.RED)
        return 1

    user_id = info["id"]
    projects = get_user_projects(user_id)

    print(f"  User: {info['name'] or '(no name)'} ({info['email'] or '(no email)'})")
    print(f"  ID: {user_id}")
    print(f"  Projects: {len(projects)}")
    print()

    # ==========================================================================
    # PHASE 1: Gather all data to be deleted
    # ==========================================================================
    print_colored("📊 Scanning data to be deleted...", Colors.BLUE)
    print()

    project_data = []
    total_redis_keys = 0
    total_vectors = 0

    for project_id, project_name in projects:
        print(f"  Project: {project_name} ({project_id})")

        # Check Redis
        redis_info = get_project_redis_keys(project_id)
        redis_keys = redis_info.get("keys", [])
        total_redis_keys += len(redis_keys)

        if redis_info["success"]:
            print(f"    Redis: {len(redis_keys)} keys")
            # Show breakdown
            feedback_keys = [k for k in redis_keys if k.startswith(f"feedback:{project_id}")]
            cluster_keys = [k for k in redis_keys if k.startswith(f"cluster:{project_id}")]
            if feedback_keys:
                print(f"      - {len(feedback_keys)} feedback keys")
            if cluster_keys:
                print(f"      - {len(cluster_keys)} cluster keys")
        else:
            print_colored(f"    Redis: {redis_info.get('error')}", Colors.YELLOW)

        # Check Vector
        vector_info = check_vector_namespace(project_id)
        vector_count = vector_info.get("vector_count", 0)
        total_vectors += vector_count

        if vector_info["success"]:
            if vector_info.get("exists"):
                print(f"    Vector: {vector_count} embeddings")
            else:
                print(f"    Vector: namespace not found")
        else:
            print_colored(f"    Vector: {vector_info.get('error')}", Colors.YELLOW)

        project_data.append({
            "id": project_id,
            "name": project_name,
            "redis_keys": redis_keys,
            "vector_count": vector_count,
        })
        print()

    # ==========================================================================
    # PHASE 2: Show summary and confirm
    # ==========================================================================
    print_colored("=" * 60, Colors.BOLD)
    print_colored("DELETION SUMMARY", Colors.BOLD)
    print_colored("=" * 60, Colors.BOLD)
    print()
    print(f"  User: {info['name'] or user_id}")
    print(f"  Projects: {len(projects)}")
    print(f"  Redis keys: {total_redis_keys}")
    print(f"  Vector embeddings: {total_vectors}")
    print(f"  Postgres: 1 user + {len(projects)} project(s)")
    print()

    if not args.force:
        print_colored("⚠️  This action is PERMANENT and cannot be undone.", Colors.YELLOW)
        print()
        confirm_value = info['email'] or user_id
        response = input(f"Type '{confirm_value}' to confirm deletion: ")
        if response != confirm_value:
            print_colored("❌ Aborted.", Colors.RED)
            return 1
        print()

    # ==========================================================================
    # PHASE 3: Delete
    # ==========================================================================
    print_colored("🗑️  Deleting...", Colors.RED)
    print()

    for pdata in project_data:
        print(f"  Project: {pdata['name']}...")

        # Delete Redis keys
        if pdata["redis_keys"]:
            redis_result = delete_redis_keys(pdata["redis_keys"])
            if redis_result["success"]:
                print_colored(f"    ✓ Redis: {redis_result.get('deleted_keys', 0)} keys deleted", Colors.GREEN)
            else:
                print_colored(f"    ✗ Redis failed", Colors.RED)
        else:
            print(f"    - Redis: nothing to delete")

        # Delete Vector namespace
        if pdata["vector_count"] > 0:
            vector_result = delete_vector_namespace(pdata["id"])
            if vector_result["success"]:
                print_colored(f"    ✓ Vector: namespace deleted", Colors.GREEN)
            else:
                print_colored(f"    ✗ Vector: {vector_result.get('error')}", Colors.RED)
        else:
            print(f"    - Vector: nothing to delete")

    # Delete user from Postgres
    print()
    print("  Postgres...")
    pg_result = delete_user_postgres(user_id)
    if pg_result["success"]:
        print_colored("    ✓ User and projects deleted", Colors.GREEN)
    else:
        print_colored(f"    ✗ {pg_result.get('error')}", Colors.RED)

    print()
    print_colored("=" * 60, Colors.BOLD)
    print_colored("✓ Deletion complete", Colors.GREEN)
    print_colored("=" * 60, Colors.BOLD)

    return 0


if __name__ == "__main__":
    sys.exit(main())
