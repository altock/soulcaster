from unittest.mock import MagicMock, patch
from uuid import UUID
from datetime import datetime, timezone
from models import IssueCluster, FeedbackItem
from planner import generate_plan

def test_generate_plan_success():
    # Setup mock data context
    cluster = IssueCluster(
        id="c1", project_id="p1", title="Fix Bug", summary="Bad bug",
        feedback_ids=["f1"], status="new", created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    feedback = FeedbackItem(
        id=UUID("00000000-0000-0000-0000-000000000001"), project_id="p1", 
        source="manual", title="Report", body="It crashes", 
        created_at=datetime.now(timezone.utc)
    )
    
    # Mock the google.genai.Client
    with patch("planner._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.parsed.title = "Technical Fix Plan"
        mock_response.parsed.description = "Fix steps"
        
        mock_client.models.generate_content.return_value = mock_response
        
        # Execute
        plan = generate_plan(cluster, [feedback])
        
        # Verify
        assert plan is not None
        assert plan.title == "Technical Fix Plan"
        assert plan.description == "Fix steps"
        assert plan.cluster_id == "c1"

def test_generate_plan_no_api_key():
    cluster = IssueCluster(
        id="c1", project_id="p1", title="Fix Bug", summary="Bad bug",
        feedback_ids=[], status="new", created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    with patch("planner._get_client", return_value=None):
        plan = generate_plan(cluster, [])
        assert "no API key" in plan.description 
        assert plan.cluster_id == "c1"

def test_generate_plan_exception_handling():
    cluster = IssueCluster(
        id="c1", project_id="p1", title="Bug", summary="Bug summary",
        feedback_ids=[], status="new", created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    with patch("planner._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        # API raises error
        mock_client.models.generate_content.side_effect = Exception("API Broken")
        
        plan = generate_plan(cluster, [])
        assert plan.title.startswith("Error planning fix")
        assert "API Broken" in plan.description
