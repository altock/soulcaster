import argparse
import subprocess
import os
import re
import sys
import time
import json
import requests
import tempfile
import shutil
import random
import string
from pathlib import Path
from dotenv import load_dotenv

# Global state
LOG_BUFFER = []


def log(message: str):
    """Print message and append to global log buffer."""
    print(message)
    LOG_BUFFER.append(message)


def update_job(job_id: str, status: str, logs: str = None, pr_url: str = None):
    """
    Update the job record on the configured backend with a new status and optional metadata.
    
    Sends an HTTP PATCH to "{BACKEND_URL}/jobs/{job_id}" with a JSON payload containing
    "status" and, when provided, "logs" and "pr_url". If either `job_id` or the
    BACKEND_URL environment variable is missing the update is skipped. Exceptions
    raised while making the request are caught and printed.
    
    Parameters:
        job_id (str): Identifier of the job to update.
        status (str): New status value to set for the job.
        logs (str, optional): Optional log text to attach to the job.
        pr_url (str, optional): Optional pull request URL to attach to the job.
    """
    backend_url = os.getenv("BACKEND_URL")
    
    if not job_id or not backend_url:
        print("WARN: No JOB_ID or BACKEND_URL, skipping status update")
        return

    try:
        url = f"{backend_url}/jobs/{job_id}"
        payload = {"status": status}
        if logs:
            payload["logs"] = logs
        if pr_url:
            payload["pr_url"] = pr_url
            
        requests.patch(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to update job status: {e}")


def run_command(command, cwd=None, capture_output=True, env=None, log_output=True):
    """
    Run a shell command and return its standard output.
    
    Parameters:
        command (str): Shell command to execute.
        cwd (str | None): Working directory for the command; uses the current process cwd if None.
        capture_output (bool): If True, capture and return stdout (and stderr for logging); if False, output is not captured and an empty string is returned.
        env (Mapping[str, str] | None): Environment variables for the subprocess; uses the current process environment if None.
        log_output (bool): If True, log the command and any errors; if False, suppress logging (useful for sensitive operations like credential setup).
    
    Returns:
        str: The command's stdout with surrounding whitespace removed; returns an empty string if there is no output or if output capture is disabled.
    
    Raises:
        subprocess.CalledProcessError: If the command exits with a non-zero status.
    """
    try:
        if log_output:
            log(f"Running: {command}")
        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            text=True,
            env=env if env else os.environ
        )
        output = result.stdout.strip() if result.stdout else ""
        if output and log_output:
            # Log truncated output if too long
            display_out = output[:500] + "..." if len(output) > 500 else output
            # log(f"Output: {display_out}") # Too verbose?
        return output
    except subprocess.CalledProcessError as e:
        if log_output:
            log(f"Error running command: {command}")
            log(f"STDOUT: {e.stdout}")
            log(f"STDERR: {e.stderr}")
        raise


def parse_issue_url(url):
    """
    Extract the owner, repository name, and issue number from a GitHub issue URL.
    
    Parameters:
        url (str): A GitHub issue URL in the form "https://github.com/<owner>/<repo>/issues/<number>".
    
    Returns:
        tuple: `(owner, repo, issue_number)` — each element is a string.
    
    Raises:
        ValueError: If `url` does not match the expected GitHub issue pattern.
    """
    # Format: https://github.com/owner/repo/issues/number
    match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
    if not match:
        raise ValueError("Invalid GitHub issue URL")
    return match.group(1), match.group(2), match.group(3)


def get_github_username() -> str:
    """
    Retrieve the authenticated GitHub username.
    
    Queries the local GitHub CLI configuration to obtain the current user's login. Raises an exception if no username can be determined (for example, when GITHUB_TOKEN or CLI authentication is not configured).
    
    Returns:
        str: The GitHub username.
    """
    user = run_command("gh api user --jq .login")
    cleaned = user.strip()
    if not cleaned:
        raise Exception("Unable to determine GitHub username; ensure GITHUB_TOKEN is configured.")
    return cleaned


def ensure_fork(owner_name: str, repo_name: str) -> str:
    """
    Ensure the authenticated user has a fork of the specified repository, creating a uniquely named fork if one does not already exist.
    
    Parameters:
        owner_name (str): Owner of the original repository (e.g., "octocat").
        repo_name (str): Name of the original repository (e.g., "hello-world").
    
    Returns:
        tuple: (username, fork_name) where `username` is the authenticated GitHub username and `fork_name` is the existing or newly created fork repository name.
    
    Raises:
        Exception: If fork creation fails or the created fork is not accessible after retries.
    """
    username = get_github_username()
    # Add random suffix to ensure uniqueness
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    fork_name = f"aie-fork-{repo_name}-{random_suffix}"
    fork_ref = f"{username}/{fork_name}"
    
    # Check if fork already exists using REST API
    log(f"Checking if fork {fork_ref} exists via REST API...")
    try:
        result = run_command(f'gh api repos/{username}/{fork_name} --jq .full_name')
        if result and result.strip():
            log(f"Fork {fork_ref} already exists (found via REST API)")
            return username, fork_name
    except subprocess.CalledProcessError:
        log(f"Fork {fork_ref} does not exist yet")
    
    # Fork doesn't exist, create it with custom name
    log(f"Creating fork with name {fork_name}...")
    try:
        result = run_command(f"gh repo fork {owner_name}/{repo_name} --fork-name {fork_name} --clone=false --remote=false")
        log(f"Fork command completed: {result if result else '(no output)'}")
    except subprocess.CalledProcessError as e:
        log(f"Fork command error: {e}")
        # Check if fork was created despite error
        try:
            result = run_command(f'gh api repos/{username}/{fork_name} --jq .full_name')
            if result and result.strip():
                log(f"Fork exists despite error - proceeding")
                return username, fork_name
        except Exception as verify_error:
            log(f"Failed to verify fork existence after fork command error: {verify_error}")
        raise
    
    # Verify fork was created via REST API
    log(f"Verifying fork {fork_ref} was created...")
    for attempt in range(5):
        if attempt > 0:
            sleep_time = 2 ** attempt
            log(f"Waiting {sleep_time}s before retry {attempt + 1}/5...")
            time.sleep(sleep_time)
        
        try:
            result = run_command(f'gh api repos/{username}/{fork_name} --jq .full_name')
            if result and result.strip():
                log(f"Fork {fork_ref} is accessible: {result.strip()}")
                return username, fork_name
        except subprocess.CalledProcessError as e:
            if attempt == 4:
                log(f"Fork {fork_ref} still not accessible after retries.")
                log(f"Please check manually: https://github.com/{fork_ref}")
                raise Exception(f"Fork creation failed for {fork_ref}") from e
    
    return username, fork_name


def add_upstream_remote(owner_name: str, repo_name: str, cwd: str):
    """
    Ensure the local Git repository at `cwd` has an `upstream` remote pointing to the original repository.
    
    If an `upstream` remote is already configured, the function does nothing; otherwise it adds `upstream` with the URL https://github.com/{owner_name}/{repo_name}.git.
    
    Parameters:
        owner_name (str): GitHub owner or organization name of the original repository.
        repo_name (str): Repository name of the original repository.
        cwd (str): Filesystem path to the local Git repository where the remote should be configured.
    """
    try:
        run_command("git remote get-url upstream", cwd=cwd)
    except subprocess.CalledProcessError:
        run_command(
            f"git remote add upstream https://github.com/{owner_name}/{repo_name}.git",
            cwd=cwd,
        )


def get_default_branch(owner_name: str, repo_name: str) -> str:
    """
    Retrieve the repository's default branch name.
    
    Returns:
        branch_name (str): The repository's default branch (for example "main" or "master"); returns "main" if the default branch cannot be determined.
    """
    branch = run_command(
        f"gh repo view {owner_name}/{repo_name} --json defaultBranchRef --jq .defaultBranchRef.name"
    ).strip()
    return branch or "main"


def _run_agent_logic(issue_url):
    # Configure Kilo for Gemini if GEMINI_API_KEY is present
    """
    Automates fixing a GitHub issue by running Kilo in a forked repository, committing changes, and creating a pull request.
    
    Parameters:
        issue_url (str): URL of the GitHub issue to fix (e.g., "https://github.com/owner/repo/issues/123").
    
    Returns:
        str: The URL of the created pull request.
    
    Raises:
        Exception: If required environment configuration is missing (e.g., GIT_USER_EMAIL/GIT_USER_NAME), the issue cannot be found, Kilo exits with a non-zero code, or other operations (fork/clone/commit/push/pr creation) fail.
    """
    minimax_key = os.getenv("MINIMAX_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    if minimax_key or gemini_key:
        log("Configuring Kilo via config file...")
        
        # Define config path - Kilo uses ~/.kilocode/cli/config.json
        config_dir = Path.home() / ".kilocode" / "cli"
        config_path = config_dir / "config.json"
        
        log(f"DEBUG: Config path will be: {config_path}")
        
        # Ensure directory exists
        config_dir.mkdir(parents=True, exist_ok=True)
        
        providers = []
        
        if minimax_key:
            log("Configuring Minimax provider...")
            providers.append({
                "id": "default",
                "provider": "minimax",
                "minimaxBaseUrl": "https://api.minimax.io/anthropic",
                "minimaxApiKey": minimax_key,
                "apiModelId": "MiniMax-M2"
            })
        elif gemini_key:
            log("Configuring Gemini provider...")
            providers.append({
                "id": "default",
                "provider": "gemini",
                "geminiApiKey": gemini_key,
                "apiModelId": os.getenv("KILO_API_MODEL_ID", "gemini-2.5-flash-preview-04-17"),
                "enableUrlContext": True,
                "enableGrounding": True
            })

        # Create full config with autoApproval settings for autonomous operation
        config_data = {
            "version": "1.0.0",
            "mode": "code",
            "telemetry": True,
            "provider": "default",
            "providers": providers,
            "autoApproval": {
                "enabled": True,
                "read": {
                    "enabled": True,
                    "outside": True
                },
                "write": {
                    "enabled": True,
                    "outside": True,
                    "protected": False
                },
                "browser": {
                    "enabled": False
                },
                "retry": {
                    "enabled": False,
                    "delay": 10
                },
                "mcp": {
                    "enabled": True
                },
                "mode": {
                    "enabled": True
                },
                "subtasks": {
                    "enabled": True
                },
                "execute": {
                    "enabled": True,
                    "allowed": [
                        "ls",
                        "cat",
                        "echo",
                        "pwd",
                        "npm",
                        "node",
                        "yarn",
                        "pnpm",
                        "pip",
                        "python",
                        "python3",
                        "pytest",
                        "go",
                        "cargo",
                        "make"
                    ],
                    "denied": [
                        "rm -rf",
                        "sudo rm",
                        "mkfs",
                        "dd if="
                    ]
                },
                "question": {
                    "enabled": False,
                    "timeout": 60
                },
                "todo": {
                    "enabled": True
                }
            },
            "theme": "dark",
            "customThemes": {}
        }
        
        try:
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            log(f"Wrote Kilo config to {config_path}")
        except Exception as e:
            log(f"Failed to write Kilo config: {e}")
    
    owner, repo, issue_num = parse_issue_url(issue_url)
    log(f"Processing Issue #{issue_num} for {owner}/{repo}")

    temp_dir = tempfile.mkdtemp(prefix="kilo_agent_")
    log(f"Created temp directory: {temp_dir}")

    fork_owner, fork_name = ensure_fork(owner, repo)
    log(f"Using fork owned by {fork_owner}: {fork_name}")

    repo_dir = os.path.join(temp_dir, repo)

    log(f"Cloning {fork_owner}/{fork_name} into {repo_dir}...")
    run_command(f"gh repo clone {fork_owner}/{fork_name} {repo_dir}")

    cwd = os.path.abspath(repo_dir)
    add_upstream_remote(owner, repo, cwd)

    log("Configuring git user identity...")
    git_email = os.getenv("GIT_USER_EMAIL")
    git_name = os.getenv("GIT_USER_NAME")
    
    if not git_email or not git_name:
        raise Exception("GIT_USER_EMAIL and GIT_USER_NAME environment variables are required")
    
    run_command(f'git config user.email "{git_email}"', cwd=cwd)
    run_command(f'git config user.name "{git_name}"', cwd=cwd)
    
    if os.getenv("GITHUB_TOKEN"):
        log("Configuring git credentials with GITHUB_TOKEN...")
        gh_token = os.getenv("GITHUB_TOKEN")
        # Use environment variable to avoid embedding token in command string that gets logged
        credential_cmd = 'git config credential.helper "!f() { echo username=x-access-token; echo password=$GH_TOKEN_CRED; }; f"'
        # Pass token via env variable and suppress logging to prevent token exposure
        cred_env = os.environ.copy()
        cred_env["GH_TOKEN_CRED"] = gh_token
        run_command(credential_cmd, cwd=cwd, env=cred_env, log_output=False)

    log("Fetching issue details from upstream repo...")
    # First verify the issue exists and get full details
    try:
        issue_json = run_command(f"gh issue view {issue_num} --repo {owner}/{repo} --json number,title,body,url", cwd=cwd)
        issue_data = json.loads(issue_json)
        issue_title = issue_data.get('title', '')
        issue_body_text = issue_data.get('body', '')
        issue_url_full = issue_data.get('url', '')
    except subprocess.CalledProcessError:
        log(f"Issue #{issue_num} not found in {owner}/{repo}")
        log(f"Please verify the issue exists at: https://github.com/{owner}/{repo}/issues/{issue_num}")
        raise Exception(f"Issue #{issue_num} does not exist in {owner}/{repo}")
    except json.JSONDecodeError as e:
        log(f"Failed to parse issue JSON: {e}")
        raise
    
    issue_body = f"Title: {issue_title}\n\n{issue_body_text}"
    
    branch_name = f"fix/issue-{issue_num}"
    log(f"Creating branch {branch_name}...")
    try:
        run_command(f"git checkout -b {branch_name}", cwd=cwd)
    except:
        log(f"Branch {branch_name} might already exist, switching to it...")
        run_command(f"git checkout {branch_name}", cwd=cwd)

    log("Running Kilo to fix the issue...")
    safe_issue_body = issue_body.replace('"', '\\"')
    prompt = f"Fix the following issue: {safe_issue_body}"
    
    log(f"Running Kilo on {cwd}...")
    sys.stdout.flush()
    sys.stderr.flush()

    exit_code = subprocess.call(
        f'kilocode --auto "{prompt}"',
        cwd=cwd,
        shell=True,
        env=os.environ
    )
    
    if exit_code != 0:
        raise Exception(f"Kilo exited with code {exit_code}")
    
    log("kilo finished.")
    sys.stdout.flush()

    status = run_command("git status --porcelain", cwd=cwd)
    
    if not status:
        log("No changes detected via file system.")

    log("Changes detected. Committing...")
    run_command("git add .", cwd=cwd)
    commit_msg = f"Fix issue #{issue_num}"
    run_command(f"git commit -m '{commit_msg}'", cwd=cwd)
    
    log("Pushing branch...")
    run_command(f"git push -u origin {branch_name}", cwd=cwd)

    log("Creating Pull Request...")
    default_branch = get_default_branch(owner, repo)
    head_ref = f"{fork_owner}:{branch_name}"
    
    # Create a detailed PR body
    pr_title = f"🤖 Fix: {issue_title}"
    pr_body = f"""## 🔧 Automated Fix

This PR addresses issue #{issue_num}: **{issue_title}**

### 📋 Issue Reference
Closes #{issue_num}
Original issue: {issue_url_full}

### 🤖 How This Was Generated
This fix was automatically generated using AI-powered code analysis and remediation:
- **Tool**: Kilo AI Code Assistant
- **Analysis**: Analyzed the issue description and codebase context
- **Implementation**: Applied targeted fixes based on best practices

### ✅ Changes Made
Please review the changes in the Files Changed tab. The modifications were made to address the specific requirements outlined in the issue.

### 🧪 Testing
Please verify:
1. The fix addresses the issue as described
2. No regressions are introduced
3. Code quality and style are maintained

---
*Generated by Soulcaster AI Agent*
"""
    
    pr_url = run_command(
        f"gh pr create --repo {owner}/{repo} --head {head_ref} --base {default_branch} --title {json.dumps(pr_title)} --body {json.dumps(pr_body)}",
        cwd=cwd,
    )
    log(f"PR Created: {pr_url}")
    
    return pr_url.strip()


def apply_patches_from_markdown(markdown_text, cwd):
    """
    Extracts code blocks from markdown and writes them to files under the given directory.
    
    Supports code fences of the form ```lang:filename\n...``` where the filename after the colon is used as the target path relative to `cwd`. The function creates parent directories as needed and overwrites existing files with the extracted content.
    
    Parameters:
        markdown_text (str): Markdown text to scan for file-containing code blocks.
        cwd (str): Destination directory in which to create files referenced by code block filenames.
    
    Returns:
        True if one or more files were written, False otherwise.
    """
    # Regex to find code blocks with filenames
    # Format:
    # ```python:filename.py
    # code
    # ```
    # or
    # ```
    # # filename.py
    # code
    # ```

    # Pattern 1: ```lang:filename
    pattern1 = r"```\w+:([^\n]+)\n(.*?)```"
    matches1 = re.findall(pattern1, markdown_text, re.DOTALL)

    applied_count = 0

    for filename, content in matches1:
        filename = filename.strip()
        filepath = os.path.join(cwd, filename)
        log(f"Applying patch to {filename}...")
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                f.write(content)
            applied_count += 1
        except Exception as e:
            log(f"Failed to write {filename}: {e}")

    # Pattern 2: Filename in comment or just implied?
    # This is harder to guess. We'll stick to explicit patterns or maybe look for "File: filename" lines before blocks.

    return applied_count > 0

def main():
    """
    Orchestrates the CLI workflow to fix a GitHub issue and report progress to the backend.
    
    Loads environment variables, parses command-line arguments (issue URL and optional job ID), marks the backend job as "running", invokes the core agent workflow to produce a fix and obtain a PR URL, and updates the backend job to "success" with collected logs and the PR URL. If an exception occurs, logs the failure, updates the backend job to "failed" with logs, and exits the process with status code 1.
    """
    load_dotenv()  # Load API keys from .env
    
    parser = argparse.ArgumentParser(description="Fix a GitHub issue using Kilo CLI")
    parser.add_argument("issue_url", help="URL of the GitHub issue to fix")
    parser.add_argument("--job-id", help="Job ID for backend updates")
    args = parser.parse_args()

    job_id = args.job_id or os.getenv("JOB_ID")
    update_job(job_id, "running")
    
    try:
        pr_url = _run_agent_logic(args.issue_url)
        update_job(job_id, "success", "\n".join(LOG_BUFFER), pr_url=pr_url)
    except Exception as e:
        log(f"CRITICAL FAILURE: {e}")
        update_job(job_id, "failed", "\n".join(LOG_BUFFER))
        sys.exit(1)

if __name__ == "__main__":
    main()
