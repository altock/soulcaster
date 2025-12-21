"""Module for generating coding plans using Gemini."""
import logging
import os
from datetime import datetime, timezone
from uuid import uuid4

from google import genai
from google.genai import types
from pydantic import BaseModel

from models import IssueCluster, CodingPlan, FeedbackItem

logger = logging.getLogger(__name__)

# Use a schema for structured generation
class PlanSchema(BaseModel):
    title: str
    description: str


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set. Plan generation will fail.")
        return None
    return genai.Client(api_key=api_key)


def generate_plan(cluster: IssueCluster, feedback_items: list[FeedbackItem]) -> CodingPlan:
    """
    Generate a high-level coding plan for an issue cluster from user feedback using Gemini.
    
    Parameters:
        cluster (IssueCluster): The issue cluster to generate a plan for.
        feedback_items (list[FeedbackItem]): Ordered user feedback entries relevant to the cluster.
    
    Returns:
        CodingPlan: A plan containing a new UUID, the cluster ID, a short product-facing title,
        a single-block description describing problem, expected behavior, and (optionally)
        acceptance criteria, and created/updated UTC timestamps.
    
    Behavior:
        - If the Gemini API key is missing, returns a placeholder plan indicating automatic
          plan generation failed (title prefixed with "Fix:" and a description noting the failure).
        - If generation succeeds, returns a CodingPlan populated from the model's parsed
          title and description.
        - If generation raises an exception, logs the error and returns a fallback plan whose
          title indicates the error and whose description contains the exception message.
    """
    client = _get_client()
    if not client:
        # Fallback for when no API key is present (e.g. tests)
        return CodingPlan(
            id=str(uuid4()),
            cluster_id=cluster.id,
            title=f"Fix: {cluster.title}",
            description=(
                "Automatic plan generation failed (no API key). "
                "This is a placeholder plan with high-level requirements only."
            ),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    # Construct the prompt context
    feedback_text = "\n\n".join(
        [
            f"--- Feedback {i+1} ---\nTitle: {item.title}\nBody: {item.body}"
            for i, item in enumerate(feedback_items)
        ]
    )

    prompt = f"""
You are a senior product manager writing instructions for a developer.

Cluster Title: {cluster.title}
Cluster Summary: {cluster.summary}

User Feedback Reports:
{feedback_text}

Write a HIGH-LEVEL plan only.

Hard rules:
- Do NOT invent file paths, code symbols, APIs, libraries, or specific implementation steps.
- Do NOT include sections like "Files to edit" or "Tasks".
- Only use information present in the cluster title/summary and the feedback reports.

Output requirements:
- title: a short product-facing title.
- description: a single plain-text block that combines:
    - problem statement and user impact
    - explicit requirements / expected behavior
    - (optional) acceptance criteria phrased as observable outcomes
"""

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PlanSchema,
                temperature=0.2,
            ),
        )

        parsed_plan = response.parsed

        return CodingPlan(
            id=str(uuid4()),
            cluster_id=cluster.id,
            title=parsed_plan.title,
            description=parsed_plan.description,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.exception(f"Failed to generate plan for cluster {cluster.id}")
        # Return a fallback plan indicating failure
        return CodingPlan(
            id=str(uuid4()),
            cluster_id=cluster.id,
            title=f"Error planning fix for: {cluster.title}",
            description=f"Plan generation failed: {str(e)}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )