import asyncio
import json
import logging
import os
import time
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

try:
    from e2b_code_interpreter import AsyncSandbox
except ImportError:
    AsyncSandbox = None

from models import AgentJob, CodingPlan, IssueCluster
from store import get_job, update_job, update_cluster
from agent_runner import AgentRunner, register_runner
import job_logs_manager
from blob_storage import upload_job_logs_to_blob

logger = logging.getLogger(__name__)

# Template ID for the Kilocode sandbox.
KILOCODE_TEMPLATE_ID = os.getenv("KILOCODE_TEMPLATE_ID", "base") 

AGENT_SCRIPT = r"""
import os
import sys
import json
import subprocess
import time
import shlex
import re
from pathlib import Path

def log(msg):
    print(msg)
    sys.stdout.flush()

def run_command(cmd, cwd=None, env=None, log_cmd=None, sensitive=False):
    log(f"Running: {log_cmd or cmd}")
    try:
        subprocess.check_call(cmd, shell=True, cwd=cwd, env=env)
    except subprocess.CalledProcessError as e:
        if sensitive:
            log("Command failed (details redacted).")
            raise subprocess.CalledProcessError(e.returncode, "<redacted>") from None
        log(f"Command failed: {e}")
        raise

def run_capture(cmd, cwd=None, env=None):
    log(f"Running: {cmd}")
    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out = (proc.stdout or "").strip()
    if out:
        log(out)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)
    return out

def try_diagnostic(cmd, cwd=None):
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy(),
        )
        out = (proc.stdout or "").strip()
        if out:
            log(f"[diag] {cmd}\n{out}")
        else:
            log(f"[diag] {cmd} (no output)")
    except Exception as e:
        log(f"[diag] {cmd} failed: {e}")

def configure_kilocode():
    # Pre-seed Kilo config for non-interactive sandboxes.
    #
    # Kilo Gateway uses browser-based device auth by default, which will hang in E2B.
    # If we have provider credentials (e.g. Minimax/Gemini), write a config file so
    # `kilocode --auto` can run headlessly.
    config_dir = Path.home() / ".kilocode" / "cli"
    config_path = config_dir / "config.json"
    config_dir.mkdir(parents=True, exist_ok=True)

    explicit_config_json = (os.getenv("KILOCODE_CONFIG_JSON") or "").strip()
    provider_preference = (os.getenv("KILOCODE_PROVIDER") or "").strip().lower()
    minimax_key = (os.getenv("MINIMAX_API_KEY") or os.getenv("MINIMAX_API_TOKEN") or "").strip()
    minimax_base_url = (os.getenv("MINIMAX_BASE_URL") or "https://api.minimax.io/anthropic").strip()
    gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    api_model_id = (os.getenv("KILO_API_MODEL_ID") or "").strip()

    # If a config already exists, respect it and avoid overwriting settings.
    if config_path.exists():
        log(f"Kilo config already exists at {config_path}; leaving as-is")
        return

    if explicit_config_json:
        with open(config_path, "w") as f:
            f.write(explicit_config_json)
        log(f"Wrote Kilo config to {config_path}")
        return

    provider_cfg = None

    def _want(provider: str) -> bool:
        return (not provider_preference) or (provider_preference == provider)

    # Prefer Gemini by default when available to avoid provider billing/balance issues.
    if gemini_key and _want("gemini"):
        provider_cfg = {
            "id": "default",
            "provider": "gemini",
            "geminiApiKey": gemini_key,
            "apiModelId": api_model_id or "gemini-3-flash-preview",
            "enableUrlContext": False,
            "enableGrounding": False,
        }
    elif minimax_key and _want("minimax"):
        provider_cfg = {
            "id": "default",
            "provider": "minimax",
            "minimaxBaseUrl": minimax_base_url,
            "minimaxApiKey": minimax_key,
        }
        if api_model_id:
            provider_cfg["apiModelId"] = api_model_id
        else:
            provider_cfg["apiModelId"] = "MiniMax-M2"

    if not provider_cfg:
        log(
            "No Kilo provider credentials found (KILOCODE_CONFIG_JSON/GEMINI_API_KEY/MINIMAX_API_KEY). "
            "Kilo may prompt for device auth and hang in a headless sandbox."
        )
        return

    config_data = {
        "version": "1.0.0",
        "mode": "code",
        "telemetry": True,
        "provider": "default",
        "providers": [provider_cfg],
        "autoApproval": {
            "enabled": True,
            "read": {"enabled": True, "outside": True},
            "write": {"enabled": True, "outside": True, "protected": False},
            "browser": {"enabled": False},
            "retry": {"enabled": False, "delay": 10},
            "mcp": {"enabled": True},
            "mode": {"enabled": True},
            "subtasks": {"enabled": True},
            "execute": {
                "enabled": True,
                "allowed": ["ls", "cat", "echo", "pwd", "npm", "node", "yarn", "pnpm", "pip", "python", "python3", "pytest", "go", "cargo", "make", "git", "gh"],
                "denied": ["rm -rf", "sudo rm", "mkfs", "dd if="],
            },
            "question": {"enabled": False, "timeout": 60},
            "todo": {"enabled": True},
        },
        "theme": "dark",
        "customThemes": {},
    }

    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)
    log(f"Wrote Kilo config to {config_path}")

def _stream_process_with_pty(argv, cwd):
    # Stream output live and auto-accept first-run prompts by pressing Enter.
    import os
    import pty
    import select
    import subprocess
    import time
    import signal

    master_fd, slave_fd = pty.openpty()
    try:
        proc = subprocess.Popen(
            argv,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=cwd,
            text=False,
            env=os.environ.copy(),
        )
    finally:
        os.close(slave_fd)

    buffer = b""
    last_auto_enter = 0.0
    auth_wait_started = None
    auth_url = None
    auth_code = None
    auth_timeout_seconds = int(os.getenv("KILOCODE_AUTH_TIMEOUT_SECONDS", "60"))

    def maybe_auto_enter(text: str):
        nonlocal last_auto_enter
        now = time.time()
        if now - last_auto_enter < 0.75:
            return
        # Heuristics: Kilo uses a first-run wizard with question marks and selection prompts.
        triggers = [
            "Please select which provider you would like to use",
            "To get you started, please fill out",
            "? ",
            "navigate",
            "Configuration",
        ]
        if any(t in text for t in triggers):
            os.write(master_fd, b"\n")
            last_auto_enter = now
            log("[auto] pressed Enter to accept default")

    def maybe_detect_auth(text: str):
        nonlocal auth_wait_started, auth_url, auth_code
        if "Visit:" in text:
            # Example: "Visit: https://app.kilo.ai/device-auth?code=XXXX-YYYY"
            auth_url = text.split("Visit:", 1)[1].strip() or auth_url
        if text.startswith("Verification code:"):
            auth_code = text.split("Verification code:", 1)[1].strip() or auth_code
        if "Waiting for authorization" in text:
            if auth_wait_started is None:
                auth_wait_started = time.time()
                log(
                    f"[auth] waiting for Kilo Gateway device auth (timeout {auth_timeout_seconds}s)"
                )

    try:
        while True:
            r, _, _ = select.select([master_fd], [], [], 0.2)
            if master_fd in r:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError as e:
                    # Common PTY behavior: when the slave side closes, reads on the master
                    # can raise EIO instead of returning b"".
                    if getattr(e, "errno", None) == 5:
                        break
                    raise
                if not chunk:
                    break
                buffer += chunk
                # Emit line by line to keep logs readable
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    text = line.decode(errors="replace")
                    log(text)
                    maybe_auto_enter(text)
                    maybe_detect_auth(text)
            if auth_wait_started is not None and (time.time() - auth_wait_started) > auth_timeout_seconds:
                log(
                    "[auth] timed out waiting for device auth; canceling kilocode run. "
                    "To run non-interactively, set KILOCODE_SEED_CONFIG=true and provide a gateway key/token in the sandbox, "
                    "or pre-bake ~/.kilocode/cli/config.json into the E2B template."
                )
                if auth_url or auth_code:
                    log(f"[auth] url={auth_url or ''} code={auth_code or ''}".strip())
                try:
                    proc.send_signal(signal.SIGINT)
                except Exception:
                    pass
                try:
                    proc.kill()
                except Exception:
                    pass
                return 1
            if proc.poll() is not None:
                break
        # Flush remainder
        if buffer:
            text = buffer.decode(errors="replace")
            for line in text.splitlines():
                log(line)
                maybe_auto_enter(line)
                maybe_detect_auth(line)
        return proc.wait()
    finally:
        try:
            os.close(master_fd)
        except Exception:
            pass

def main():
    # Avoid committing __pycache__/pyc artifacts (and keep repos clean).
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    # 1. Read Plan
    with open("/tmp/plan.json", "r") as f:
        plan = json.load(f)

    configure_kilocode()
    
    repo_url = os.getenv("REPO_URL")
    if not repo_url:
        raise Exception("REPO_URL env var missing")

    # 2. Extract owner/repo
    # https://github.com/owner/repo.git or https://github.com/owner/repo
    parts = repo_url.strip("/").replace(".git", "").split("/")
    repo_name = parts[-1]
    owner = parts[-2]
    
    # 3. Clone
    # We use GITHUB_TOKEN from env implicitly with gh cli. If gh can't access the repo
    # (private repo, missing scopes, etc) try a git clone fallback (without leaking the token in logs).
    github_token = (os.getenv("GITHUB_TOKEN") or "").strip()
    askpass_path = None
    if github_token:
        log(f"GITHUB_TOKEN present (len={len(github_token)})")
        os.environ["GITHUB_TOKEN"] = github_token
        # Configure git non-interactively (clone/push) without embedding tokens in URLs or logs.
        askpass_path = "/tmp/git_askpass.sh"
        with open(askpass_path, "w") as f:
            f.write(
                "#!/bin/sh\n"
                'case "$1" in\n'
                '  *Username*) echo "x-access-token";;\n'
                '  *Password*) echo "$GITHUB_TOKEN";;\n'
                '  *) echo "";;\n'
                "esac\n"
            )
        os.chmod(askpass_path, 0o700)
    else:
        log("GITHUB_TOKEN missing; cloning may fail for private repositories.")

    log(f"Cloning {owner}/{repo_name} from {repo_url}...")
    try:
        run_command(f"gh repo clone {owner}/{repo_name} repo")
    except Exception:
        # Log a bit of context to help debug private-repo auth issues.
        try_diagnostic("gh --version")
        try_diagnostic("gh auth status")  # Removed -t flag to avoid leaking token
        try_diagnostic("gh api user -q .login")
        try_diagnostic(f"gh api repos/{owner}/{repo_name} -q .full_name")

        if not (github_token and repo_url.startswith("https://github.com/")):
            raise

        # Last-resort fallback: git clone with GIT_ASKPASS (never embeds token in URL/command).
        if not askpass_path:
            raise
        clone_env = os.environ.copy()
        clone_env["GIT_ASKPASS"] = askpass_path
        clone_env["GIT_TERMINAL_PROMPT"] = "0"
        clone_env["GIT_ASKPASS_REQUIRE"] = "force"
        run_command(
            f"git clone {shlex.quote(repo_url)} repo",
            env=clone_env,
            sensitive=True,
        )
    cwd = os.path.abspath("repo")

    # 4. Git Config
    run_command('git config user.email "agent@soulcaster.dev"', cwd=cwd)
    run_command('git config user.name "Soulcaster Agent"', cwd=cwd)

    # 5. Branch
    branch_name = f"fix/soulcaster-{int(time.time())}"
    run_command(f"git checkout -b {branch_name}", cwd=cwd)

    # 6. Create empty commit and push to create draft PR early
    log("Creating initial commit and draft PR...")
    commit_title = f"WIP: {plan['title']}"
    run_command(f"git commit --allow-empty -m {json.dumps(commit_title)}", cwd=cwd)

    # Push branch
    push_env = os.environ.copy()
    push_env["GIT_TERMINAL_PROMPT"] = "0"
    if askpass_path:
        push_env["GIT_ASKPASS"] = askpass_path
        push_env["GIT_ASKPASS_REQUIRE"] = "force"
    run_command(f"git push -u origin {branch_name}", cwd=cwd, env=push_env, sensitive=bool(askpass_path))

    # Create DRAFT PR immediately
    pr_title = f"Fix: {plan['title']}"
    pr_body = f"🚧 Draft PR - Automated fix in progress...\\n\\n{plan['description']}\\n\\nThis PR will be marked as ready once the automated changes are complete."
    pr_url = ""

    # Write draft PR body to temp file to avoid shell escaping issues
    draft_pr_body_file = "/tmp/draft_pr_body.txt"
    with open(draft_pr_body_file, "w") as f:
        f.write(pr_body)

    # Try to create draft PR (gh pr create outputs URL to stdout by default)
    try:
        pr_url = run_capture(
            f"gh pr create --repo {json.dumps(f'{owner}/{repo_name}')} "
            f"--title {json.dumps(pr_title)} --body-file {draft_pr_body_file} "
            f"--head {json.dumps(branch_name)} --draft",
            cwd=cwd,
        ).strip()
        log(f"Draft PR created: {pr_url}")
    except Exception as e:
        # Fallback: try without --json flag
        log(f"--json flag failed, trying without: {e}")
        proc_result = subprocess.run(
            f"gh pr create --repo {json.dumps(f'{owner}/{repo_name}')} "
            f"--title {json.dumps(pr_title)} --body-file {draft_pr_body_file} "
            f"--head {json.dumps(branch_name)} --draft",
            shell=True,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        out = (proc_result.stdout or "").strip()
        if out:
            log(out)

        # Try to extract URL from output or "already exists" message
        match = re.search(r"https://github\.com/[\w\-_]+/[\w\-_]+/pull/\d+", out)
        if match:
            pr_url = match.group(0)
            log(f"Draft PR URL extracted: {pr_url}")
        else:
            log("Could not extract draft PR URL, will retry after coding")

    if pr_url:
        log(f"__SOULCASTER_PR_URL__={pr_url}")

    # 7. Run Kilocode to make the actual changes
    prompt = f"Executing Coding Plan: {plan['title']}\n\n"
    prompt += f"Description: {plan['description']}\n\n"
    prompt += f"Tasks:\n"
    for task in plan.get('tasks', []):
        prompt += f"- {task}\n"
    
    log("Starting Kilocode...")
    exit_code = _stream_process_with_pty(["kilocode", "--auto", prompt], cwd=cwd)
    log(f"Kilocode exit code: {exit_code}")
    if exit_code != 0:
        raise subprocess.CalledProcessError(exit_code, "kilocode --auto")

    # 8. Commit Kilocode changes and push
    log("Committing changes made by Kilocode...")
    run_command("find . -type d -name '__pycache__' -prune -exec rm -rf {} + || true", cwd=cwd)
    run_command("find . -type f -name '*.pyc' -delete || true", cwd=cwd)

    run_command(f"git add .", cwd=cwd)

    # Check if anything to commit
    status = run_capture("git status --porcelain", cwd=cwd)
    if not status:
        log("No changes detected from Kilocode; skipping commit.")
    else:
        commit_msg = f"Fix: {plan['title']}"
        run_command(f"git commit -m {json.dumps(commit_msg)}", cwd=cwd)

        # Push changes
        run_command(f"git push", cwd=cwd, env=push_env, sensitive=bool(askpass_path))
        log("Changes pushed successfully")

    # 9. If draft PR wasn't created, try to find or create it now
    if not pr_url:
        log("Draft PR was not created earlier, trying to find or create PR now...")

        # First, try to find existing PR by branch
        try:
            pr_url = run_capture(
                f"gh pr list --repo {json.dumps(f'{owner}/{repo_name}')} "
                f"--head {json.dumps(branch_name)} --json url -q '.[0].url'",
                cwd=cwd,
            ).strip()
            if pr_url:
                log(f"Found existing PR: {pr_url}")
        except Exception:
            pass

        # If no existing PR found, try to create one
        if not pr_url:
            log("No existing PR found, creating final PR...")
            pr_title = f"Fix: {plan['title']}"
            pr_body = f"Automated fix based on plan.\\n\\n{plan['description']}"

            # Write PR body to a temp file to avoid shell escaping issues
            pr_body_file = "/tmp/pr_body.txt"
            with open(pr_body_file, "w") as f:
                f.write(pr_body)

            # Try to create final PR using --body-file (gh pr create outputs URL to stdout)
            try:
                pr_url = run_capture(
                    f"gh pr create --repo {json.dumps(f'{owner}/{repo_name}')} "
                    f"--title {json.dumps(pr_title)} --body-file {pr_body_file} "
                    f"--head {json.dumps(branch_name)}",
                    cwd=cwd,
                ).strip()
            except Exception:
                # Fallback: create PR without --json and scrape URL from output
                proc_result = subprocess.run(
                    f"gh pr create --repo {json.dumps(f'{owner}/{repo_name}')} "
                    f"--title {json.dumps(pr_title)} --body-file {pr_body_file} "
                    f"--head {json.dumps(branch_name)}",
                    shell=True,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                out = (proc_result.stdout or "").strip()
                if out:
                    log(out)
                # Try to find PR URL from output or "already exists" message
                match = re.search(r"https://github\.com/[\w\-_]+/[\w\-_]+/pull/\d+", out)
                if match:
                    pr_url = match.group(0)
                    log(f"PR URL extracted: {pr_url}")

    # 10. If we have a PR URL (from draft or fallback), generate description and mark ready
    if pr_url:
        log(f"__SOULCASTER_PR_URL__={pr_url}")
        log("Generating final PR description with LLM...")

        # Get diff for LLM
        diff_output = run_capture("git diff HEAD~1", cwd=cwd)

        # Generate PR description using Gemini
        gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_api_key:
            try:
                # Install google-genai if not available
                try:
                    from google import genai
                except ImportError:
                    log("Installing google-genai package...")
                    run_command("pip install -q google-genai")
                    from google import genai

                client = genai.Client(api_key=gemini_api_key)

                prompt = (
                    "You are writing a pull request description for a code change.\\n\\n"
                    f"Plan Title: {plan['title']}\\n"
                    f"Plan Description: {plan['description']}\\n\\n"
                    f"Git Diff:\\n{diff_output[:8000]}\\n\\n"
                    "Write a clear and concise PR description with the following sections:\\n"
                    "1. Summary: What problem does this fix and how?\\n"
                    "2. Changes Made: What files/code were modified?\\n"
                    "3. Test Plan: How should this be tested?\\n\\n"
                    "Keep it professional and concise. Use markdown formatting.\\n"
                    "IMPORTANT: Output the markdown directly without wrapping in code blocks. "
                    "Do NOT use ```markdown or ``` wrappers."
                )

                response = client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents=prompt
                )
                generated_description = response.text.strip()

                # Remove markdown code block wrappers if LLM added them
                if generated_description.startswith("```markdown"):
                    generated_description = generated_description[len("```markdown"):].strip()
                if generated_description.startswith("```"):
                    generated_description = generated_description[3:].strip()
                if generated_description.endswith("```"):
                    generated_description = generated_description[:-3].strip()

                final_pr_body = generated_description + "\n\n---\n🤖 Generated with Soulcaster Agent\n"
                log("PR description generated by LLM")
            except Exception as e:
                log(f"Failed to generate PR description with LLM: {e}")
                log("Using fallback template...")
                final_pr_body = (
                    "## Summary\n\n" + plan['description'] +
                    "\n\n## Changes Made\n\n"
                    "Automated fix implemented based on the coding plan.\n\n"
                    "## Test Plan\n\n"
                    "Please review the changes and test manually.\n\n"
                    "---\n🤖 Generated with Soulcaster Agent\n"
                )
        else:
            log("GEMINI_API_KEY not available, using template...")
            final_pr_body = (
                "## Summary\n\n" + plan['description'] +
                "\n\n## Changes Made\n\n"
                "Automated fix implemented based on the coding plan.\n\n"
                "## Test Plan\n\n"
                "Please review the changes and test manually.\n\n"
                "---\n🤖 Generated with Soulcaster Agent\n"
            )

        # Update PR description using REST API (avoids gh CLI scope issues)
        # gh pr edit requires read:org scope due to GraphQL over-fetching
        # See: https://github.com/cli/cli/issues/9166
        log("Updating PR description...")
        try:
            # Parse PR URL: https://github.com/{owner}/{repo}/pull/{pr_number}
            pr_parts = pr_url.rstrip("/").split("/")
            pr_number = pr_parts[-1]
            pr_repo = pr_parts[-3]
            pr_owner = pr_parts[-4]

            # Write final PR body to temp file
            final_pr_body_file = "/tmp/final_pr_body.txt"
            with open(final_pr_body_file, "w") as f:
                f.write(final_pr_body)

            # Use GitHub REST API via curl (only requires repo scope)
            github_token = os.getenv("GITHUB_TOKEN", "")
            api_url = f"https://api.github.com/repos/{pr_owner}/{pr_repo}/pulls/{pr_number}"

            # Build JSON payload with body content
            import json as json_module
            payload = json_module.dumps({"body": final_pr_body})
            payload_file = "/tmp/pr_update_payload.json"
            with open(payload_file, "w") as f:
                f.write(payload)

            run_command(
                f'curl -s -X PATCH {shlex.quote(api_url)} '
                f'-H "Authorization: Bearer $GITHUB_TOKEN" '
                f'-H "Accept: application/vnd.github+json" '
                f'-H "X-GitHub-Api-Version: 2022-11-28" '
                f'-d @{shlex.quote(payload_file)}',
                cwd=cwd
            )
            log("PR description updated!")
        except Exception as e:
            log(f"Could not update PR description: {e}")

        # Mark PR as ready for review
        log("Marking PR as ready for review...")
        try:
            run_command(f"gh pr ready {shlex.quote(pr_url)}", cwd=cwd)
            log("PR marked as ready!")
        except Exception as e:
            log(f"Could not mark PR as ready (may already be ready): {e}")

        log("PR process completed successfully!")
    else:
        log("Could not create or find PR. Check if branch was pushed successfully.")

if __name__ == "__main__":
    main()
"""

class SandboxKilocodeRunner(AgentRunner):
    async def _archive_logs_to_blob(self, job_id: UUID) -> bool:
        """
        Archive in-memory logs for a job to blob storage and attach the resulting blob URL to the job record.
        
        If logs exist for the given job, they are concatenated, uploaded to blob storage, the job is updated with the blob URL, and the in-memory logs are cleared. If no logs are present or an error occurs, no job update is performed.
        
        Returns:
            True if logs were found and successfully uploaded and recorded on the job, False otherwise.
        """
        try:
            logs = job_logs_manager.get_logs(job_id)
            if logs:
                full_logs = "".join(logs)
                blob_url = await asyncio.to_thread(upload_job_logs_to_blob, job_id, full_logs)
                await asyncio.to_thread(update_job, job_id, blob_url=blob_url)
                job_logs_manager.clear_logs(job_id)
                logger.info(f"Job {job_id} logs archived to Blob: {blob_url}")
                return True
            else:
                logger.warning(f"No logs found in memory for job {job_id}")
                return False
        except Exception:
            logger.exception(f"Failed to archive logs for job {job_id}")
            return False

    async def start(
        self,
        job: AgentJob,
        plan: CodingPlan,
        cluster: IssueCluster,
        github_token: Optional[str] = None
    ) -> None:
        """
        Start and run a Kilocode agent inside an external sandbox, stream and persist its logs, and update job and cluster state based on execution results.
        
        Parameters:
            job (AgentJob): The agent job record to update with status, logs, and PR URL.
            plan (CodingPlan): The coding plan to execute inside the sandbox; written to the sandbox workspace.
            cluster (IssueCluster): The issue cluster whose metadata (e.g., repo URL, PR state) may be read and updated.
            github_token (Optional[str]): OAuth token used to authenticate GitHub operations inside the sandbox; required for repository access and PR creation.
        
        Behavior:
            - Creates a temporary sandbox configured from environment variables and the provided plan.
            - Streams stdout/stderr from the agent process into the job's log stream with buffered flushing and optional console mirroring.
            - Detects and persists a PR URL signaled by the agent script; updates the associated cluster status.
            - Marks the job as success on exit code 0 (or failed on non-zero/exception), and attempts to archive logs to blob storage.
            - Ensures sandbox termination unless E2B_KEEP_SANDBOX is enabled.
        
        Exceptions:
            - Does not raise; failures are recorded to the job/cluster state and logged.
        """
        if not AsyncSandbox:
            logger.error("e2b SDK not installed. Cannot run SandboxKilocodeRunner.")
            await self._fail_job(job.id, "e2b SDK missing")
            return

        sandbox = None
        try:
             logger.info(f"Starting sandbox job {job.id} for plan {plan.id}")
             try:
                 await asyncio.to_thread(
                     update_job,
                     job.id,
                     status="running",
                     logs="Initializing sandbox environment...",
                     updated_at=datetime.now(timezone.utc),
                 )
             except Exception as update_err:
                 logger.error(f"Failed to update job status: {update_err}")
                 raise update_err

             # Prepare Environment Variables
             repo_url = (
                 cluster.github_repo_url
                 or os.getenv("DEFAULT_GITHUB_REPO_URL")
                 or "https://github.com/naga-k/bad-ux-mart"
             ).strip()

             # Require github_token from user's OAuth (no fallback to env var)
             if not github_token:
                  await self._fail_job(job.id, "GitHub authentication required. User must be signed in with GitHub OAuth.")
                  return

             env_vars = {
                 "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
                 "KILO_API_MODEL_ID": os.getenv("KILO_API_MODEL_ID", ""),
                 "KILOCODE_PROVIDER": os.getenv("KILOCODE_PROVIDER", ""),
                 "MINIMAX_API_KEY": os.getenv("MINIMAX_API_KEY", os.getenv("MINIMAX_API_TOKEN", "")),
                 "MINIMAX_BASE_URL": os.getenv("MINIMAX_BASE_URL", ""),
                 "KILOCODE_CONFIG_JSON": os.getenv("KILOCODE_CONFIG_JSON", ""),
                 "GITHUB_TOKEN": github_token,
                 "REPO_URL": repo_url,
             }

             if not env_vars["REPO_URL"]:
                  await self._fail_job(job.id, "Missing REPO_URL for sandbox run")
                  return
             
             logger.info(f"Preparing environment for job {job.id}...")
             # Create Sandbox
             # Check for Template Name (alias) first, then ID
             template_req = os.getenv("KILOCODE_TEMPLATE_NAME") or os.getenv("KILOCODE_TEMPLATE_ID", "base")

             if template_req == "base":
                 logger.warning("KILOCODE_TEMPLATE_NAME/ID not set, defaulting to 'base' (this might fail if tools are missing)")

             logger.info(f"Creating sandbox with template: {template_req}")

             # Sandbox TTL (time-to-live) in seconds - how long the sandbox stays alive
             # Default 30 minutes, configurable via E2B_SANDBOX_TTL_SECONDS
             sandbox_ttl_env = (os.getenv("E2B_SANDBOX_TTL_SECONDS") or "").strip()
             try:
                 sandbox_ttl = int(sandbox_ttl_env) if sandbox_ttl_env else 1800  # 30 min default
             except ValueError:
                 sandbox_ttl = 1800

             # Use AsyncSandbox with explicit timeout for sandbox lifetime
             sandbox = await AsyncSandbox.create(
                 template=template_req,
                 envs=env_vars,
                 timeout=sandbox_ttl,
             )
             await self._log(job.id, f"Sandbox created with ID: {sandbox.sandbox_id}")
             logger.info(f"Sandbox created: {sandbox.sandbox_id}")

             # Buffer job log writes so we don't hammer Redis/Upstash on every CLI line.
             flush_interval_s = float(os.getenv("JOB_LOG_FLUSH_INTERVAL_SECONDS", "1.0"))
             max_buffer_chars = int(os.getenv("JOB_LOG_MAX_BUFFER_CHARS", "8000"))
             buffer_lock = asyncio.Lock()
             buffer_lines: list[str] = []
             buffer_chars = 0
             last_flush = time.monotonic()
             mirror = os.getenv("JOB_LOG_MIRROR_TO_CONSOLE", "").lower() in {"1", "true", "yes"}

             async def flush_logs(force: bool = False) -> None:
                 """
                 Flush buffered log lines to the persistent job log storage.
                 
                 When the buffer exceeds configured size or enough time has passed, or when `force` is True, this function writes the accumulated log chunk to job_logs_manager for the current job and resets the in-memory buffer and timers.
                 
                 Parameters:
                 	force (bool): If True, flush immediately regardless of buffer size or elapsed time.
                 """
                 nonlocal buffer_chars, buffer_lines, last_flush
                 now = time.monotonic()
                 if not force and buffer_chars < max_buffer_chars and (now - last_flush) < flush_interval_s:
                     return
                 async with buffer_lock:
                     if not buffer_lines:
                         last_flush = now
                         buffer_chars = 0
                         return
                     chunk = "".join(buffer_lines)
                     buffer_lines = []
                     buffer_chars = 0
                     last_flush = now

                 job_logs_manager.append_log(job.id, chunk)

             async def buffered_log(message: str) -> None:
                 """
                 Append a log line to the job's in-memory buffer and schedule it to be flushed.
                 
                 Parameters:
                     message (str): Log text to append; a newline will be added if one is not present.
                 """
                 nonlocal buffer_chars
                 line = message if message.endswith("\n") else f"{message}\n"
                 async with buffer_lock:
                     buffer_lines.append(line)
                     buffer_chars += len(line)
                 if mirror:
                     logger.info("[sandbox_kilo][job=%s] %s", job.id, message.rstrip())
                 await flush_logs(force=False)

             # Upload Agent Script and Plan
             await buffered_log("Uploading context...")
             logger.info("Uploading agent script and plan...")
             await sandbox.files.write("/tmp/agent_script.py", AGENT_SCRIPT)
             await sandbox.files.write("/tmp/plan.json", plan.model_dump_json())
             logger.info("Context uploaded.")

             # Execute Script
             await buffered_log("Executing agent script...")
             logger.info("Starting execution of agent script...")
             
             async def handle_stdout(output):
                 text = str(output)
                 # Capture PR URL signal emitted by the agent script so we can persist it.
                 if "__SOULCASTER_PR_URL__=" in text:
                     try:
                         # Extract only the URL on the same line, ignore subsequent log messages
                         pr_url = text.split("__SOULCASTER_PR_URL__=", 1)[1].split('\n')[0].strip()
                         if pr_url:
                             await asyncio.to_thread(update_job, job.id, pr_url=pr_url, updated_at=datetime.now(timezone.utc))
                             await asyncio.to_thread(
                                 update_cluster,
                                 str(job.project_id),
                                 job.cluster_id,
                                 github_pr_url=pr_url,
                                 updated_at=datetime.now(timezone.utc),
                             )
                     except Exception:
                         pass
                 await buffered_log(text)

             async def handle_stderr(output):
                 await buffered_log(f"[ERR] {str(output)}")

             timeout_env = (os.getenv("SANDBOX_AGENT_TIMEOUT_SECONDS") or "").strip()
             timeout_seconds: int | None
             try:
                 timeout_seconds = int(timeout_env) if timeout_env else 3600
             except ValueError:
                 timeout_seconds = 3600
             if timeout_seconds <= 0:
                 timeout_seconds = None

             try:
                 proc = await sandbox.commands.run(
                     "python3 /tmp/agent_script.py",
                     on_stdout=handle_stdout,
                     on_stderr=handle_stderr,
                     timeout=timeout_seconds,
                 )
             finally:
                 await flush_logs(force=True)

             if proc.exit_code == 0:
                  latest_job = await asyncio.to_thread(get_job, job.id)
                  existing_logs = (latest_job.logs or "") if latest_job else ""
                  success_logs = (existing_logs + "\n" if existing_logs else "") + "Success."
                  await asyncio.to_thread(
                      update_job,
                      job.id,
                      status="success",
                      logs=success_logs,
                      updated_at=datetime.now(timezone.utc),
                  )
                  # Mark cluster as completed and clear any previous error.
                  try:
                      refreshed = await asyncio.to_thread(get_job, job.id)
                      cluster_updates = {
                          "status": "pr_opened" if (refreshed and refreshed.pr_url) else "new",
                          "error_message": None,
                          "updated_at": datetime.now(timezone.utc),
                      }
                      await asyncio.to_thread(
                          update_cluster,
                          str(job.project_id),
                          job.cluster_id,
                          **cluster_updates,
                      )
                  except Exception as e:
                      logger.warning("Failed to update cluster %s on success: %s", job.cluster_id, e)

                  # Archive logs to Blob
                  if not await self._archive_logs_to_blob(job.id):
                      logger.warning(f"Job {job.id} completed but log archival failed")
             else:
                  await self._fail_job(job.id, f"Agent script exited with code {proc.exit_code}")

        except Exception as e:
            # Some transports (notably long-running streaming callbacks) can error with
            # "peer closed connection without sending complete message body (incomplete chunked read)".
            # This is often a timeout/stream reset rather than a true agent failure.
            msg = str(e)
            if "incomplete chunked read" in msg.lower() or "peer closed connection" in msg.lower():
                try:
                    await self._log(
                        job.id,
                        "Stream disconnected while running the sandbox command. "
                        "If the job is legitimately long-running, increase `SANDBOX_AGENT_TIMEOUT_SECONDS` "
                        "(or set it to 0 to disable the timeout).",
                    )
                except Exception:
                    pass
            logger.exception(f"Job {job.id} failed in sandbox")
            await self._fail_job(job.id, str(e))
        finally:
            if sandbox is not None:
                should_keep = os.getenv("E2B_KEEP_SANDBOX", "").lower() in {"1", "true", "yes"}
                if should_keep:
                    logger.info("E2B_KEEP_SANDBOX enabled; leaving sandbox %s running", sandbox.sandbox_id)
                else:
                    try:
                        killed = sandbox.kill()
                        if asyncio.iscoroutine(killed):
                            killed = await killed
                        logger.info("Sandbox %s killed=%s", sandbox.sandbox_id, killed)
                    except Exception as kill_err:
                        # E2B may already have terminated the sandbox (e.g. TTL or upstream cleanup),
                        # which can surface as a 404 on delete. Treat that as non-fatal cleanup.
                        msg = str(kill_err)
                        if "404" in msg and "Not Found" in msg:
                            logger.info("Sandbox %s already gone (404 on kill)", getattr(sandbox, "sandbox_id", "?"))
                        else:
                            logger.warning("Failed to kill sandbox %s: %s", getattr(sandbox, "sandbox_id", "?"), kill_err)

    async def _log(self, job_id: UUID, message: str):
        # Persist to job log stream/list and optionally mirror to console.
        """
        Persist a single log line to the job's centralized log stream and optionally mirror it to the console.
        
        Appends the provided message (ensuring it ends with a newline) to the job's log storage and, when console mirroring is enabled via the JOB_LOG_MIRROR_TO_CONSOLE environment variable, writes the log to the application logger.
        
        Parameters:
        	job_id (UUID): Identifier of the job whose log stream will receive the message.
        	message (str): The log message to append; a trailing newline will be added if not present.
        """
        mirror = os.getenv("JOB_LOG_MIRROR_TO_CONSOLE", "").lower() in {"1", "true", "yes"}
        if mirror:
            logger.info("[sandbox_kilo][job=%s] %s", job_id, message.rstrip())
        line = message if message.endswith("\n") else f"{message}\n"
        job_logs_manager.append_log(job_id, line)

    async def _fail_job(self, job_id: UUID, error: str):
        """
        Mark a job as failed, append the error message to its logs, update the associated cluster status, and attempt to archive the job logs to blob storage.
        
        Parameters:
            job_id (UUID): Identifier of the job to mark as failed.
            error (str): Error message to append to the job logs and record as the cluster failure reason.
        """
        job = await asyncio.to_thread(get_job, job_id)
        current_logs = (job.logs or "") if job is not None else ""
        await asyncio.to_thread(
            update_job,
            job_id,
            status="failed",
            logs=f"{current_logs}\nError: {error}",
            updated_at=datetime.now(timezone.utc),
        )
        
        # Update cluster status so UI can show the button again
        if job and job.cluster_id:
            try:
                # update_cluster needs project_id first
                await asyncio.to_thread(
                    update_cluster,
                    str(job.project_id),
                    job.cluster_id,
                    status="failed",
                    error_message=error,
                    updated_at=datetime.now(timezone.utc),
                )
            except Exception as e:
                logger.error(f"Failed to update cluster status: {e}")

        # Archive logs to Blob
        if not await self._archive_logs_to_blob(job_id):
            logger.warning(f"Job {job_id} failed but log archival also failed")

register_runner("sandbox_kilo", SandboxKilocodeRunner)