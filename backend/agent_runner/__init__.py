from abc import ABC, abstractmethod
from typing import Dict, Optional, Type
from uuid import UUID

from models import AgentJob, CodingPlan, IssueCluster


class AgentRunner(ABC):
    """
    Protocol for a coding agent runner.
    """

    @abstractmethod
    async def start(
        self,
        job: AgentJob,
        plan: CodingPlan,
        cluster: IssueCluster,
        github_token: Optional[str] = None
    ) -> None:
        """
        Start the agent execution for the given job.
        Should handle setup, execution, logging, and completion.

        Args:
            job: The agent job to execute
            plan: The coding plan to implement
            cluster: The issue cluster being fixed
            github_token: Optional per-user GitHub token. Falls back to GITHUB_TOKEN env var if not provided.
        """
        pass


_registry: Dict[str, Type[AgentRunner]] = {}


def register_runner(name: str, runner_cls: Type[AgentRunner]):
    _registry[name] = runner_cls


def get_runner(name: str) -> AgentRunner:
    runner_cls = _registry.get(name)
    if not runner_cls:
        raise ValueError(f"Runner '{name}' not found in registry")
    return runner_cls()
