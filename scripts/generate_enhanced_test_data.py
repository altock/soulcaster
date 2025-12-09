#!/usr/bin/env python3
"""
Enhanced Test Data Generator for Soulcaster

Creates realistic GitHub repositories with intentional bugs and generates 
clustered issues for testing the feedback clustering and coding agent.

Usage:
    python scripts/generate_enhanced_test_data.py <repo_url> <github_token> [--modules all|basic]
    
Example:
    python scripts/generate_enhanced_test_data.py https://github.com/username/test-repo ghp_xxxxx --modules all
"""

import os
import random
import requests
import time
import subprocess
import shutil
import argparse
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# Configuration
DEFAULT_SLEEP_BETWEEN_ISSUES = 2  # seconds
MAX_RETRIES = 3
RATE_LIMIT_WAIT = 60  # seconds


class CodeGenerator:
    """Generates code modules with intentional bugs for testing."""
    
    @staticmethod
    def generate_math_ops() -> str:
        """
        Generate a Python module source containing basic math operation functions intentionally crafted with common bugs for testing.
        
        The returned module implements add, subtract, multiply, divide, power, sqrt, factorial, and modulo functions; the implementation intentionally omits checks for division/modulo by zero, does not handle sqrt of negative numbers, and does not validate negative input for factorial.
        
        Returns:
            module_source (str): The Python source code of the generated math operations module.
        """
        return """import math

def add(a, b):
    \"\"\"Add two numbers.\"\"\"
    return a + b

def subtract(a, b):
    \"\"\"Subtract b from a.\"\"\"
    return a - b

def multiply(a, b):
    \"\"\"Multiply two numbers.\"\"\"
    return a * b

def divide(a, b):
    \"\"\"Divide a by b.
    
    TODO: Add zero division check
    \"\"\"
    # BUG: No check for b == 0
    return a / b

def power(a, b):
    \"\"\"Return a raised to the power of b.\"\"\"
    return a ** b

def sqrt(a):
    \"\"\"Calculate square root of a.
    
    TODO: Handle negative numbers
    \"\"\"
    # BUG: Will crash on negative numbers
    return math.sqrt(a)

def factorial(n):
    \"\"\"Calculate factorial of n.
    
    TODO: Add validation for negative numbers
    \"\"\"
    if n == 0:
        return 1
    # BUG: Infinite recursion for negative numbers
    return n * factorial(n - 1)

def modulo(a, b):
    \"\"\"Calculate a modulo b.
    
    TODO: Check for zero divisor
    \"\"\"
    # BUG: No check for b == 0
    return a % b
"""

    @staticmethod
    def generate_string_utils() -> str:
        """
        Generate source code for a Python module containing string utility functions with intentional case-sensitivity and boundary bugs.
        
        Returns:
            module_src (str): Python source code as a string defining the functions
            `reverse_string`, `to_upper`, `to_lower`, `is_palindrome`, `truncate`,
            `word_count`, and `starts_with_vowel`. Several functions include
            intentionally introduced bugs (case-sensitive comparisons, improper
            boundary checks, and missing edge-case handling) for testing purposes.
        """
        return """def reverse_string(s):
    \"\"\"Reverse a string.\"\"\"
    return s[::-1]

def to_upper(s):
    \"\"\"Convert string to uppercase.\"\"\"
    return s.upper()

def to_lower(s):
    \"\"\"Convert string to lowercase.\"\"\"
    return s.lower()

def is_palindrome(s):
    \"\"\"Check if string is a palindrome.
    
    TODO: Make case-insensitive
    \"\"\"
    # BUG: Case sensitive check
    return s == s[::-1]

def truncate(s, length):
    \"\"\"Truncate string to specified length.
    
    TODO: Handle edge cases better
    \"\"\"
    # BUG: Raises error if length > len(s)
    if length > len(s):
        raise IndexError(f"Length {length} exceeds string length {len(s)}")
    return s[:length]

def word_count(s):
    \"\"\"Count words in string.
    
    TODO: Handle empty strings
    \"\"\"
    # BUG: Crashes on empty string
    return len(s.split())

def starts_with_vowel(s):
    \"\"\"Check if string starts with vowel.
    
    TODO: Make case-insensitive
    \"\"\"
    # BUG: Doesn't handle uppercase
    vowels = ['a', 'e', 'i', 'o', 'u']
    return s[0] in vowels
"""

    @staticmethod
    def generate_user_manager() -> str:
        """
        Generate source code for an in-memory UserManager module that intentionally contains concurrency and deletion bugs.
        
        The returned source defines a UserManager class with methods to add, get, delete, update, and list users. The implementation includes deliberate issues for testing: deletion is a no-op (does not remove users), get_user may return None silently when a user is missing, add_user and update_user lack proper thread-safety (race conditions), and several TODO comments note missing validations and exception handling.
        
        Returns:
            str: Python source code for the UserManager module containing the described behaviours and deliberate bugs.
        """
        return """import threading

class UserManager:
    \"\"\"Manage user data in memory.
    
    TODO: Add thread safety
    \"\"\"
    
    def __init__(self):
        self.users = {}
        self.lock = threading.Lock()
    
    def add_user(self, user_id, name, email=None):
        \"\"\"Add a user.\"\"\"
        # BUG: No thread safety
        self.users[user_id] = {
            "name": name,
            "email": email
        }
    
    def get_user(self, user_id):
        \"\"\"Get user by ID.
        
        TODO: Raise exception if user not found?
        \"\"\"
        # BUG: Returns None silently
        return self.users.get(user_id)
    
    def delete_user(self, user_id):
        \"\"\"Delete a user.
        
        TODO: Actually implement deletion
        \"\"\"
        # BUG: No-op, doesn't actually delete
        if user_id in self.users:
            pass  # Forgot to delete!
    
    def update_user(self, user_id, name=None, email=None):
        \"\"\"Update user information.
        
        TODO: Add validation
        \"\"\"
        # BUG: Race condition - no locking
        if user_id in self.users:
            if name:
                self.users[user_id]["name"] = name
            if email:
                self.users[user_id]["email"] = email
    
    def list_users(self):
        \"\"\"List all users.\"\"\"
        return list(self.users.values())
"""

    @staticmethod
    def generate_api_client() -> str:
        """
        Generate the Python source for a toy API client module that intentionally includes timeout, error-handling, and retry/backoff bugs.
        
        The returned source defines an APIClient class with `get`, `post`, and `retry_request` methods. The generated code purposefully omits a timeout on GET requests, provides minimal connection/error handling on POST, and retries without exponential backoff to serve as test data containing common networking bugs.
        
        Returns:
            module_source (str): Python source code for the defective API client module.
        """
        return """import requests
import time

class APIClient:
    \"\"\"Simple API client with retry logic.
    
    TODO: Improve error handling
    \"\"\"
    
    def __init__(self, base_url, timeout=10):
        self.base_url = base_url
        self.timeout = timeout
    
    def get(self, endpoint, params=None):
        \"\"\"Make GET request.
        
        TODO: Add timeout handling
        \"\"\"
        url = f"{self.base_url}/{endpoint}"
        # BUG: No timeout set, will hang forever
        response = requests.get(url, params=params)
        return response.json()
    
    def post(self, endpoint, data=None):
        \"\"\"Make POST request.
        
        TODO: Handle connection errors
        \"\"\"
        url = f"{self.base_url}/{endpoint}"
        # BUG: No error handling for connection issues
        response = requests.post(url, json=data, timeout=self.timeout)
        return response.json()
    
    def retry_request(self, method, endpoint, max_retries=3):
        \"\"\"Retry failed requests.
        
        TODO: Add exponential backoff
        \"\"\"
        for i in range(max_retries):
            try:
                if method == "GET":
                    return self.get(endpoint)
                elif method == "POST":
                    return self.post(endpoint)
            except Exception as e:
                # BUG: No backoff, hammers the API
                if i < max_retries - 1:
                    time.sleep(0.1)  # Should be exponential!
                else:
                    raise
"""

    @staticmethod
    def generate_database_layer() -> str:
        """
        Return a Python module source string that defines a deliberately insecure Database wrapper.
        
        The generated module contains a Database class with intentional defects for testing:
        - non-parameterized query construction (SQL injection vulnerability),
        - unsafe handling of connection lifecycle (connect/close misuse and missing existence checks),
        - use of string formatting for query parameters,
        and inline TODO comments indicating missing security and error-handling improvements.
        
        Returns:
            str: Source code of the Python module implementing the insecure Database class.
        """
        return """import sqlite3

class Database:
    \"\"\"Simple database wrapper.
    
    TODO: Add security measures
    \"\"\"
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        \"\"\"Connect to database.\"\"\"
        self.conn = sqlite3.connect(self.db_path)
    
    def execute_query(self, query, params=None):
        \"\"\"Execute a SQL query.
        
        TODO: Use parameterized queries
        \"\"\"
        # BUG: SQL injection vulnerability
        cursor = self.conn.cursor()
        if params:
            # BUG: String formatting instead of parameters
            query = query % params
        cursor.execute(query)
        return cursor.fetchall()
    
    def insert_user(self, username, email):
        \"\"\"Insert a user.
        
        TODO: Use parameterized queries
        \"\"\"
        # BUG: SQL injection possible
        query = f"INSERT INTO users (username, email) VALUES ('{username}', '{email}')"
        return self.execute_query(query)
    
    def close(self):
        \"\"\"Close database connection.
        
        TODO: Auto-close on errors
        \"\"\"
        # BUG: Doesn't check if conn exists
        self.conn.close()
"""

    @staticmethod
    def generate_cache_manager() -> str:
        """
        Provide the source code for a test CacheManager module that intentionally contains TTL and memory-leak bugs.
        
        The returned string is a complete Python module defining a CacheManager class with methods:
        `set(key, value, ttl)`, `get(key)`, `delete(key)`, and `cleanup_expired()`.
        
        Known intentional issues encoded in the module:
        - Expired entries may still be returned by `get`.
        - No automatic cleanup task is implemented, leading to potential memory leaks.
        - `delete` removes cache entries but does not remove their TTL records.
        - `cleanup_expired` may raise `KeyError` if an entry is removed from the cache before TTL cleanup.
        
        Returns:
            str: Python source code for the buggy CacheManager module, suitable for use in test repositories.
        """
        return """import time
from typing import Any, Optional

class CacheManager:
    \"\"\"In-memory cache with TTL support.
    
    TODO: Implement cleanup
    \"\"\"
    
    def __init__(self, default_ttl=300):
        self.cache = {}
        self.ttl_map = {}
        self.default_ttl = default_ttl
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        \"\"\"Set a cache value with TTL.\"\"\"
        self.cache[key] = value
        expiry = time.time() + (ttl or self.default_ttl)
        self.ttl_map[key] = expiry
        # BUG: No cleanup task, memory leak!
    
    def get(self, key: str) -> Optional[Any]:
        \"\"\"Get a cache value.
        
        TODO: Check expiry before returning
        \"\"\"
        # BUG: Returns expired values
        return self.cache.get(key)
    
    def delete(self, key: str):
        \"\"\"Delete a cache entry.\"\"\"
        if key in self.cache:
            del self.cache[key]
        # BUG: Doesn't remove from ttl_map
    
    def cleanup_expired(self):
        \"\"\"Remove expired entries.
        
        TODO: Run automatically
        \"\"\"
        current_time = time.time()
        expired_keys = [
            k for k, expiry in self.ttl_map.items() 
            if expiry < current_time
        ]
        for key in expired_keys:
            # BUG: KeyError if already deleted
            del self.cache[key]
            del self.ttl_map[key]
"""


class IssueClusterGenerator:
    """Generates clusters of related GitHub issues."""
    
    @staticmethod
    def get_all_clusters() -> Dict[str, List[Dict[str, Any]]]:
        """
        Collects all predefined issue clusters keyed by cluster name.
        
        Each cluster value is a list of issue dictionaries describing specific bug scenarios; each issue dict contains keys such as `title`, `body`, and `labels`.
        
        Returns:
            clusters (Dict[str, List[Dict[str, Any]]]): Mapping from cluster key to a list of issue dictionaries.
        """
        return {
            "division_by_zero": IssueClusterGenerator._division_by_zero_cluster(),
            "sqrt_negative": IssueClusterGenerator._sqrt_negative_cluster(),
            "factorial_recursion": IssueClusterGenerator._factorial_recursion_cluster(),
            "palindrome_case": IssueClusterGenerator._palindrome_case_cluster(),
            "truncate_error": IssueClusterGenerator._truncate_error_cluster(),
            "delete_user_noop": IssueClusterGenerator._delete_user_noop_cluster(),
            "race_condition": IssueClusterGenerator._race_condition_cluster(),
            "api_timeout": IssueClusterGenerator._api_timeout_cluster(),
            "sql_injection": IssueClusterGenerator._sql_injection_cluster(),
            "memory_leak": IssueClusterGenerator._memory_leak_cluster(),
        }
    
    @staticmethod
    def _division_by_zero_cluster() -> List[Dict[str, Any]]:
        """
        Provide a set of GitHub issue templates focused on division-by-zero bugs and related validations.
        
        Each entry describes a reproducible problem or enhancement for handling division/modulo by zero, including crash reports, reproduction steps, and suggested fixes or validations.
        
        Returns:
            A list of dictionaries where each dictionary has keys:
              - `title` (str): short issue title
              - `body` (str): detailed issue description and reproduction steps
              - `labels` (List[str]): labels to categorize the issue (e.g., "bug", "critical")
        """
        return [
            {
                "title": "ZeroDivisionError in math_ops.divide",
                "body": "The `divide` function crashes when the second argument is 0.\n\n**Steps to reproduce:**\n1. Call `divide(10, 0)`\n2. See error\n\n**Expected:** Should return error message or infinity\n**Actual:** Crashes with ZeroDivisionError",
                "labels": ["bug", "critical"]
            },
            {
                "title": "App crashes when dividing by zero",
                "body": "I tried to use the divide function with 0 as the denominator and got:\n```\nZeroDivisionError: division by zero\n```\nThis is blocking our production deployment.",
                "labels": ["bug", "blocker"]
            },
            {
                "title": "Need input validation in divide function",
                "body": "We should add a check to ensure we don't divide by zero. This is a common edge case that should be handled gracefully.",
                "labels": ["enhancement", "good first issue"]
            },
            {
                "title": "Unhandled exception in math_ops",
                "body": "Getting crashes in production from divide(x, 0). Need to add validation.",
                "labels": ["bug"]
            },
            {
                "title": "modulo function also has zero division issue",
                "body": "Similar to the divide bug, `modulo(5, 0)` also crashes. Should be fixed together with divide.",
                "labels": ["bug"]
            },
        ]
    
    @staticmethod
    def _sqrt_negative_cluster() -> List[Dict[str, Any]]:
        """
        Provide issue-cluster templates focused on handling square-root of negative numbers.
        
        Each item is a dictionary describing a GitHub issue with keys:
        - `title`: short issue title
        - `body`: detailed description or repro/stack trace
        - `labels`: list of label strings
        
        Returns:
            List[Dict[str, Any]]: A list of issue dictionaries covering bug reports, enhancement suggestions, production crashes, and validation/good-first-issue items related to `sqrt` handling of negative inputs.
        """
        return [
            {
                "title": "ValueError when calculating square root of negative numbers",
                "body": "Calling `sqrt(-1)` raises:\n```\nValueError: math domain error\n```\nMaybe return None or support complex numbers?",
                "labels": ["bug"]
            },
            {
                "title": "sqrt function should handle negative inputs gracefully",
                "body": "Instead of crashing, we should either:\n1. Return a complex number\n2. Return None\n3. Raise a custom exception with helpful message",
                "labels": ["enhancement"]
            },
            {
                "title": "Crash report: math domain error in sqrt",
                "body": "Production error when user inputted negative value. Stack trace:\n```\nFile \"math_ops.py\", line 23, in sqrt\n    return math.sqrt(a)\nValueError: math domain error\n```",
                "labels": ["bug", "production"]
            },
            {
                "title": "Add validation to sqrt before calling math.sqrt",
                "body": "Need to check if `a < 0` before calling `math.sqrt(a)`.",
                "labels": ["good first issue"]
            },
        ]
    
    @staticmethod
    def _factorial_recursion_cluster() -> List[Dict[str, Any]]:
        """
        Produce a set of GitHub issue templates describing factorial recursion bugs and an input-validation enhancement.
        
        Returns:
            List[Dict[str, Any]]: A list of issue dictionaries; each dict contains `title`, `body`, and `labels` describing specific problems (infinite recursion on negative input, stack overflow, and a suggestion to add input validation).
        """
        return [
            {
                "title": "Factorial causes infinite recursion on negative numbers",
                "body": "Calling `factorial(-1)` never returns and eventually causes stack overflow.",
                "labels": ["bug", "critical"]
            },
            {
                "title": "Stack overflow in factorial",
                "body": "The factorial function doesn't validate input. Negative numbers cause infinite loop.",
                "labels": ["bug"]
            },
            {
                "title": "Add input validation to factorial",
                "body": "Should check `n >= 0` at the start of the function.",
                "labels": ["enhancement"]
            },
        ]
    
    @staticmethod
    def _palindrome_case_cluster() -> List[Dict[str, Any]]:
        """
        Produce a cluster of issue descriptors describing palindrome case-sensitivity bugs and related enhancements.
        
        Each item is a dictionary representing an issue with keys `title`, `body`, and `labels`.
        
        Returns:
            List[Dict[str, Any]]: A list of issue dictionaries for palindrome case-related bugs and improvements.
        """
        return [
            {
                "title": "is_palindrome should be case insensitive",
                "body": "`is_palindrome('Racecar')` returns `False`, but it should return `True`.\n\nPalindromes should ignore case by convention.",
                "labels": ["bug"]
            },
            {
                "title": "Palindrome check fails for mixed case strings",
                "body": "The function compares raw strings without normalizing case first.",
                "labels": ["bug"]
            },
            {
                "title": "String utils palindrome bug with capital letters",
                "body": "Capital letters cause the palindrome check to fail. Need to convert to lowercase before comparing.",
                "labels": ["bug", "good first issue"]
            },
            {
                "title": "Make is_palindrome robust to case and spaces",
                "body": "It should:\n1. Convert to lowercase\n2. Remove spaces\n3. Then compare",
                "labels": ["enhancement"]
            },
        ]
    
    @staticmethod
    def _truncate_error_cluster() -> List[Dict[str, Any]]:
        """
        Return a list of issue definitions describing bugs and enhancements for string truncate behavior.
        
        The cluster focuses on cases where the truncate implementation raises an exception when the requested length exceeds the string length and on the desired behavior of returning the full string in that case.
        
        Returns:
            List[Dict[str, Any]]: A list of issue dictionaries, each containing `title` (str), `body` (str), and `labels` (List[str]).
        """
        return [
            {
                "title": "IndexError in truncate function",
                "body": "`truncate('abc', 10)` raises `IndexError: Length 10 exceeds string length 3`.\n\nShould just return the whole string instead.",
                "labels": ["bug"]
            },
            {
                "title": "truncate throws exception if length is larger than string",
                "body": "Python slicing handles this gracefully (`'abc'[:10]` == `'abc'`), but our function raises an error.",
                "labels": ["bug"]
            },
            {
                "title": "String truncation edge case",
                "body": "Truncate should return the full string if requested length exceeds actual length.",
                "labels": ["enhancement"]
            },
        ]
    
    @staticmethod
    def _delete_user_noop_cluster() -> List[Dict[str, Any]]:
        """
        Return a list of GitHub issue templates describing deletion-related bugs in the UserManager.
        
        Each list item is a dictionary representing an issue with keys:
        - `title`: short issue title.
        - `body`: issue description and reproduction or suggested fix.
        - `labels`: list of labels to tag the issue (e.g., "bug", "critical").
        
        Returns:
            List[Dict[str, Any]]: A list of issue dictionaries focused on delete_user being a no-op or causing related problems.
        """
        return [
            {
                "title": "delete_user doesn't actually delete users",
                "body": "I called `user_manager.delete_user(123)` but the user still shows up in `list_users()`.",
                "labels": ["bug", "critical"]
            },
            {
                "title": "Users persist after deletion",
                "body": "The delete_user function appears to be a no-op. Checked the code and it just has `pass` in the if block.",
                "labels": ["bug", "blocker"]
            },
            {
                "title": "UserManager.delete_user is not implemented",
                "body": "Need to actually delete from self.users dict:\n```python\ndel self.users[user_id]\n```",
                "labels": ["bug", "good first issue"]
            },
            {
                "title": "Memory leak? Users not being removed",
                "body": "Our user list keeps growing even though we're calling delete_user. Is there a memory leak?",
                "labels": ["bug", "performance"]
            },
        ]
    
    @staticmethod
    def _race_condition_cluster() -> List[Dict[str, Any]]:
        """
        Provide a set of GitHub issue templates describing race-condition and thread-safety problems in the UserManager module.
        
        Each issue dictionary contains a `title`, a descriptive `body`, and `labels` indicating severity or type (e.g., "bug", "threading", "critical", "enhancement").
        
        Returns:
            List[Dict[str, Any]]: A list of issue dictionaries for race-condition and threading-related bugs or enhancements.
        """
        return [
            {
                "title": "Race condition in UserManager.update_user",
                "body": "When multiple threads update the same user simultaneously, we get corrupted data.\n\nThe lock is defined but never used.",
                "labels": ["bug", "threading"]
            },
            {
                "title": "Thread safety issues in user manager",
                "body": "add_user and update_user are not thread-safe despite having a lock attribute.",
                "labels": ["bug", "critical"]
            },
            {
                "title": "Concurrent updates cause data corruption",
                "body": "Under load testing, user data gets corrupted. Need proper locking.",
                "labels": ["bug", "production"]
            },
            {
                "title": "Use threading.Lock in all mutation methods",
                "body": "Should wrap all dict modifications in `with self.lock:`",
                "labels": ["enhancement"]
            },
        ]
    
    @staticmethod
    def _api_timeout_cluster() -> List[Dict[str, Any]]:
        """
        Provide a list of issue dictionaries for API client timeout bugs and related enhancements.
        
        Each dictionary contains:
        - `title`: a short issue title,
        - `body`: a detailed description of the problem or proposal,
        - `labels`: a list of labels to apply to the issue.
        
        Returns:
            List[Dict[str, Any]]: Issue dictionaries representing the API timeout cluster.
        """
        return [
            {
                "title": "APIClient.get hangs forever on slow endpoints",
                "body": "The GET method doesn't use the timeout parameter. Requests hang indefinitely.",
                "labels": ["bug", "critical"]
            },
            {
                "title": "Timeout not applied to GET requests",
                "body": "Only POST has timeout, GET is missing it.",
                "labels": ["bug"]
            },
            {
                "title": "Add timeout to all HTTP requests",
                "body": "Both get() and post() should respect self.timeout.",
                "labels": ["enhancement", "good first issue"]
            },
        ]
    
    @staticmethod
    def _sql_injection_cluster() -> List[Dict[str, Any]]:
        """
        Provide issue templates for SQL injection vulnerabilities and remediation in the database layer.
        
        Each item is a dict with `title`, `body`, and `labels` describing a specific security bug or enhancement related to SQL injection.
        Returns:
            List[Dict[str, Any]]: A list of issue dictionaries suitable for creating GitHub issues.
        """
        return [
            {
                "title": "SQL injection vulnerability in Database.insert_user",
                "body": "The insert_user method uses f-strings to build queries. This is a critical security vulnerability.\n\n**Exploit:**\n```python\ndb.insert_user(\"admin' OR '1'='1\", \"\")\n```",
                "labels": ["security", "critical"]
            },
            {
                "title": "Use parameterized queries throughout database layer",
                "body": "All SQL queries should use `?` placeholders and parameter tuples instead of string formatting.",
                "labels": ["security", "enhancement"]
            },
            {
                "title": "execute_query uses string formatting",
                "body": "Line 25: `query = query % params` is vulnerable to SQL injection.",
                "labels": ["security", "bug"]
            },
        ]
    
    @staticmethod
    def _memory_leak_cluster() -> List[Dict[str, Any]]:
        """
        Provide issue templates describing memory-leak–related problems and enhancements for the CacheManager.
        
        Each item represents a GitHub issue dictionary with keys 'title', 'body', and 'labels' describing a specific bug or enhancement related to memory growth, TTL handling, or cleanup behavior.
        
        Returns:
            List[Dict[str, Any]]: A list of issue dictionaries; each dictionary contains:
                - 'title' (str): short issue summary
                - 'body' (str): detailed issue description
                - 'labels' (List[str]): labels to apply to the issue
        """
        return [
            {
                "title": "Memory leak in CacheManager",
                "body": "Cache grows indefinitely. Expired entries are never removed automatically.\n\nAfter 24 hours, memory usage is 2GB+.",
                "labels": ["bug", "critical", "performance"]
            },
            {
                "title": "CacheManager.delete doesn't cleanup ttl_map",
                "body": "When deleting a key, we remove from `cache` but not `ttl_map`. This causes memory leak over time.",
                "labels": ["bug"]
            },
            {
                "title": "Implement automatic cleanup task",
                "body": "Need a background thread that runs `cleanup_expired()` every N seconds.",
                "labels": ["enhancement"]
            },
            {
                "title": "KeyError in cleanup_expired",
                "body": "Sometimes cleanup_expired crashes with KeyError if a key was manually deleted. Need to use .get() or check existence first.",
                "labels": ["bug"]
            },
        ]
    
    @staticmethod
    def get_noise_issues() -> List[Dict[str, Any]]:
        """
        Return a list of unrelated "noise" GitHub issue templates used to mix with bug clusters.
        
        Returns:
            issues (List[Dict[str, Any]]): A list of issue dictionaries, each containing keys `title` (str), `body` (str), and `labels` (List[str]).
        """
        return [
            {"title": "Update README with installation instructions", "body": "Add setup steps and requirements.", "labels": ["documentation"]},
            {"title": "Add CI/CD pipeline", "body": "Setup GitHub Actions for tests.", "labels": ["devops"]},
            {"title": "Refactor directory structure", "body": "Move code to src/ directory.", "labels": ["refactor"]},
            {"title": "Add MIT License", "body": "Need open source license.", "labels": ["legal"]},
            {"title": "Support Python 3.12", "body": "Test with latest Python version.", "labels": ["enhancement"]},
            {"title": "Add logging to all modules", "body": "Use standard logging library.", "labels": ["enhancement"]},
            {"title": "Create CLI interface", "body": "Would be nice to run from command line.", "labels": ["feature"]},
            {"title": "Fix typos in docstrings", "body": "Found several spelling errors.", "labels": ["documentation"]},
            {"title": "Increase test coverage", "body": "Currently at 45%, should be >80%.", "labels": ["testing"]},
            {"title": "Performance optimization for large datasets", "body": "Some operations are slow.", "labels": ["performance"]},
            {"title": "Add type hints throughout codebase", "body": "Use mypy for type checking.", "labels": ["enhancement"]},
            {"title": "Setup pre-commit hooks", "body": "Run black, flake8, mypy before commits.", "labels": ["devops"]},
            {"title": "Add Docker support", "body": "Create Dockerfile and docker-compose.yml.", "labels": ["devops"]},
            {"title": "Implement rate limiting", "body": "Prevent API abuse.", "labels": ["security"]},
            {"title": "Add health check endpoint", "body": "For load balancer monitoring.", "labels": ["feature"]},
        ]


def create_local_files(target_dir: str = ".", module_set: str = "all"):
    """
    Create a local test project containing generated buggy modules for Soulcaster.
    
    Creates or replaces the directory at `target_dir`, writes generated module files, a README.md describing included modules, and a requirements.txt. Always writes math_ops.py, string_utils.py, and user_manager.py; if `module_set` is "all" also writes api_client.py, database.py, and cache_manager.py.
    
    Parameters:
        target_dir (str): Filesystem path where the project will be created. If the path exists it will be removed and recreated.
        module_set (str): Which module set to generate. "basic" creates only the core modules; "all" (default) includes additional advanced modules.
    """
    print(f"Creating files in {target_dir} (module set: {module_set})...")
    
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir)
    
    gen = CodeGenerator()
    
    # Always include basic modules
    modules = {
        "math_ops.py": gen.generate_math_ops(),
        "string_utils.py": gen.generate_string_utils(),
        "user_manager.py": gen.generate_user_manager(),
    }
    
    # Add advanced modules if requested
    if module_set == "all":
        modules.update({
            "api_client.py": gen.generate_api_client(),
            "database.py": gen.generate_database_layer(),
            "cache_manager.py": gen.generate_cache_manager(),
        })
    
    # Write all modules
    for filename, content in modules.items():
        with open(os.path.join(target_dir, filename), "w") as f:
            f.write(content)
    
    # Create README
    readme_content = """# Test Project for Soulcaster

This repository contains intentional bugs for testing the Soulcaster feedback clustering and coding agent.

## Modules

- `math_ops.py`: Mathematical operations (division by zero, negative sqrt, factorial recursion)
- `string_utils.py`: String utilities (case sensitivity, boundary issues)
- `user_manager.py`: User management (delete bug, race conditions)
"""
    
    if module_set == "all":
        readme_content += """- `api_client.py`: HTTP client (timeout issues, retry logic)
- `database.py`: Database layer (SQL injection, connection handling)
- `cache_manager.py`: Cache management (memory leaks, TTL bugs)
"""
    
    readme_content += """
## Known Issues

See the GitHub Issues tab for a list of bugs and enhancements.

## Testing

This is a test repository for Soulcaster. Do not use in production!
"""
    
    with open(os.path.join(target_dir, "README.md"), "w") as f:
        f.write(readme_content)
    
    # Create requirements.txt
    requirements = "requests>=2.31.0\n"
    with open(os.path.join(target_dir, "requirements.txt"), "w") as f:
        f.write(requirements)
    
    print(f"Created {len(modules)} code modules and README")


def push_to_github(repo_url: str, target_dir: str = "."):
    """
    Initialize a local git repository in target_dir, commit the files, add the given GitHub remote, and push the main branch.
    
    Parameters:
        repo_url (str): HTTPS or SSH GitHub repository URL (e.g. https://github.com/owner/repo.git or git@github.com:owner/repo.git).
        target_dir (str): Path to the local directory to initialize and push (defaults to current directory).
    
    Raises:
        ValueError: If repo_url is not a valid GitHub HTTPS or SSH URL.
        subprocess.CalledProcessError: If any git command fails.
    """
    if not (repo_url.startswith("https://github.com/") or repo_url.startswith("git@github.com:")):
        raise ValueError(f"Invalid repo_url: '{repo_url}'. Must be a GitHub URL.")
    
    print(f"Pushing to {repo_url}...")
    try:
        subprocess.run(["git", "init"], cwd=target_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=target_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit with buggy code for Soulcaster testing"], cwd=target_dir, check=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=target_dir, check=True)
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=target_dir, check=True)
        
        # Check if remote main exists
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", "main"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        remote_main_exists = result.stdout.strip() != ""
        
        if remote_main_exists:
            print("Remote main branch exists. Using standard push.")
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=target_dir, check=True)
        else:
            print("Remote main branch is empty. Using force-push.")
            subprocess.run(["git", "push", "-u", "-f", "origin", "main"], cwd=target_dir, check=True)
            
        print("✅ Successfully pushed code to GitHub")
    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e}")
        raise


def create_issues(repo_owner: str, repo_name: str, token: str, cluster_types: List[str] = None, noise_ratio: float = 0.3):
    """
    Create clustered GitHub issues in the specified repository.
    
    This function aggregates issue clusters from IssueClusterGenerator (optionally filtered by `cluster_types`), appends a proportion of unrelated "noise" issues, shuffles the list, and posts each issue to the repository's GitHub Issues API. It implements retry logic for transient failures, basic rate-limit handling, and prints progress and a final summary of created/failed counts.
    
    Parameters:
        repo_owner (str): GitHub repository owner (organization or user).
        repo_name (str): GitHub repository name.
        token (str): Personal access token used for authentication.
        cluster_types (List[str], optional): If provided, only clusters whose keys are in this list will be posted. Defaults to None (all clusters).
        noise_ratio (float, optional): Fraction of the total clustered issues to add as unrelated "noise" issues (between 0.0 and 1.0). Defaults to 0.3.
    """
    print(f"Creating issues for {repo_owner}/{repo_name}...")
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Get all available clusters
    all_clusters = IssueClusterGenerator.get_all_clusters()
    
    # Filter clusters if specified
    if cluster_types:
        all_clusters = {k: v for k, v in all_clusters.items() if k in cluster_types}
    
    # Flatten issues
    all_issues = []
    for cluster_name, issues in all_clusters.items():
        print(f"  Adding cluster: {cluster_name} ({len(issues)} issues)")
        all_issues.extend(issues)
    
    # Add noise
    noise_count = int(len(all_issues) * noise_ratio)
    noise_issues = IssueClusterGenerator.get_noise_issues()[:noise_count]
    print(f"  Adding {len(noise_issues)} noise issues")
    all_issues.extend(noise_issues)
    
    # Shuffle
    random.shuffle(all_issues)
    
    print(f"\nCreating {len(all_issues)} total issues...")
    
    created_count = 0
    failed_count = 0
    
    for i, issue in enumerate(all_issues):
        print(f"[{i+1}/{len(all_issues)}] Creating: {issue['title'][:60]}...")
        
        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                response = requests.post(url, json=issue, headers=headers, timeout=10)
                
                if response.status_code == 201:
                    created_count += 1
                    break
                elif response.status_code in [403, 429]:
                    print(f"  ⚠️  Rate limited, waiting {RATE_LIMIT_WAIT}s...")
                    time.sleep(RATE_LIMIT_WAIT)
                    retry_count += 1
                else:
                    print(f"  ❌ Failed: {response.status_code} - {response.text[:100]}")
                    failed_count += 1
                    break
                    
            except requests.exceptions.Timeout:
                retry_count += 1
                if retry_count < MAX_RETRIES:
                    print(f"  ⚠️  Timeout, retrying ({retry_count}/{MAX_RETRIES})...")
                    time.sleep(3)
                else:
                    print(f"  ❌ Timeout after {MAX_RETRIES} attempts")
                    failed_count += 1
                    break
                    
            except requests.exceptions.RequestException as e:
                print(f"  ❌ Request error: {e}")
                failed_count += 1
                break
        
        # Sleep between issues
        time.sleep(DEFAULT_SLEEP_BETWEEN_ISSUES)
    
    print(f"\n✅ Issue creation complete:")
    print(f"   Created: {created_count}")
    print(f"   Failed: {failed_count}")
    print(f"   Total: {len(all_issues)}")


def parse_github_url(repo_url: str) -> Tuple[str, str]:
    """
    Extract the repository owner and repository name from a GitHub URL.
    
    Accepts common GitHub URL formats (HTTPS and SSH, with or without a trailing `.git`) and returns the final two path segments as (owner, repo).
    
    Parameters:
        repo_url (str): GitHub repository URL in HTTPS (e.g. https://github.com/owner/repo or https://github.com/owner/repo.git) or SSH (e.g. git@github.com:owner/repo.git) form.
    
    Returns:
        tuple: A 2-tuple `(repo_owner, repo_name)` containing the repository owner and repository name.
    
    Raises:
        ValueError: If the URL is malformed or owner/repo cannot be extracted.
    """
    try:
        if repo_url.startswith("git@"):
            if ":" not in repo_url:
                raise ValueError(f"Invalid SSH URL format: {repo_url}")
            _, path_part = repo_url.split(":", 1)
            # Remove trailing .git if present (exact match)
            if path_part.endswith(".git"):
                path_part = path_part[:-4]
            path_part = path_part.rstrip("/")
            segments = path_part.split("/")
        else:
            parsed = urlparse(repo_url)
            path = parsed.path.lstrip("/")
            # Remove trailing .git if present (exact match)
            if path.endswith(".git"):
                path = path[:-4]
            path = path.rstrip("/")
            segments = path.split("/")
        
        if len(segments) < 2:
            raise ValueError(f"Could not extract owner and repo from URL: {repo_url}")
        
        repo_owner = segments[-2]
        repo_name = segments[-1]
        
        if not repo_owner or not repo_name:
            raise ValueError(f"Extracted empty owner or repo name from URL: {repo_url}")
        
        return repo_owner, repo_name
    
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Unexpected error parsing GitHub URL '{repo_url}': {e}")


def main():
    """
    Orchestrates command-line parsing and the end-to-end workflow to generate test code, optionally push it to GitHub, and optionally create clustered issues.
    
    Parses CLI arguments (repository URL, GitHub token, module selection, cluster selection, noise ratio, and skip flags), generates a temporary test repository with selected buggy modules, conditionally pushes the repository to the provided GitHub URL, and conditionally creates GitHub issues based on selected clusters and noise ratio. Always attempts to remove the temporary repository directory on exit.
    
    Returns:
        exit_code (int): `0` on success, `1` on error.
    """
    parser = argparse.ArgumentParser(
        description="Generate test data for Soulcaster (code + issues)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all modules
  python generate_enhanced_test_data.py https://github.com/user/repo $GITHUB_TOKEN --modules all
  
  # Generate basic modules only
  python generate_enhanced_test_data.py https://github.com/user/repo $GITHUB_TOKEN --modules basic
  
  # Generate specific clusters
  python generate_enhanced_test_data.py https://github.com/user/repo $GITHUB_TOKEN --clusters division_by_zero sql_injection
        """
    )
    
    parser.add_argument("repo_url", help="GitHub repository URL (HTTPS or SSH)")
    parser.add_argument("token", help="GitHub personal access token")
    parser.add_argument("--modules", choices=["all", "basic"], default="all", help="Which code modules to generate")
    parser.add_argument("--clusters", nargs="*", help="Specific bug clusters to create (default: all)")
    parser.add_argument("--noise-ratio", type=float, default=0.3, help="Ratio of noise issues to bug issues")
    parser.add_argument("--skip-push", action="store_true", help="Skip pushing code to GitHub")
    parser.add_argument("--skip-issues", action="store_true", help="Skip creating issues")
    
    args = parser.parse_args()
    
    # Parse repo URL
    try:
        repo_owner, repo_name = parse_github_url(args.repo_url)
        print(f"Target repository: {repo_owner}/{repo_name}")
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    
    # Create temp directory
    temp_dir = "temp_test_repo"
    
    try:
        # Generate code
        create_local_files(temp_dir, args.modules)
        
        # Push to GitHub
        if not args.skip_push:
            push_to_github(args.repo_url, temp_dir)
        else:
            print("Skipping push (--skip-push)")
        
        # Create issues
        if not args.skip_issues:
            create_issues(repo_owner, repo_name, args.token, args.clusters, args.noise_ratio)
        else:
            print("Skipping issues (--skip-issues)")
        
        print("\n✅ All done!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            print(f"\nCleaning up {temp_dir}...")
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    exit(main())