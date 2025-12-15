import asyncio
import logging
import os
import json
from uuid import UUID
from datetime import datetime, timezone

try:
    from e2b_code_interpreter import Sandbox
except ImportError:
    Sandbox = None

from models import AgentJob, CodingPlan, IssueCluster
from store import update_job
from agent_runner import AgentRunner, register_runner

logger = logging.getLogger(__name__)

# Template ID for the Kilocode sandbox.
KILOCODE_TEMPLATE_ID = os.getenv("KILOCODE_TEMPLATE_ID", "base") 

AGENT_SCRIPT = r"""
import os
import sys
import json
import subprocess
import time
from pathlib import Path

def log(msg):
    print(msg)
    sys.stdout.flush()

def run_command(cmd, cwd=None, env=None):
    log(f"Running: {cmd}")
    try:
        subprocess.check_call(cmd, shell=True, cwd=cwd, env=env)
    except subprocess.CalledProcessError as e:
        log(f"Command failed: {e}")
        raise

def setup_kilo_config():
    # Configure Kilo CLI
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        log("WARN: No GEMINI_API_KEY found")
        return

    config_dir = Path.home() / ".kilocode" / "cli"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    
    config_data = {
        "version": "1.0.0",
        "mode": "code",
        "provider": "default",
        "providers": [{
            "id": "default",
            "provider": "gemini",
            "geminiApiKey": gemini_key,
            "apiModelId": os.getenv("KILO_API_MODEL_ID", "gemini-2.5-flash-preview-04-17"),
            "enableUrlContext": True
        }],
        "autoApproval": {
            "enabled": True,
            "execute": {"enabled": True},
            "read": {"enabled": True},
            "write": {"enabled": True}
        }
    }
    with open(config_path, "w") as f:
        json.dump(config_data, f, indent=2)
    log("Kilo config written.")

def main():
    # 1. Read Plan
    with open("/tmp/plan.json", "r") as f:
        plan = json.load(f)
    
    repo_url = os.getenv("REPO_URL")
    if not repo_url:
        raise Exception("REPO_URL env var missing")

    # 2. Extract owner/repo
    # https://github.com/owner/repo.git or https://github.com/owner/repo
    parts = repo_url.strip("/").replace(".git", "").split("/")
    repo_name = parts[-1]
    owner = parts[-2]
    
    # 3. Clone
    # We use GH_TOKEN from env implicitly with gh cli or git
    # But for simplicity, let's use git with token if needed, or assume ssh/https helper is set up
    # The sandbox usually has gh installed.
    # Let's try gh repo clone
    log(f"Cloning {owner}/{repo_name}...")
    run_command(f"gh repo clone {owner}/{repo_name} repo")
    cwd = os.path.abspath("repo")

    # 4. Git Config
    run_command('git config user.email "agent@soulcaster.dev"', cwd=cwd)
    run_command('git config user.name "Soulcaster Agent"', cwd=cwd)

    # 5. Branch
    branch_name = f"fix/soulcaster-{int(time.time())}"
    run_command(f"git checkout -b {branch_name}", cwd=cwd)

    # 6. Run Kilocode
    setup_kilo_config()
    
    prompt = f"Executing Coding Plan: {plan['title']}\n\n"
    prompt += f"Description: {plan['description']}\n\n"
    prompt += f"Tasks:\n"
    for task in plan.get('tasks', []):
        prompt += f"- {task}\n"
    
    log("Starting Kilocode...")
    # Escape quotes for shell safety - simple version
    safe_prompt = prompt.replace('"', '\\"')
    run_command(f'kilocode --auto "{safe_prompt}"', cwd=cwd)

    # 7. Push and PR
    run_command(f"git add .", cwd=cwd)
    # Check if anything to commit
    try:
        run_command(f"git commit -m 'Fix: {plan['title']}'", cwd=cwd)
        run_command(f"git push -u origin {branch_name}", cwd=cwd)
        
        pr_title = f"Fix: {plan['title']}"
        pr_body = f"Automated fix based on plan.\n\n{plan['description']}"
        
        # gh pr create
        # Ensure GH_TOKEN is available to gh cli
        run_command(f"gh pr create --title \"{pr_title}\" --body \"{pr_body}\" --head {branch_name}", cwd=cwd)
        log("PR Created Successfully.")
    except Exception as e:
        log(f"Git/PR step failed (maybe no changes?): {e}")

if __name__ == "__main__":
    main()
"""

class SandboxKilocodeRunner(AgentRunner):
    async def start(self, job: AgentJob, plan: CodingPlan, cluster: IssueCluster) -> None:
        if not Sandbox:
            logger.error("e2b SDK not installed. Cannot run SandboxKilocodeRunner.")
            await self._fail_job(job.id, "e2b SDK missing")
            return

        logger.info(f"Starting sandbox job {job.id} for plan {plan.id}")
        update_job(job.id, status="running", logs="Initializing sandbox environment...")

        # Prepare Environment Variables
        env_vars = {
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
            "GH_TOKEN": os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN", "")),
            "REPO_URL": cluster.github_repo_url or "",
            "KILO_API_MODEL_ID": os.getenv("KILO_API_MODEL_ID", "gemini-2.5-flash-preview-04-17"),
        }
        
        if not env_vars["REPO_URL"]:
             # Fallback if repo url not on cluster, try to construct? or fail
             await self._fail_job(job.id, "Cluster missing github_repo_url")
             return

        try:
            # Create Sandbox
            # We assume 'base' template or similar has: python3, git, gh, kilocode (via pip install?)
            # If kilocode not in template, we must install it.
            async with Sandbox.create(template=KILOCODE_TEMPLATE_ID, envs=env_vars) as sandbox:
                await self._log(job.id, "Sandbox created.")

                # Install dependencies if needed
                # Ideally the template has them. If not, this adds overhead.
                # await sandbox.commands.run("pip install kilocode")
                
                # Upload Agent Script and Plan
                await self._log(job.id, "Uploading context...")
                await sandbox.files.write("/tmp/agent_script.py", AGENT_SCRIPT)
                await sandbox.files.write("/tmp/plan.json", plan.model_dump_json())

                # Execute Script
                await self._log(job.id, "Executing agent script...")
                
                # Run and stream logs
                # e2b SDK: sandbox.commands.run returns a result, logs can be streamed via callbacks
                # Note: API might have changed slightly in recent e2b versions (e.g. sandbox.process.start)
                # But sandbox.commands.run is standard for sync-like waiting with output.
                # To stream, use on_stdout/on_stderr
                
                async def handle_stdout(output):
                    await self._log(job.id, output.line)

                async def handle_stderr(output):
                    await self._log(job.id, f"[ERR] {output.line}")

                proc = await sandbox.commands.run(
                    "python3 /tmp/agent_script.py",
                    on_stdout=handle_stdout,
                    on_stderr=handle_stderr,
                    timeout=600 # 10 mins timeout
                )

                if proc.exit_code == 0:
                    # Success
                     # We might want to parse the PR URL from logs if not explicitly returned?
                     # The script logs "PR Created Successfully."
                     # For now, mark success.
                     update_job(job.id, status="success", logs=f"{job.logs}\nSuccess.")
                else:
                     await self._fail_job(job.id, f"Agent script exited with code {proc.exit_code}")

        except Exception as e:
            logger.exception(f"Job {job.id} failed in sandbox")
            await self._fail_job(job.id, str(e))

    async def _log(self, job_id: UUID, message: str):
        from store import get_job, update_job
        job = get_job(job_id)
        if job:
            # Append log line
            # In high freq, this is bad, but acceptable for prototype
            current_logs = job.logs or ""
            new_log = f"{message}\n"
            update_job(job_id, logs=current_logs + new_log)

    async def _fail_job(self, job_id: UUID, error: str):
        update_job(job_id, status="failed", logs=f"Error: {error}")

