import os
import random
import requests
import time
import subprocess
import shutil
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
load_dotenv(dotenv_path="backend/.env", override = False)

# Configuration
# GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def generate_math_code():
    """
    Generate source code for a small math utilities Python module.
    
    The returned string is a complete Python module defining functions: add, subtract, multiply, divide, power, sqrt, and factorial. The generated code intentionally omits safeguards: divide has no zero-division check, sqrt does not guard against negative inputs, and factorial does not handle negative values (which can cause infinite recursion).
    
    Returns:
        module_source (str): Multi-line Python source code for the math utilities module.
    """
    return """
import math

def add(a, b):
    \"\"\"Adds two numbers.\"\"\"
    return a + b

def subtract(a, b):
    \"\"\"Subtracts b from a.\"\"\"
    return a - b

def multiply(a, b):
    \"\"\"Multiplies two numbers.\"\"\"
    return a * b

def divide(a, b):
    \"\"\"Divides a by b.
    TODO: Add error handling for zero division.
    \"\"\"
    # Bug: No check for b == 0
    return a / b

def power(a, b):
    \"\"\"Returns a raised to the power of b.\"\"\"
    return a ** b

def sqrt(a):
    \"\"\"Returns the square root of a.\"\"\"
    # Bug: No check for negative numbers, will raise ValueError
    return math.sqrt(a)

def factorial(n):
    \"\"\"Calculates factorial of n.\"\"\"
    if n == 0:
        return 1
    # Bug: Infinite recursion for negative numbers
    return n * factorial(n - 1)
"""

def generate_string_code():
    """
    Return Python source code for a small string utilities module.
    
    The returned source defines: `reverse_string`, `to_upper`, `is_palindrome` (case-sensitive), and `truncate` (raises IndexError if `length > len(s)`).
    
    Returns:
        str: Multi-line Python source code implementing the string utility functions.
    """
    return """
def reverse_string(s):
    \"\"\"Reverses a string.\"\"\"
    return s[::-1]

def to_upper(s):
    \"\"\"Converts string to uppercase.\"\"\"
    return s.upper()

def is_palindrome(s):
    \"\"\"Checks if a string is a palindrome.\"\"\"
    # Bug: Case sensitive, so 'Racecar' returns False
    return s == s[::-1]

def truncate(s, length):
    \"\"\"Truncates string to length.\"\"\"
    # Bug: Might raise IndexError if length > len(s) depending on implementation, 
    # but python slicing is safe. Let's introduce a manual bug.
    if length > len(s):
        raise IndexError("Length is too large")
    return s[:length]
"""

def generate_user_manager_code():
    """
    Return Python source code for a simple UserManager class.
    
    The returned source defines a UserManager with an in-memory `users` dict and three methods:
    `add_user(user_id, name)` to store a user, `get_user(user_id)` which returns the stored name or `None` if not found, and `delete_user(user_id)` which contains a no-op bug and does not remove the user even when present.
    
    Returns:
        str: Python source code (multi-line string) that defines the described UserManager class.
    """
    return """
class UserManager:
    def __init__(self):
        self.users = {}

    def add_user(self, user_id, name):
        self.users[user_id] = name

    def get_user(self, user_id):
        # Bug: Returns None but doesn't raise error, caller might expect exception
        return self.users.get(user_id)

    def delete_user(self, user_id):
        # Bug: Does not actually delete the user
        if user_id in self.users:
            pass # Forgot to add 'del self.users[user_id]'
"""

def create_local_files(target_dir="."):
    """
    Create a project directory populated with generated Python modules and a README, replacing the directory if it already exists.
    
    Parameters:
        target_dir (str): Path to the directory to create or overwrite. The function will remove any existing directory at this path and write generated files: math_ops.py, string_utils.py, user_manager.py, and README.md.
    """
    print(f"Creating files in {target_dir}...")
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir)
    
    with open(os.path.join(target_dir, "math_ops.py"), "w") as f:
        f.write(generate_math_code())
        
    with open(os.path.join(target_dir, "string_utils.py"), "w") as f:
        f.write(generate_string_code())

    with open(os.path.join(target_dir, "user_manager.py"), "w") as f:
        f.write(generate_user_manager_code())
    
    with open(os.path.join(target_dir, "README.md"), "w") as f:
        f.write("# Test Project\n\nA project with some intentional bugs for testing clustering.\n")

def push_to_github(repo_url, target_dir="."):
    """
    Initialize a Git repository in target_dir, commit its contents, set the main branch, add the given remote, and push the commit to the remote repository.
    
    Parameters:
        repo_url (str): Remote Git repository URL to push to (e.g., https://github.com/owner/repo.git or git@github.com:owner/repo.git).
        target_dir (str): Path to the directory to initialize and push (defaults to current directory).
    
    Raises:
        ValueError: If repo_url does not match allowed GitHub URL patterns.
    
    Notes:
        - On git command failure the function prints an error message and does not raise.
        - Force-push is only used if the remote main branch is empty (for fresh repos).
        - If the remote main branch already has commits, a standard push is attempted instead.
        - To use this script, ensure the target GitHub repository is newly created and empty.
    """
    # Validate repo_url against allowed GitHub patterns to prevent command injection
    if not (repo_url.startswith("https://github.com/") or repo_url.startswith("git@github.com:")):
        raise ValueError(
            f"Invalid repo_url: '{repo_url}'. Must start with 'https://github.com/' or 'git@github.com:'"
        )
    
    print(f"Pushing to {repo_url}...")
    try:
        subprocess.run(["git", "init"], cwd=target_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=target_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit with buggy code"], cwd=target_dir, check=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=target_dir, check=True)
        subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=target_dir, check=True)
        
        # Check if the remote main branch is empty before deciding to force-push
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--heads", "origin", "main"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            remote_main_exists = result.stdout.strip() != ""
        except subprocess.CalledProcessError:
            remote_main_exists = False
        
        # Only force-push if remote main doesn't exist (fresh repo)
        if remote_main_exists:
            print("Remote main branch already exists. Using standard push (no force).")
            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=target_dir, check=True)
        else:
            print("Remote main branch is empty. Using force-push for fresh initialization.")
            subprocess.run(["git", "push", "-u", "-f", "origin", "main"], cwd=target_dir, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Git operation failed: {e}")

def create_issues(repo_owner, repo_name, token):
    """
    Create and post a shuffled set of clustered and noise GitHub issues to a repository.
    
    Generates predefined clusters of related bug reports (e.g., division-by-zero, sqrt negatives, palindrome case issues, no-op delete_user, truncate IndexError, factorial recursion) plus unrelated "noise" issues, shuffles the combined list, and creates each issue via the GitHub Issues REST API for the given repository. Prints progress for each created issue, sleeps briefly between requests to reduce rate-limit risk, and on HTTP 403 or 429 waits 60 seconds before continuing.
    
    Parameters:
        repo_owner (str): GitHub repository owner or organization name.
        repo_name (str): GitHub repository name.
        token (str): Personal access token used to authorize API requests.
    """
    print(f"Creating issues for {repo_owner}/{repo_name}...")
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # Define clusters of issues (same bug, different wording)
    issue_clusters = [
        # Cluster 1: Division by zero
        [
            {"title": "Division by zero error in math_ops", "body": "The divide function crashes when the second argument is 0.", "labels": ["bug"]},
            {"title": "App crashes when dividing by 0", "body": "I tried to use the divide function with 0 as the denominator and it raised a ZeroDivisionError.", "labels": ["bug", "critical"]},
            {"title": "Unhandled exception in divide function", "body": "We need to handle the case where b is 0 in the divide function.", "labels": ["enhancement"]},
            {"title": "math_ops.divide needs input validation", "body": "Please add a check to ensure we don't divide by zero.", "labels": ["bug"]},
        ],
        # Cluster 2: Sqrt negative number
        [
            {"title": "ValueError when calculating square root of negative numbers", "body": "sqrt(-1) crashes the program.", "labels": ["bug"]},
            {"title": "sqrt function should handle negative inputs gracefully", "body": "Maybe return None or a complex number instead of crashing?", "labels": ["enhancement"]},
            {"title": "Crash report: math domain error in sqrt", "body": "Got a math domain error when calling sqrt with a negative value.", "labels": ["bug"]},
        ],
        # Cluster 3: Palindrome case sensitivity
        [
            {"title": "is_palindrome should be case insensitive", "body": "is_palindrome('Racecar') returns False, which is unexpected.", "labels": ["bug"]},
            {"title": "Palindrome check fails for mixed case strings", "body": "The function seems to compare raw strings without normalizing case.", "labels": ["bug"]},
            {"title": "String utils palindrome bug with capital letters", "body": "Capital letters cause the palindrome check to fail.", "labels": ["bug"]},
            {"title": "Make is_palindrome robust to case", "body": "It should convert to lowercase before comparing.", "labels": ["enhancement"]},
        ],
        # Cluster 4: Delete user bug
        [
            {"title": "delete_user method doesn't remove the user from the list", "body": "I called delete_user but the user is still there.", "labels": ["bug", "critical"]},
            {"title": "Users still exist after calling delete_user", "body": "The delete_user function seems to do nothing.", "labels": ["bug"]},
            {"title": "UserManager.delete_user seems to be a no-op", "body": "Checked the code, it passes but doesn't delete.", "labels": ["bug"]},
            {"title": "Memory leak? Users not being deleted.", "body": "Our user list keeps growing even though we delete users.", "labels": ["bug"]},
        ],
        # Cluster 5: Truncate index error
        [
            {"title": "IndexError in truncate function for short strings", "body": "If I try to truncate a string to a length larger than the string, it crashes.", "labels": ["bug"]},
            {"title": "truncate throws exception if length is larger than string", "body": "Shouldn't it just return the whole string?", "labels": ["enhancement"]},
            {"title": "String truncation bug with large length", "body": "truncate('abc', 10) raises an error.", "labels": ["bug"]},
        ],
        # Cluster 6: Factorial recursion
        [
            {"title": "Factorial stack overflow on negative numbers", "body": "Calling factorial with a negative number causes infinite recursion.", "labels": ["bug"]},
            {"title": "Infinite loop in factorial", "body": "factorial(-1) never returns.", "labels": ["bug"]},
        ]
    ]

    # Flatten and add some noise
    all_issues = []
    for cluster in issue_clusters:
        all_issues.extend(cluster)

    # Add noise/unrelated issues
    noise_issues = [
        {"title": "Update README", "body": "Add installation instructions.", "labels": ["documentation"]},
        {"title": "Add CI/CD pipeline", "body": "We need GitHub Actions.", "labels": ["devops"]},
        {"title": "Refactor directory structure", "body": "Move files to src/.", "labels": ["refactor"]},
        {"title": "Add license", "body": "MIT License needed.", "labels": ["legal"]},
        {"title": "Support Python 3.12", "body": "Test with latest python.", "labels": ["enhancement"]},
        {"title": "Add logging to UserManager", "body": "We need to see when users are added.", "labels": ["enhancement"]},
        {"title": "Create a CLI interface", "body": "Would be nice to run this from command line.", "labels": ["enhancement"]},
        {"title": "Fix typo in comments", "body": "Some typos in docstrings.", "labels": ["documentation"]},
        {"title": "Add unit tests", "body": "We have 0% coverage.", "labels": ["testing"]},
        {"title": "Performance optimization for large numbers", "body": "Math ops are slow.", "labels": ["enhancement"]},
    ]
    
    all_issues.extend(noise_issues)
    
    # Shuffle to mix them up
    random.shuffle(all_issues)

    print(f"Generated {len(all_issues)} issues to create.")

    for i, issue in enumerate(all_issues):
        print(f"Creating issue {i+1}/{len(all_issues)}: {issue['title']}")
        
        # Attempt to create issue with retry logic for timeouts
        max_retries = 1
        retry_count = 0
        created = False
        
        while retry_count <= max_retries and not created:
            try:
                response = requests.post(url, json=issue, headers=headers, timeout=10)
                
                if response.status_code != 201:
                    print(f"Failed to create issue: {response.text}")
                    # If rate limited, wait a bit
                    if response.status_code == 403 or response.status_code == 429:
                        print("Rate limited, waiting 60s...")
                        time.sleep(60)
                
                created = True
            
            except requests.exceptions.Timeout:
                retry_count += 1
                if retry_count <= max_retries:
                    print(f"Timeout creating issue '{issue['title']}'. Retrying (attempt {retry_count + 1}/{max_retries + 1})...")
                    time.sleep(3)  # Wait before retry
                else:
                    print(f"Timeout creating issue '{issue['title']}' after {max_retries + 1} attempts. Skipping...")
                    created = True  # Mark as done to exit loop
            
            except requests.exceptions.RequestException as e:
                print(f"Request error while creating issue '{issue['title']}': {e}")
                print(f"Skipping issue...")
                created = True  # Mark as done to exit loop
        
        # Sleep a bit to avoid hitting secondary rate limits
        time.sleep(2)

def parse_github_url(repo_url: str) -> Tuple[str, str]:
    """
    Robustly parse a GitHub repository URL to extract owner and repo name.
    
    Supports both HTTPS and SSH URL formats:
    - HTTPS: https://github.com/owner/repo.git or https://github.com/owner/repo
    - SSH: git@github.com:owner/repo.git or git@github.com:owner/repo
    
    Parameters:
        repo_url (str): The GitHub repository URL to parse.
    
    Returns:
        Tuple[str, str]: A tuple of (repo_owner, repo_name).
    
    Raises:
        ValueError: If the URL format is unexpected or cannot be parsed into owner/repo.
    """
    try:
        # Handle SSH-style URLs (git@github.com:owner/repo.git)
        if repo_url.startswith("git@"):
            # Split on ':' to separate host from path
            if ":" not in repo_url:
                raise ValueError(f"Invalid SSH URL format: {repo_url}")
            
            _, path_part = repo_url.split(":", 1)
            # Remove trailing .git if present (exact match)
            if path_part.endswith(".git"):
                path_part = path_part[:-4]
            # Split path on '/'
            segments = path_part.split("/")
        else:
            # Handle HTTP(S) URLs
            parsed = urlparse(repo_url)
            path = parsed.path
            # Remove leading '/'
            path = path.lstrip("/")
            # Remove trailing '.git' (exact match)
            if path.endswith(".git"):
                path = path[:-4]
            # Split path on '/'
            segments = path.split("/")
        
        # Validate that we have at least owner and repo name
        if len(segments) < 2:
            raise ValueError(
                f"Could not extract owner and repo name from URL: {repo_url}. "
                f"Expected at least 2 path segments, got {len(segments)}."
            )
        
        repo_owner = segments[-2]
        repo_name = segments[-1]
        
        # Final validation: ensure both are non-empty
        if not repo_owner or not repo_name:
            raise ValueError(
                f"Extracted empty owner or repo name from URL: {repo_url}. "
                f"Got owner='{repo_owner}', repo='{repo_name}'."
            )
        
        return repo_owner, repo_name
    
    except ValueError:
        # Re-raise ValueError as-is
        raise
    except Exception as e:
        # Catch any other unexpected errors and wrap them
        raise ValueError(
            f"Unexpected error parsing GitHub URL '{repo_url}': {type(e).__name__}: {e}"
        )

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python generate_test_data.py <repo_url> <token>")
        sys.exit(1)
        
    repo_url = sys.argv[1]
    token = sys.argv[2]
    
    # Extract owner and repo name from URL with robust parsing for HTTPS and SSH formats
    try:
        repo_owner, repo_name = parse_github_url(repo_url)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Create a temporary directory for the repo
    temp_dir = "temp_test_repo"
    
    create_local_files(temp_dir)
    push_to_github(repo_url, temp_dir)
    create_issues(repo_owner, repo_name, token)
    
    # Cleanup
    # shutil.rmtree(temp_dir)
    print("Done!")