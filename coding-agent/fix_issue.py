import argparse
import subprocess
import os
import re
import sys
import time
import json
from pathlib import Path

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
    load_dotenv()  # Load API keys from .env

    # Configure Kilo for Gemini if GEMINI_API_KEY is present
    # Configure Kilo for Gemini if GEMINI_API_KEY is present
    if os.getenv("GEMINI_API_KEY"):
        print("Configuring Kilo for Gemini via config file...")
        
        # Define config path
        config_dir = Path.home() / ".kilocode"
        config_path = config_dir / "config.json"
        
        # Ensure directory exists
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create config content
        # Create config content
        config_data = {
            "version": "1.0.0",
            "mode": "code",
            "telemetry": True,
            "provider": "default",
            "providers": [
                {
                    "id": "default",
                    "provider": "gemini",
                    "geminiApiKey": os.getenv("GEMINI_API_KEY"),
                    "apiModelId": os.getenv("KILO_API_MODEL_ID", "gemini-2.5-flash-preview-04-17"),
                    "googleGeminiBaseUrl": "",
                    "enableUrlContext": False,
                    "enableGrounding": False
                }
            ],
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
                json.dump(config_data, f, indent=4)
            print(f"Wrote Kilo config to {config_path}")
        except Exception as e:
            print(f"Failed to write Kilo config: {e}")
            # Fallback to env vars just in case? 
            # The user specifically asked for config file, so maybe not.
            # But let's keep it clean and just rely on the file.
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

        # 4. Run Kilo
        print("Running Kilo to fix the issue...")
        # Escape double quotes in issue body for the command line
        safe_issue_body = issue_body.replace('"', '\\"')
        prompt = f"""
You are an autonomous senior software engineer running inside a Kilo cloud coding agent on a freshly checked-out Git repository.

You are currently inside the root of the target repository. You have full read/write access to the working tree and are allowed to run commands to inspect, build, test, and modify the project. A separate orchestrator (outside of you) will handle git commits, pushing, and pull request creation, so DO NOT run any git commands yourself.

-----------------
Primary objective
-----------------
Given the following GitHub issue, your job is to:

1. Fully understand the problem/feature request.
2. Inspect the codebase to locate the relevant modules, entrypoints, and tests.
3. Infer and install any missing dependencies needed to build and test the project.
4. Implement the fix or feature with clean, idiomatic code consistent with the existing style.
5. Add or update automated tests to cover the change where appropriate.
6. Run the test suite and any obvious checks (lint/build) to validate the change.
7. Leave the working directory in a consistent, buildable state with no obviously broken behavior.

----------------
GitHub issue
----------------
{safe_issue_body}

--------------------------
Environment / behavior
--------------------------
Follow these guidelines:

1. Repository understanding
   - Start by running simple inspection commands (e.g. `ls`, `cat` relevant files) to understand the project layout.
   - Detect the language and ecosystem by inspecting files and lockfiles:
     - For Node/TypeScript/JavaScript: look for package.json, pnpm-lock.yaml, yarn.lock, etc.
     - For Python: look for pyproject.toml, requirements.txt, Pipfile, poetry.lock, etc.
     - For other ecosystems, infer the standard build/test workflow from configuration files.

2. Dependency management
   - If the project has an existing lockfile or clear package manager, use that:
     - npm: `npm install`
     - pnpm: `pnpm install`
     - yarn: `yarn install`
     - Python: `pip install -r requirements.txt`, `pip install -e .`, or equivalent as indicated by the project.
   - Do NOT introduce a new package manager if one is already in use.
   - Only add new dependencies if they are clearly required by the change; prefer using existing utilities and libraries already present in the project.

3. Implementing the change
   - Before editing, locate the minimal, most appropriate place in the codebase to implement the fix or feature.
   - Preserve existing abstractions, layering, and naming conventions.
   - Avoid large-scale refactors unless absolutely necessary to implement the requested change.
   - If the fix requires non-trivial logic, factor it into small, testable functions with clear responsibilities.
   - Add comments only where they clarify non-obvious behavior; do not over-comment trivial code.

4. Testing and verification
   - Identify the project’s existing test framework and typical commands from config and docs (e.g., `npm test`, `pytest`, `go test ./...`, etc.).
   - Add or update tests so that the issue’s desired behavior is explicitly validated.
   - Run the relevant test command(s) after making changes.
   - If a full test suite is extremely large, run the most targeted subset that covers your changes plus any obvious fast smoke tests.

5. Error handling and robustness
   - Prefer explicit error handling over silent failures.
   - Avoid logging sensitive data; follow any existing logging patterns in the repository.
   - Treat TODOs or FIXMEs carefully; do not remove them unless you have fully addressed them.

6. Safety and constraints
   - DO NOT run any destructive shell commands (e.g., `rm -rf`, formatting disks, or anything that could wipe the repository or system).
   - DO NOT run any git commands (no `git commit`, `git push`, `git rebase`, etc.). The orchestrator will handle all git operations.
   - Work only inside the repository’s directory tree.

7. Communication / outputs
   - At the end of your work, print a concise but detailed summary including:
     - A high-level description of what you changed to address the issue.
     - A list of key files you modified and their roles.
     - Any new dependencies you added or removed.
     - The exact test commands you ran and their results.
     - Any limitations, assumptions, or follow-up work that might still be needed if the issue description was ambiguous.

---------------
Definition of done
---------------
- The behavior described in the GitHub issue is implemented or the bug is fixed.
- The code compiles/builds successfully.
- Relevant tests pass, and new/updated tests clearly demonstrate the fix/feature.
- No obviously unrelated files are modified.
- You have output a final summary describing the change, affected files, dependencies, and tests executed.
"""
        
        # We use kilocode --auto for autonomous, non-interactive execution
        print(f"Running Kilo on {cwd}...")
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Use subprocess.run with unbuffered output for live streaming
        result = subprocess.run(
            f'kilocode --auto "{prompt}"',
            cwd=cwd,
            shell=True,
            env=os.environ,
            stdout=None,  # Inherit stdout for live output
            stderr=None   # Inherit stderr for live output
        )
        exit_code = result.returncode
        
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
