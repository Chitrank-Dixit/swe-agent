import pytest
import asyncio
from unittest.mock import patch, MagicMock
from src.agents.structures import (
    CoachOutput,
    CoordinatorOutput,
    TestStrategyOutput,
    SkepticOutput
)
from src.agents.team import should_invoke_skeptic, run_agent_stream_buffered

class MockSession:
    def __init__(self, type_name, raw_input):
        self.type = type_name
        self.raw_input = raw_input

def test_should_invoke_skeptic_wrong_workflow():
    session = MockSession("MEETING", "Discuss sprint goals")
    coach_out = CoachOutput(
        step_name="Review",
        recommendations="Let's do this",
        actions=["Review README.md"],
        checks=[]
    )
    assert not should_invoke_skeptic(session, coach_out)

def test_should_invoke_skeptic_trivial_keyword():
    session = MockSession("FEATURE", "Fix typo in docstring")
    coach_out = CoachOutput(
        step_name="Verify",
        recommendations="```python\n# Docstring typo fix\n```",
        actions=["Edit src/cli.py"],
        checks=[]
    )
    # Trivial keywords matched
    assert not should_invoke_skeptic(session, coach_out)

def test_should_invoke_skeptic_below_threshold():
    session = MockSession("FEATURE", "Add small print statement")
    coach_out = CoachOutput(
        step_name="Verify",
        recommendations="```python\nprint('hello')\n```",
        actions=["Edit src/cli.py"],
        checks=[]
    )
    # 1 file (src/cli.py) * 10 + 2 lines = 12. (SUBSTANTIAL_THRESHOLD is 20)
    assert not should_invoke_skeptic(session, coach_out)

def test_should_invoke_skeptic_above_threshold():
    session = MockSession("FEATURE", "Add database user model and migrations")
    coach_out = CoachOutput(
        step_name="Implement Model",
        recommendations=(
            "```python\n"
            "class User(BaseModel):\n"
            "    id: int\n"
            "    name: str\n"
            "    email: str\n"
            "```"
        ),
        actions=["Edit src/models.py", "Edit src/migrations/env.py", "Edit tests/test_models.py"],
        checks=["Verify DB migration is created"]
    )
    # 3 files * 10 + 6 lines = 36. (SUBSTANTIAL_THRESHOLD is 20)
    assert should_invoke_skeptic(session, coach_out)

@pytest.mark.asyncio
async def test_run_agent_stream_buffered():
    agent = MagicMock()
    
    from autogen_agentchat.messages import TextMessage

    # Create async generator mock for run_stream
    async def mock_run_stream(task):
        yield TextMessage(source="TestAgent", content="Buffered text output")

    agent.run_stream = mock_run_stream
    
    res_text, tokens = await run_agent_stream_buffered(agent, "Hello", "TestAgent")
    assert res_text == "Buffered text output"
    assert tokens == ["[THINKING]"]

@pytest.mark.asyncio
async def test_execute_step_debate_parallel_execution(db_session):
    from src.state import repository
    from src.workflows.feature import feature_workflow
    
    session = repository.create_session(
        db_session,
        raw_input="Add database model",
        session_type="FEATURE"
    )
    session_id = session.id
    steps = repository.add_steps(db_session, session_id, feature_workflow.get_step_names())
    pending_step = steps[0]
    
    # Coordinator outputs Feature
    mock_coord_json = '{"workflow_type": "FEATURE", "goal": "Add database model", "relevant_files": [], "constraints": [], "context_summary": "Feature input"}'
    
    # Substantial coach proposals to trigger skeptic (touches multiple files, line changes)
    mock_coach_json = (
        '{"step_name": "Capture & Clarify", '
        '"recommendations": "Add class User model. \\n```python\\nclass User(BaseModel):\\n    id: int\\n```", '
        '"actions": ["Edit src/models.py", "Edit src/db.py", "Edit tests/test_models.py"], '
        '"checks": []}'
    )
    
    mock_test_json = '{"bdd_scenarios": ["Scenario: Create user"], "pytest_skeletons": ["def test_user(): pass"]}'
    mock_skeptic_json = '{"critique": "Critique notes", "gaps": [], "challenges": []}'
    
    stream_idx = 0
    mock_responses = [mock_coord_json, mock_coach_json, mock_test_json, mock_skeptic_json]
    
    async def mock_run_agent_stream(agent, prompt, agent_name, callback):
        nonlocal stream_idx
        res = mock_responses[stream_idx]
        stream_idx += 1
        return res

    with patch("src.agents.team.SessionLocal", return_value=db_session), \
         patch("src.agents.team.run_agent_stream", side_effect=mock_run_agent_stream), \
         patch("src.agents.team.check_regret_guard", return_value=[]):
         
        from src.agents import team
        res = await team.execute_step_debate(session_id, "Propose details")
        
        assert res["status"] == "COMPLETED"
        # Test Strategy and Skeptic Critique should both be present because the skeptic gating returned True
        assert "Coach's Proposals" in res["feedback"]
        assert "Test Strategy" in res["feedback"]
        assert "Skeptic's Critique" in res["feedback"]
