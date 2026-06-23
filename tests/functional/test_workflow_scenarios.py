import pytest
import httpx
from unittest.mock import patch
from src.state import repository
from src.agents import team
from src.state.db import SessionLocal

def is_lm_studio_online() -> bool:
    """Helper to detect if the local LM Studio server is active."""
    for host in ["localhost", "host.docker.internal"]:
        try:
            response = httpx.get(f"http://{host}:1234/v1/models", timeout=1.5)
            if response.status_code == 200:
                return True
        except Exception:
            continue
    return False

@pytest.mark.asyncio
async def test_live_qwen_bug_scenario(db_session):
    """Live integration scenario testing the BUG workflow using Qwen 3.5 in LM Studio (skipped if offline)."""
    if not is_lm_studio_online():
        pytest.skip("LM Studio local server is offline. Skipping live Qwen integration scenario.")

    with patch("src.agents.team.SessionLocal", return_value=db_session):
        # 1. Classification
        raw_input = "We have a bug where the login endpoint returns 500 when the password has special characters like % or &."
        class_res = await team.classify_input(raw_input)
        assert class_res["type"] == "BUG"
        
        # Create session and add steps
        session = repository.create_session(db_session, raw_input=raw_input, session_type="BUG")
        from src.workflows.bug import bug_workflow
        repository.add_steps(db_session, session_id=session.id, step_names=bug_workflow.get_step_names())
        
        # 2. Capture & Clarify step debate
        user_input = "Operating System: macOS, Python: 3.11, occurs because URL unescaping fails on raw % without escaping."
        debate_res = await team.execute_step_debate(session.id, user_input)
        
        assert debate_res["session_id"] == session.id
        assert debate_res["current_step"] == "Capture & Clarify"
        # Since input is detailed, the model should either COMPLETED or ask for more details PENDING
        assert debate_res["status"] in ["COMPLETED", "PENDING"]

@pytest.mark.asyncio
async def test_live_qwen_feature_scenario(db_session):
    """Live integration scenario testing the FEATURE workflow using Qwen 3.5 in LM Studio (skipped if offline)."""
    if not is_lm_studio_online():
        pytest.skip("LM Studio local server is offline. Skipping live Qwen integration scenario.")

    with patch("src.agents.team.SessionLocal", return_value=db_session):
        # 1. Classification
        raw_input = "We need to build a new feature: file upload endpoint for user avatars. It should store files in AWS S3 and validate image size (< 2MB)."
        class_res = await team.classify_input(raw_input)
        assert class_res["type"] == "FEATURE"
        
        # Create session and add steps
        session = repository.create_session(db_session, raw_input=raw_input, session_type="FEATURE")
        from src.workflows.feature import feature_workflow
        repository.add_steps(db_session, session_id=session.id, step_names=feature_workflow.get_step_names())
        
        # 2. Understand Problem & Goals step debate
        user_input = "Target audience is mobile and web app users. Success metrics are upload latency < 200ms and failure rate < 0.1%."
        debate_res = await team.execute_step_debate(session.id, user_input)
        
        assert debate_res["session_id"] == session.id
        assert debate_res["current_step"] == "Understand Problem & Goals"
        assert debate_res["status"] in ["COMPLETED", "PENDING"]

@pytest.mark.asyncio
async def test_live_qwen_meeting_scenario(db_session):
    """Live integration scenario testing the MEETING/PLANNING workflow using Qwen 3.5 in LM Studio (skipped if offline)."""
    if not is_lm_studio_online():
        pytest.skip("LM Studio local server is offline. Skipping live Qwen integration scenario.")

    with patch("src.agents.team.SessionLocal", return_value=db_session):
        # 1. Classification
        raw_input = "Meeting with PM to discuss Q3 roadmap planning and backend performance tuning next week."
        class_res = await team.classify_input(raw_input)
        assert class_res["type"] == "MEETING/PLANNING"
        
        # Create session and add steps
        session = repository.create_session(db_session, raw_input=raw_input, session_type="MEETING/PLANNING")
        from src.workflows.meeting import meeting_workflow
        repository.add_steps(db_session, session_id=session.id, step_names=meeting_workflow.get_step_names())
        
        # 2. Review Agenda & Prepare step debate
        user_input = "Goal is to align on Q3 goals, discuss load testing results showing 500ms API latency, and assign owners."
        debate_res = await team.execute_step_debate(session.id, user_input)
        
        assert debate_res["session_id"] == session.id
        assert debate_res["current_step"] == "Review Agenda & Prepare"
        assert debate_res["status"] in ["COMPLETED", "PENDING"]
