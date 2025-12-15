"""
Module for generating coding plans using Gemini.
"""

import json
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
    files_to_edit: list[str]
    tasks: list[str]


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set. Plan generation will fail.")
        return None
    return genai.Client(api_key=api_key)


def generate_plan(cluster: IssueCluster, feedback_items: list[FeedbackItem]) -> CodingPlan:
    """
    Generate a CodingPlan for the given cluster and feedback items using Gemini.
    """
    client = _get_client()
    if not client:
        # Fallback for when no API key is present (e.g. tests)
        return CodingPlan(
            id=str(uuid4()),
            cluster_id=cluster.id,
            title=f"Fix: {cluster.title}",
            description="Automatic plan generation failed (no API key). This is a placeholder.",
            files_to_edit=[],
            tasks=["Check API key configuration"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    # Construct the prompt context
    feedback_text = "\n\n".join(
        [f"--- Feedback {i+1} ---\nTitle: {item.title}\nBody: {item.body}" 
         for i, item in enumerate(feedback_items)]
    )

    prompt = f"""
You are a senior software engineer. Create a detailed implementation plan to fix the following issue cluster.

Cluster Title: {cluster.title}
Cluster Summary: {cluster.summary}

User Feedback Reports:
{feedback_text}

Your plan should include:
1. A clear, technical title for the fix.
2. A detailed description of the approach.
3. A list of files that likely need to be created or modified.
4. A step-by-step list of tasks to implement the fix.
"""

    try:
        response = client.models.generate_content(
            model="gemini-1.5-pro-002",
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
            files_to_edit=parsed_plan.files_to_edit,
            tasks=parsed_plan.tasks,
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
            files_to_edit=[],
            tasks=["Investigate plan generation error"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
