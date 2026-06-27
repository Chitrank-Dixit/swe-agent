import pytest
import json
from unittest.mock import MagicMock, patch
from src.agents.structures import (
    CoordinatorOutput,
    CoachOutput,
    TestStrategyInput,
    TestStrategyOutput,
    SkepticInput,
    SkepticOutput
)
from src.agents.team import parse_json_from_response

def test_pydantic_structures_serialization():
    # Test CoordinatorOutput
    coord = CoordinatorOutput(
        workflow_type="BUG",
        goal="Fix NameError",
        relevant_files=["src/cli.py"],
        constraints=["No extra libraries"],
        context_summary="NameError in cli.py"
    )
    assert coord.workflow_type == "BUG"
    assert coord.relevant_files == ["src/cli.py"]
    
    # Test CoachOutput
    coach = CoachOutput(
        step_name="Verify",
        recommendations="Add import",
        actions=["Edit file"],
        checks=["Run tests"]
    )
    assert coach.actions == ["Edit file"]
    
    # Test TestStrategyInput
    ts_in = TestStrategyInput(
        workflow_type="FEATURE",
        goal="Add login",
        code_snippets=["def test_login(): pass"],
        constraints=["Use pytest"]
    )
    assert ts_in.goal == "Add login"
    
    # Test TestStrategyOutput
    ts_out = TestStrategyOutput(
        bdd_scenarios=["Scenario: User logs in successfully"],
        pytest_skeletons=["def test_login_flow():\n    pass"]
    )
    assert len(ts_out.bdd_scenarios) == 1
    assert "Scenario" in ts_out.bdd_scenarios[0]

def test_parse_json_from_response_standard():
    raw = '{"workflow_type": "BUG", "goal": "Fix NameError", "relevant_files": [], "constraints": [], "context_summary": "Summary"}'
    parsed = parse_json_from_response(raw)
    assert parsed["workflow_type"] == "BUG"
    assert parsed["goal"] == "Fix NameError"

def test_parse_json_from_response_markdown_fenced():
    raw = '```json\n{"workflow_type": "BUG", "goal": "Fix NameError", "relevant_files": [], "constraints": [], "context_summary": "Summary"}\n```'
    parsed = parse_json_from_response(raw)
    assert parsed["workflow_type"] == "BUG"

def test_parse_json_from_response_text_with_json():
    raw = 'Here is the result:\n{\n  "workflow_type": "BUG",\n  "goal": "Fix NameError",\n  "relevant_files": [],\n  "constraints": [],\n  "context_summary": "Summary"\n}\nHope this helps!'
    parsed = parse_json_from_response(raw)
    assert parsed["workflow_type"] == "BUG"

def test_parse_json_from_response_invalid():
    raw = "This is not JSON at all."
    with pytest.raises(ValueError, match="Failed to parse JSON"):
        parse_json_from_response(raw)

@pytest.mark.asyncio
async def test_execute_step_debate_sequential_structured_flow(db_session):
    # Setup mock session and step
    from src.state import repository
    from src.workflows.bug import bug_workflow
    
    session = repository.create_session(
        db_session,
        raw_input="Fix NameError in cli.py",
        session_type="BUG"
    )
    session_id = session.id
    steps = repository.add_steps(db_session, session_id, bug_workflow.get_step_names())
    pending_step = steps[0]
    
    # Mocking run_agent_stream responses for Coordinator, BugWorkflowCoach, TestStrategy, and Skeptic
    mock_coord_json = json.dumps({
        "workflow_type": "BUG",
        "goal": "Fix NameError in cli.py",
        "relevant_files": ["src/cli.py"],
        "constraints": [],
        "context_summary": "NameError in cli.py"
    })
    
    mock_coach_json = json.dumps({
        "step_name": pending_step.name,
        "recommendations": "Proposing to add the missing import to cli.py.\n```python\nimport sys\nimport os\nimport json\nimport typing\n```",
        "actions": ["Add import Optional", "Modify file src/cli.py", "Modify src/main.py", "Modify src/db.py"],
        "checks": ["Verify code compiles"]
    })
    
    mock_test_json = json.dumps({
        "bdd_scenarios": ["Scenario: Verify cli runs without NameError"],
        "pytest_skeletons": ["def test_cli_import():\n    pass"]
    })
    
    mock_skeptic_json = json.dumps({
        "critique": "The solution looks solid. No loopholes found.",
        "gaps": [],
        "challenges": []
    })
    
    # Sequential mock execution
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
        res = await team.execute_step_debate(session_id, "Explain details")
        
        assert res["status"] == "COMPLETED"
        assert "Proposing to add the missing import" in res["feedback"]
        assert "Skeptic's Critique" in res["feedback"]
        
        # Verify artifacts were created programmatically from structured TestStrategyOutput
        artifacts = repository.get_artifacts(db_session, session_id)
        artifact_types = [a.type for a in artifacts]
        assert "BDD_SCENARIO" in artifact_types
        assert "TEST_SKELETON" in artifact_types
