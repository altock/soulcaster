import argparse
import subprocess
import os
import re
import sys
import time

def run_command(command, cwd=None, capture_output=True, env=None):
    """Runs a shell command and returns the result."""
    try:
        print(f"Running: {command}")
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
        return result.stdout.strip() if result.stdout else ""
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        raise

def parse_issue_url(url):
    """Parses github issue URL to get owner, repo, and issue number."""
    # Format: https://github.com/owner/repo/issues/number
    match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
    if not match:
        raise ValueError("Invalid GitHub issue URL")
    return match.group(1), match.group(2), match.group(3)

from dotenv import load_dotenv

def main():
    load_dotenv()  # Load CODEX_API_KEY from .env
    parser = argparse.ArgumentParser(description="Fix a GitHub issue using Kilo CLI")
    parser.add_argument("issue_url", help="URL of the GitHub issue to fix")
    args = parser.parse_args()

    try:
        owner, repo, issue_num = parse_issue_url(args.issue_url)
        print(f"Processing Issue #{issue_num} for {owner}/{repo}")

        # 1. Clone the repo
        repo_url = f"https://github.com/{owner}/{repo}.git"
        repo_dir = repo
        
        if os.path.exists(repo_dir):
            print(f"Directory {repo_dir} already exists. Using existing directory.")
        else:
            print(f"Cloning {repo_url}...")
            run_command(f"gh repo clone {owner}/{repo}")

        cwd = os.path.abspath(repo_dir)

        # 2. Get Issue Details
        print("Fetching issue details...")
        issue_body = run_command(f"gh issue view {issue_num} --json title,body --template 'Title: {{{{ .title }}}}\n\n{{{{ .body }}}}'", cwd=cwd)
        
        # 3. Create Branch
        branch_name = f"fix/issue-{issue_num}"
        print(f"Creating branch {branch_name}...")
        try:
            run_command(f"git checkout -b {branch_name}", cwd=cwd)
        except:
            print(f"Branch {branch_name} might already exist, switching to it...")
            run_command(f"git checkout {branch_name}", cwd=cwd)

        # 4. Run Codex
        print("Running Codex to fix the issue...")
        # Escape double quotes in issue body for the command line
        safe_issue_body = issue_body.replace('"', '\\"')
        prompt = f"Fix the following issue: {safe_issue_body}"
        
        # We use kilocode --auto for autonomous, non-interactive execution
        print(f"Running Kilo on {cwd}...")
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Use subprocess.call for simpler process management
        # It waits for completion and returns the exit code
        exit_code = subprocess.call(
            f'kilocode --auto "{prompt}"',
            cwd=cwd,
            shell=True,
            env=os.environ
        )
        
        if exit_code != 0:
            raise Exception(f"Kilo exited with code {exit_code}")
        
        print("kilo finished.")
        sys.stdout.flush()

        # 5. Check for changes
        status = run_command("git status --porcelain", cwd=cwd)
        
        if not status:
            print("No changes detected via file system.")

        # 6. Commit and Push
        print("Changes detected. Committing...")
        run_command("git add .", cwd=cwd)
        # Get a safe commit message
        commit_msg = f"Fix issue #{issue_num}"
        run_command(f"git commit -m '{commit_msg}'", cwd=cwd)
        
        print("Pushing branch...")
        run_command(f"git push -u origin {branch_name}", cwd=cwd)

        # 7. Create PR
        print("Creating Pull Request...")
        pr_url = run_command(f"gh pr create --title 'Fix issue #{issue_num}' --body 'Fixes #{issue_num}\n\nAutomated fix by Kilo.'", cwd=cwd)
        print(f"PR Created: {pr_url}")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

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
        print(f"Applying patch to {filename}...")
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w') as f:
                f.write(content)
            applied_count += 1
        except Exception as e:
            print(f"Failed to write {filename}: {e}")

    # Pattern 2: Filename in comment or just implied?
    # This is harder to guess. We'll stick to explicit patterns or maybe look for "File: filename" lines before blocks.
    
    return applied_count > 0

if __name__ == "__main__":
    main()
