import pytest
from unittest.mock import patch, MagicMock
from src.agents import factory, tools, team
from src.state import repository

def test_agent_factory_initialization():
    """Verifies that agents are correctly instantiated with expected names and configurations."""
    client = MagicMock()
    
    coordinator = factory.create_coordinator_agent(client)
    assert coordinator.name == "CoordinatorAgent"
    
    bug_coach = factory.create_bug_coach_agent(client)
    assert bug_coach.name == "BugWorkflowCoach"
    
    feature_coach = factory.create_feature_coach_agent(client)
    assert feature_coach.name == "FeatureWorkflowCoach"
    
    meeting_coach = factory.create_meeting_coach_agent(client)
    assert meeting_coach.name == "MeetingWorkflowCoach"
    
    test_strategy = factory.create_test_strategy_agent(client)
    assert test_strategy.name == "TestStrategyAgent"
    
    observability = factory.create_observability_agent(client)
    assert observability.name == "ObservabilityAgent"
    
    skeptic = factory.create_skeptic_agent(client)
    assert skeptic.name == "SkepticCriticAgent"
    
    judge = factory.create_judge_agent(client)
    assert judge.name == "RegretGuardJudge"

def test_database_tools_integration(db_session):
    """Verifies that the agent tools get_session_state, update_step_status, and create_artifact execute correctly against the database."""
    # 1. Setup session
    session = repository.create_session(db_session, raw_input="Refactor auth service.", session_type="FEATURE")
    repository.add_steps(db_session, session.id, ["Understand Problem & Goals", "BDD / Acceptance Criteria"])
    
    # Patch the SessionLocal used by tools to point to our test db_session
    with patch("src.agents.tools.SessionLocal", return_value=db_session):
        # Test get_session_state
        state_str = tools.get_session_state(session.id)
        assert session.id in state_str
        assert "FEATURE" in state_str
        assert "Understand Problem & Goals" in state_str
        
        # Test update_step_status
        res_update = tools.update_step_status(
            session_id=session.id,
            step_name="Understand Problem & Goals",
            status="COMPLETED"
        )
        assert "success" in res_update
        
        # Verify status in db
        session_db = repository.get_session(db_session, session.id)
        assert session_db.steps[0].status == "COMPLETED"
        
        # Test create_artifact
        res_artifact = tools.create_artifact(
            session_id=session.id,
            name="acceptance.feature",
            artifact_type="BDD_SCENARIO",
            content="Feature: Auth refactoring"
        )
        assert "success" in res_artifact
        
        # Verify artifact in db
        artifacts = repository.get_artifacts(db_session, session.id)
        assert len(artifacts) == 1
        assert artifacts[0].name == "acceptance.feature"

@pytest.mark.asyncio
async def test_classify_input_offline_fallback():
    """Verifies that classify_input falls back to keyword-based heuristics when the LLM is offline/errored."""
    with patch("src.agents.team.get_model_client", side_effect=Exception("LLM offline")):
        # Test bug input fallback
        res_bug = await team.classify_input("I have an error in password parser")
        assert res_bug["type"] == "BUG"
        
        # Test performance / delay fallback (user specific query)
        res_delay = await team.classify_input("I am getting some delay in my python program, how to find the root cause in the code, I want to know which part of the program is taking time?")
        assert res_delay["type"] == "BUG"
        
        # Test feature input fallback
        res_feat = await team.classify_input("We should add a logging system")
        assert res_feat["type"] == "FEATURE"
        
        # Test default fallback
        res_meet = await team.classify_input("Review our calendar agenda")
        assert res_meet["type"] == "MEETING/PLANNING"

@pytest.mark.asyncio
async def test_execute_step_debate_offline_fallback(db_session):
    """Verifies that execute_step_debate completes the step gracefully when LLM connection is offline."""
    session = repository.create_session(db_session, raw_input="Bug in login", session_type="BUG")
    repository.add_steps(db_session, session.id, ["Capture & Clarify"])
    session_id = session.id
    
    with patch("src.agents.team.SessionLocal", return_value=db_session):
        with patch("autogen_agentchat.teams.RoundRobinGroupChat.run_stream", side_effect=Exception("Connection refused")):
            # execute_step_debate will raise exception on team.run_stream, triggering fallback
            # Let's verify it transitions status to COMPLETED
            result = await team.execute_step_debate(session_id, "macOS Catalina environment")
            
            assert result["session_id"] == session_id
            assert result["status"] == "COMPLETED"
            assert "LLM debate offline" in result["feedback"]
            
            # Verify DB step is updated
            step = db_session.query(repository.StepModel).filter(
                repository.StepModel.session_id == session_id,
                repository.StepModel.name == "Capture & Clarify"
            ).first()
            assert step.status == "COMPLETED"

@pytest.mark.asyncio
async def test_execute_step_debate_skip_non_critical(db_session):
    """Verifies that skipping a non-critical step succeeds immediately and bypasses debate."""
    session = repository.create_session(db_session, raw_input="Bug in login", session_type="BUG")
    repository.add_steps(db_session, session.id, ["Capture & Clarify"]) # non-critical step
    session_id = session.id
    
    with patch("src.agents.team.SessionLocal", return_value=db_session):
        result = await team.execute_step_debate(session_id, "skip")
        
        assert result["session_id"] == session_id
        assert result["status"] == "SKIPPED"
        assert "skipped successfully" in result["feedback"].lower()
        
        # Verify DB step is updated
        step = db_session.query(repository.StepModel).filter(
            repository.StepModel.session_id == session_id,
            repository.StepModel.name == "Capture & Clarify"
        ).first()
        assert step.status == "SKIPPED"
        assert step.reason == "Skipped by developer"

@pytest.mark.asyncio
async def test_execute_step_debate_skip_critical_no_reason(db_session):
    """Verifies that skipping a critical step without a reason is blocked."""
    session = repository.create_session(db_session, raw_input="Bug in login", session_type="BUG")
    repository.add_steps(db_session, session.id, ["Monitoring, Observability & Profiling"]) # critical step
    session_id = session.id
    
    with patch("src.agents.team.SessionLocal", return_value=db_session):
        result = await team.execute_step_debate(session_id, "skip")
        
        assert result["session_id"] == session_id
        assert result["status"] == "PENDING"
        assert "cannot skip it without providing a valid reason" in result["feedback"].lower()
        
        # Verify DB step is still PENDING
        step = db_session.query(repository.StepModel).filter(
            repository.StepModel.session_id == session_id,
            repository.StepModel.name == "Monitoring, Observability & Profiling"
        ).first()
        assert step.status == "PENDING"

@pytest.mark.asyncio
async def test_execute_step_debate_skip_critical_with_reason(db_session):
    """Verifies that skipping a critical step with a reason succeeds immediately."""
    session = repository.create_session(db_session, raw_input="Bug in login", session_type="BUG")
    repository.add_steps(db_session, session.id, ["Monitoring, Observability & Profiling"]) # critical step
    session_id = session.id
    
    with patch("src.agents.team.SessionLocal", return_value=db_session):
        result = await team.execute_step_debate(session_id, "skip because we already setup logging in the main gateway")
        
        assert result["session_id"] == session_id
        assert result["status"] == "SKIPPED"
        assert "skipped successfully" in result["feedback"].lower()
        
        # Verify DB step is updated with reason
        step = db_session.query(repository.StepModel).filter(
            repository.StepModel.session_id == session_id,
            repository.StepModel.name == "Monitoring, Observability & Profiling"
        ).first()
        assert step.status == "SKIPPED"
        assert "we already setup logging in the main gateway" in step.reason.lower()
