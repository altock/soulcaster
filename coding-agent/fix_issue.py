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
from pathlib import Path
from dotenv import load_dotenv

# Global state
LOG_BUFFER = []

def log(message: str):
    """Print message and append to global log buffer."""
    print(message)
    LOG_BUFFER.append(message)

def update_job(job_id: str, status: str, logs: str = None):
    """Update job status in backend."""
    backend_url = os.getenv("BACKEND_URL")
    
    if not job_id or not backend_url:
        print("WARN: No JOB_ID or BACKEND_URL, skipping status update")
        return

    try:
        url = f"{backend_url}/jobs/{job_id}"
        payload = {"status": status}
        if logs:
            payload["logs"] = logs
            
        requests.patch(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to update job status: {e}")

def run_command(command, cwd=None, capture_output=True, env=None):
    """Runs a shell command and returns the result."""
    try:
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
        if output:
            # Log truncated output if too long
            display_out = output[:500] + "..." if len(output) > 500 else output
            # log(f"Output: {display_out}") # Too verbose?
        return output
    except subprocess.CalledProcessError as e:
        log(f"Error running command: {command}")
        log(f"STDOUT: {e.stdout}")
        log(f"STDERR: {e.stderr}")
        raise

def parse_issue_url(url):
    """Parses github issue URL to get owner, repo, and issue number."""
    # Format: https://github.com/owner/repo/issues/number
    match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
    if not match:
        raise ValueError("Invalid GitHub issue URL")
    return match.group(1), match.group(2), match.group(3)

def _run_agent_logic(issue_url):
    # Configure Kilo for Gemini if GEMINI_API_KEY is present
    # Configure Kilo
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
        
        # Write config file
        try:
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            log(f"Wrote Kilo config to {config_path}")
        except Exception as e:
            log(f"Failed to write Kilo config: {e}")
    
    owner, repo, issue_num = parse_issue_url(issue_url)
    log(f"Processing Issue #{issue_num} for {owner}/{repo}")

    # 1. Clone the repo
    # Create a temp dir to avoid nesting git repos
    temp_dir = tempfile.mkdtemp(prefix="kilo_agent_")
    log(f"Created temp directory: {temp_dir}")
    
    repo_url = f"https://github.com/{owner}/{repo}.git"
    repo_dir = os.path.join(temp_dir, repo)
    
    log(f"Cloning {repo_url} into {repo_dir}...")
    run_command(f"gh repo clone {owner}/{repo} {repo_dir}")

    cwd = os.path.abspath(repo_dir)

    # Configure git user identity (required for commits)
    log("Configuring git user identity...")
    git_email = os.getenv("GIT_USER_EMAIL")
    git_name = os.getenv("GIT_USER_NAME")
    
    if not git_email or not git_name:
        raise Exception("GIT_USER_EMAIL and GIT_USER_NAME environment variables are required")
    
    run_command(f'git config user.email "{git_email}"', cwd=cwd)
    run_command(f'git config user.name "{git_name}"', cwd=cwd)
    
    # Configure git to use GH_TOKEN for authentication
    if os.getenv("GH_TOKEN"):
        log("Configuring git credentials with GH_TOKEN...")
        # Set up git credential helper to use the token
        gh_token = os.getenv("GH_TOKEN")
        # Configure git to use the token for GitHub
        run_command(f'git config credential.helper "!f() {{ echo username=x-access-token; echo password={gh_token}; }}; f"', cwd=cwd)

    # 2. Get Issue Details
    log("Fetching issue details...")
    issue_body = run_command(f"gh issue view {issue_num} --json title,body --template 'Title: {{{{ .title }}}}\n\n{{{{ .body }}}}'", cwd=cwd)
    
    # 3. Create Branch
    branch_name = f"fix/issue-{issue_num}"
    log(f"Creating branch {branch_name}...")
    try:
        run_command(f"git checkout -b {branch_name}", cwd=cwd)
    except:
        log(f"Branch {branch_name} might already exist, switching to it...")
        run_command(f"git checkout {branch_name}", cwd=cwd)

    # 4. Run Kilo
    log("Running Kilo to fix the issue...")
    # Escape double quotes in issue body for the command line
    safe_issue_body = issue_body.replace('"', '\\"')
    prompt = f"Fix the following issue: {safe_issue_body}"
    
    # We use kilocode --auto for autonomous, non-interactive execution
    log(f"Running Kilo on {cwd}...")
    sys.stdout.flush()
    sys.stderr.flush()
    
    # Use subprocess.call instead of subprocess.run for better output streaming
    # subprocess.call inherits stdout/stderr by default, allowing Kilo's output to appear in real-time
    # Do NOT use --nosplash flag as it can interfere with Kilo's interactive prompts
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

    # 5. Check for changes
    status = run_command("git status --porcelain", cwd=cwd)
    
    if not status:
        log("No changes detected via file system.")

    # 6. Commit and Push
    log("Changes detected. Committing...")
    run_command("git add .", cwd=cwd)
    # Get a safe commit message
    commit_msg = f"Fix issue #{issue_num}"
    run_command(f"git commit -m '{commit_msg}'", cwd=cwd)
    
    log("Pushing branch...")
    run_command(f"git push -u origin {branch_name}", cwd=cwd)

    # 7. Create PR
    log("Creating Pull Request...")
    pr_url = run_command(f"gh pr create --title 'Fix issue #{issue_num}' --body 'Fixes #{issue_num}\n\nAutomated fix by Kilo.'", cwd=cwd)
    log(f"PR Created: {pr_url}")

def apply_patches_from_markdown(markdown_text, cwd):
    """Parses markdown code blocks and writes them to files."""
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
    load_dotenv()  # Load API keys from .env
    
    parser = argparse.ArgumentParser(description="Fix a GitHub issue using Kilo CLI")
    parser.add_argument("issue_url", help="URL of the GitHub issue to fix")
    parser.add_argument("--job-id", help="Job ID for backend updates")
    args = parser.parse_args()

    job_id = args.job_id or os.getenv("JOB_ID")
    update_job(job_id, "running")
    
    try:
        _run_agent_logic(args.issue_url)
        update_job(args.job_id, "success", "\n".join(LOG_BUFFER))
    except Exception as e:
        log(f"CRITICAL FAILURE: {e}")
        update_job(args.job_id, "failed", "\n".join(LOG_BUFFER))
        sys.exit(1)

if __name__ == "__main__":
    main()
