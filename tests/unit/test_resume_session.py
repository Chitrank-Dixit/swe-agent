import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.cli import interactive_cli
from src.state import repository
from src.workflows.general import general_workflow

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.mark.asyncio
async def test_resume_session_from_arguments(db_session):
    # 1. Create a session with steps
    session = repository.create_session(
        db_session,
        raw_input="Explain Python list comprehensions",
        session_type="GENERAL_ENGINEERING_QUESTION"
    )
    repository.add_steps(db_session, session.id, general_workflow.get_step_names())
    db_session.expire_all()
    
    # 2. Mock inputs: first input for pending step is "my detail", next input is "/quit"
    async def mock_get_input(*args, **kwargs):
        return "/quit"
        
    async def mock_execute_debate(session_id, user_input, on_token_callback=None):
        repository.update_step_status(db_session, session_id, "Address Question", "COMPLETED")
        return {"status": "COMPLETED", "feedback": "Answered details.", "transcript": []}

    # 3. Patch and execute
    with patch("src.cli.SessionLocal", return_value=db_session), \
         patch("src.cli.get_multiline_input", side_effect=mock_get_input), \
         patch("src.cli.classify_input") as mock_classify, \
         patch("src.cli.execute_step_debate", side_effect=mock_execute_debate), \
         patch("src.cli.print_welcome_box") as mock_welcome, \
         patch("src.cli.print_prompt_bar"), \
         patch("builtins.print") as mock_print:
         
         await interactive_cli(session_id=session.id)
         
    printed_texts = [str(call[0][0]) for call in mock_print.call_args_list if call[0]]
    
    # Assert class_res / classification was skipped since we resumed
    mock_classify.assert_not_called()
    mock_welcome.assert_not_called()
    
    assert any("Resumed existing session" in t for t in printed_texts)
    assert any("Goodbye" in t for t in printed_texts)

@pytest.mark.asyncio
async def test_resume_session_from_slash_command(db_session):
    # 1. Create target session we want to resume
    resumed_session = repository.create_session(
        db_session,
        raw_input="Resume target query",
        session_type="GENERAL_ENGINEERING_QUESTION"
    )
    repository.add_steps(db_session, resumed_session.id, general_workflow.get_step_names())
    
    # 2. Create another starting session
    initial_session = repository.create_session(
        db_session,
        raw_input="Initial query",
        session_type="GENERAL_ENGINEERING_QUESTION"
    )
    repository.add_steps(db_session, initial_session.id, general_workflow.get_step_names())

    # 3. Define inputs:
    # First: initial input
    # Second: skip the Address Question step of initial session to trigger loop complete
    # Third: run `/resume <resumed_session.id>`
    # Fourth: step input for resumed session Address Question
    # Fifth: `/quit`
    call_count = 0
    async def mock_get_input(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "Initial query"
        elif call_count == 2:
            return "skip"
        elif call_count == 3:
            return f"/resume {resumed_session.id}"
        elif call_count == 4:
            return "step input for resumed session"
        return "/quit"

    async def mock_execute_debate(session_id, user_input, on_token_callback=None):
        if user_input == "step input for resumed session":
            repository.update_step_status(db_session, session_id, "Address Question", "COMPLETED")
            return {"status": "COMPLETED", "feedback": "Resumed debate results.", "transcript": []}
        return {"status": "PENDING", "feedback": "Feedback.", "transcript": []}

    with patch("src.cli.SessionLocal", return_value=db_session), \
         patch("src.cli.get_multiline_input", side_effect=mock_get_input), \
         patch("src.cli.classify_input", return_value={"type": "GENERAL_ENGINEERING_QUESTION", "question": None}), \
         patch("src.cli.execute_step_debate", side_effect=mock_execute_debate), \
         patch("src.cli.print_welcome_box"), \
         patch("src.cli.print_prompt_bar"), \
         patch("builtins.input", return_value="y"), \
         patch("builtins.print") as mock_print:
         
         await interactive_cli()
         
         printed_texts = [call[0][0] for call in mock_print.call_args_list if call[0]]
         assert any(f"Resuming session: {resumed_session.id}" in t for t in printed_texts)

@pytest.mark.asyncio
async def test_resume_invalid_session_id(db_session):
    with patch("src.cli.SessionLocal", return_value=db_session), \
         patch("builtins.print") as mock_print:
         
         await interactive_cli(session_id="invalid-id")
         
         printed_texts = [call[0][0] for call in mock_print.call_args_list if call[0]]
         assert any("Session 'invalid-id' not found in database" in t for t in printed_texts)
