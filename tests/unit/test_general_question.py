import pytest
from unittest.mock import patch, MagicMock
from src.agents import factory, team
from src.state import repository
from src.skills.registry import skills_registry

def test_load_agent_prompt():
    # Test fallback
    p = factory.load_agent_prompt("non_existent_agent", "fallback_message")
    assert p == "fallback_message"

    # Test loading existing prompt (coordinator exists)
    p2 = factory.load_agent_prompt("coordinator", "fallback")
    assert p2 != "fallback"
    assert "Software Engineering Workflow Coach" in p2

def test_skills_registry():
    # Verify code analyzer skill was loaded
    analyzer_skill = skills_registry.get_skill("code_analyzer")
    assert analyzer_skill is not None
    assert "Code Analysis" in analyzer_skill

@pytest.mark.asyncio
async def test_classify_general_question_offline_fallback():
    # Verify offline fallback keywords
    with patch("src.agents.team.get_model_client", side_effect=Exception("Offline")):
        res = await team.classify_input("Explain the difference between list and dict?")
        assert res["type"] == "GENERAL_ENGINEERING_QUESTION"

        res2 = await team.classify_input("how to optimize database queries")
        assert res2["type"] == "GENERAL_ENGINEERING_QUESTION"

def test_db_session_general_question(db_session):
    # Verify database session creation works with GENERAL_ENGINEERING_QUESTION
    session = repository.create_session(
        db_session,
        raw_input="Explain python lists",
        session_type="GENERAL_ENGINEERING_QUESTION"
    )
    assert session.id is not None
    assert session.type == "GENERAL_ENGINEERING_QUESTION"

    # Verify add steps
    from src.workflows.general import general_workflow
    steps = repository.add_steps(db_session, session.id, general_workflow.get_step_names())
    assert len(steps) == 1
    assert steps[0].name == "Address Question"
    assert steps[0].status == "PENDING"

@pytest.mark.asyncio
async def test_general_question_short_circuit(db_session):
    from src.cli import interactive_cli
    from src.state import repository
    from src.workflows.general import general_workflow

    session = repository.create_session(
        db_session,
        raw_input="What is a decorator?",
        session_type="GENERAL_ENGINEERING_QUESTION"
    )
    repository.add_steps(db_session, session.id, general_workflow.get_step_names())

    call_count = 0
    async def mock_get_input():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "What is a decorator?"
        raise AssertionError("get_multiline_input should not be called again in short-circuit!")

    mock_print_checklist = MagicMock()

    async def mock_execute_debate(session_id, user_input, on_token_callback=None):
        assert user_input == "What is a decorator?"
        repository.update_step_status(db_session, session_id, "Address Question", "COMPLETED")
        return {"status": "COMPLETED", "feedback": "Answered decorator query.", "transcript": []}

    with patch("src.cli.SessionLocal", return_value=db_session), \
         patch("src.cli.get_multiline_input", side_effect=mock_get_input), \
         patch("src.cli.classify_input", return_value={"type": "GENERAL_ENGINEERING_QUESTION", "question": None}), \
         patch("src.cli.execute_step_debate", side_effect=mock_execute_debate) as mock_debate, \
         patch("src.cli.print_workflow_checklist", mock_print_checklist), \
         patch("src.cli.print_welcome_box"), \
         patch("src.cli.print_prompt_bar"), \
         patch("builtins.print"):
         
         await interactive_cli()
         
         mock_debate.assert_called_once()
         mock_print_checklist.assert_not_called()

@pytest.mark.asyncio
async def test_general_question_skip_guard(db_session):
    from src.cli import handle_slash_command
    from src.state import repository
    from src.workflows.general import general_workflow

    session = repository.create_session(
        db_session,
        raw_input="Explain context managers",
        session_type="GENERAL_ENGINEERING_QUESTION"
    )
    repository.add_steps(db_session, session.id, general_workflow.get_step_names())

    # 1. Skip Guard: cancelled skip (confirm 'n')
    with patch("builtins.input", return_value="n"), \
         patch("builtins.print"):
        is_cmd, action = await handle_slash_command("/skip", session.id, db_session)
        assert is_cmd is True
        assert action == "continue"
        
        session = repository.get_session(db_session, session.id)
        step = session.steps[0]
        assert step.status == "PENDING"

    # 2. Skip Guard: confirmed skip (confirm 'y')
    with patch("builtins.input", return_value="y"), \
         patch("builtins.print"):
        is_cmd, action = await handle_slash_command("/skip", session.id, db_session)
        assert is_cmd is True
        assert action == "continue"
        
        session = repository.get_session(db_session, session.id)
        step = session.steps[0]
        assert step.status == "SKIPPED"

@pytest.mark.asyncio
async def test_general_question_text_skip_guard(db_session):
    from src.cli import interactive_cli
    from src.state import repository
    from src.workflows.general import general_workflow

    session = repository.create_session(
        db_session,
        raw_input="Explain context managers",
        session_type="GENERAL_ENGINEERING_QUESTION"
    )
    repository.add_steps(db_session, session.id, general_workflow.get_step_names())

    call_count = 0
    async def mock_get_input():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "Explain context managers"
        elif call_count == 2:
            return "skip"
        else:
            return "my actual query"

    debate_calls = []
    async def mock_execute_debate(session_id, user_input, on_token_callback=None):
        debate_calls.append(user_input)
        if len(debate_calls) == 1:
            return {"status": "PENDING", "feedback": "Need more info.", "transcript": []}
        else:
            repository.update_step_status(db_session, session_id, "Address Question", "COMPLETED")
            return {"status": "COMPLETED", "feedback": "Completed.", "transcript": []}

    with patch("src.cli.SessionLocal", return_value=db_session), \
         patch("src.cli.get_multiline_input", side_effect=mock_get_input), \
         patch("src.cli.classify_input", return_value={"type": "GENERAL_ENGINEERING_QUESTION", "question": None}), \
         patch("src.cli.execute_step_debate", side_effect=mock_execute_debate), \
         patch("builtins.input", return_value="n") as mock_confirm, \
         patch("src.cli.print_welcome_box"), \
         patch("src.cli.print_prompt_bar"), \
         patch("builtins.print"):
         
         await interactive_cli()
         
         mock_confirm.assert_called_once()
         assert debate_calls == ["Explain context managers", "my actual query"]

@pytest.mark.asyncio
async def test_execute_step_debate_general_question_direct_routing(db_session):
    from src.state import repository
    from src.workflows.general import general_workflow
    from src.agents import team
    from autogen_agentchat.base import TaskResult
    from autogen_agentchat.messages import TextMessage

    session = repository.create_session(
        db_session,
        raw_input="What is polymorphism?",
        session_type="GENERAL_ENGINEERING_QUESTION"
    )
    session_id = session.id
    repository.add_steps(db_session, session_id, general_workflow.get_step_names())

    # Set up mock agent and stream
    mock_agent = MagicMock()
    mock_agent.name = "GeneralEngineeringAdvisor"

    # Define an async generator to mock run_stream
    async def mock_run_stream(task):
        yield TextMessage(content="Polymorphism is...", source="GeneralEngineeringAdvisor")
        yield TaskResult(messages=[TextMessage(content="Polymorphism is...", source="GeneralEngineeringAdvisor")])

    mock_agent.run_stream.side_effect = mock_run_stream

    with patch("src.agents.team.SessionLocal", return_value=db_session), \
         patch("src.agents.team.create_general_advisor_agent", return_value=mock_agent) as mock_create_agent:
         
         result = await team.execute_step_debate(session_id, "What is polymorphism?")
         
         mock_create_agent.assert_called_once()
         mock_agent.run_stream.assert_called_once_with(task="What is polymorphism?")
         assert result["status"] == "COMPLETED"
         assert result["feedback"] == "Polymorphism is..."
         
         # Verify database status is updated
         step = db_session.query(repository.StepModel).filter(
             repository.StepModel.session_id == session_id,
             repository.StepModel.name == "Address Question"
         ).first()
         assert step.status == "COMPLETED"

@pytest.mark.asyncio
async def test_general_question_with_code_snippets(db_session):
    from src.cli import interactive_cli
    from src.state import repository
    from src.workflows.general import general_workflow

    session = repository.create_session(
        db_session,
        raw_input="How does this function work?\n```python\ndef add(a, b):\n    return a + b\n```",
        session_type="GENERAL_ENGINEERING_QUESTION"
    )
    repository.add_steps(db_session, session.id, general_workflow.get_step_names())

    call_count = 0
    async def mock_get_input():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "How does this function work?\n```python\ndef add(a, b):\n    return a + b\n```"
        raise AssertionError("get_multiline_input should not be called again in short-circuit!")

    async def mock_execute_debate(session_id, user_input, on_token_callback=None):
        assert "def add(a, b):" in user_input
        repository.update_step_status(db_session, session_id, "Address Question", "COMPLETED")
        return {"status": "COMPLETED", "feedback": "It adds two numbers.", "transcript": []}

    with patch("src.cli.SessionLocal", return_value=db_session), \
         patch("src.cli.get_multiline_input", side_effect=mock_get_input), \
         patch("src.cli.classify_input", return_value={"type": "GENERAL_ENGINEERING_QUESTION", "question": None}), \
         patch("src.cli.execute_step_debate", side_effect=mock_execute_debate) as mock_debate, \
         patch("src.cli.print_workflow_checklist"), \
         patch("src.cli.print_welcome_box"), \
         patch("src.cli.print_prompt_bar"), \
         patch("builtins.print"):
         
         await interactive_cli()
         mock_debate.assert_called_once()


@pytest.mark.asyncio
async def test_general_question_without_code(db_session):
    from src.cli import interactive_cli
    from src.state import repository
    from src.workflows.general import general_workflow

    session = repository.create_session(
        db_session,
        raw_input="What is the time complexity of bubble sort?",
        session_type="GENERAL_ENGINEERING_QUESTION"
    )
    repository.add_steps(db_session, session.id, general_workflow.get_step_names())

    call_count = 0
    async def mock_get_input():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "What is the time complexity of bubble sort?"
        raise AssertionError("get_multiline_input should not be called again in short-circuit!")

    async def mock_execute_debate(session_id, user_input, on_token_callback=None):
        assert user_input == "What is the time complexity of bubble sort?"
        repository.update_step_status(db_session, session_id, "Address Question", "COMPLETED")
        return {"status": "COMPLETED", "feedback": "O(N^2)", "transcript": []}

    with patch("src.cli.SessionLocal", return_value=db_session), \
         patch("src.cli.get_multiline_input", side_effect=mock_get_input), \
         patch("src.cli.classify_input", return_value={"type": "GENERAL_ENGINEERING_QUESTION", "question": None}), \
         patch("src.cli.execute_step_debate", side_effect=mock_execute_debate) as mock_debate, \
         patch("src.cli.print_workflow_checklist"), \
         patch("src.cli.print_welcome_box"), \
         patch("src.cli.print_prompt_bar"), \
         patch("builtins.print"):
         
         await interactive_cli()
         mock_debate.assert_called_once()


@pytest.mark.asyncio
async def test_general_question_skip_warning_and_message(db_session):
    from src.cli import interactive_cli
    from src.state import repository
    from src.workflows.general import general_workflow

    session = repository.create_session(
        db_session,
        raw_input="Explain Python metaclasses",
        session_type="GENERAL_ENGINEERING_QUESTION"
    )
    repository.add_steps(db_session, session.id, general_workflow.get_step_names())

    call_count = 0
    async def mock_get_input():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "Explain Python metaclasses"
        elif call_count == 2:
            return "skip"
        raise AssertionError("Loop should exit after confirm='y'")

    async def mock_execute_debate(session_id, user_input, on_token_callback=None):
        if user_input.strip().lower().startswith("skip"):
            repository.update_step_status(db_session, session_id, "Address Question", "SKIPPED")
            return {"status": "SKIPPED", "feedback": "Skipped.", "transcript": []}
        return {"status": "PENDING", "feedback": "Metaclasses are...", "transcript": []}

    with patch("src.cli.SessionLocal", return_value=db_session), \
         patch("src.cli.get_multiline_input", side_effect=mock_get_input), \
         patch("src.cli.classify_input", return_value={"type": "GENERAL_ENGINEERING_QUESTION", "question": None}), \
         patch("src.cli.execute_step_debate", side_effect=mock_execute_debate), \
         patch("builtins.input", return_value="y") as mock_input, \
         patch("src.cli.print_welcome_box"), \
         patch("src.cli.print_prompt_bar"), \
         patch("builtins.print") as mock_print:
         
         await interactive_cli()
         
         mock_input.assert_called_once()
         printed_texts = [call[0][0] for call in mock_print.call_args_list if call[0]]
         assert any("Session closed. No answer was given." in t for t in printed_texts)
