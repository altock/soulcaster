
import asyncio
import os
import uuid
import logging
from datetime import datetime
from agent_runner.sandbox import SandboxKilocodeRunner
from models import AgentJob, CodingPlan, IssueCluster

# Configure logging to stdout
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    print("--- STARTING TEST ---")
    
    # Mock Objects
    job_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    
    job = AgentJob(
        id=job_id,
        project_id="cmiy0tdxz00022mo0aa3ywqsx", # use a valid-looking project id string
        cluster_id="test_cluster",
        plan_id=str(plan_id),
        status="pending",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    plan = CodingPlan(
        id=str(plan_id),
        cluster_id="test_cluster",
        title="Test Plan",
        description="This is a test plan",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    cluster = IssueCluster(
        id="test_cluster",
        project_id="test_project",
        title="Test Cluster",
        summary="Test Summary",
        feedback_ids=[],
        status="new",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        github_repo_url="https://github.com/naga-karumuri/soulcaster-test-repo" # NEED A REAL REPO OR MOCK? using fake for now, but runner checks validity.
        # Ideally user has a repo in env? 
    )
    
    cluster.github_repo_url = "https://github.com/octocat/Hello-World"

    # Add job to store first so update_job doesn't fail on "not found"
    from store import add_job
    add_job(job)

    runner = SandboxKilocodeRunner()
    
    print("Invoking runner.start()...")
    try:
        await runner.start(job, plan, cluster)
        print("Runner finished successfully (check status in logs)")
    except Exception as e:
        print(f"Runner crashed with: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Ensure env vars are set
    # We rely on .env being loaded, but lets force load it
    from dotenv import load_dotenv
    load_dotenv()
    
    asyncio.run(run_test())
