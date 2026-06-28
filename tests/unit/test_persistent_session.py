import pytest
from unittest.mock import patch, MagicMock
from src.cli import interactive_cli
from src.state import repository
from src.workflows.general import general_workflow
from src.workflows.bug import bug_workflow

@pytest.mark.asyncio
async def test_general_question_answered_session_remains_open_and_reuse_id(db_session):
    call_count = 0
    async def mock_get_input(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "Explain decorators"
        elif call_count == 2:
            return "Explain metaclasses"
        elif call_count == 3:
            return "/quit"
        raise AssertionError("get_multiline_input called too many times")

    session_ids = []
    async def mock_execute_debate(session_id, user_input, on_token_callback=None):
        session_ids.append(session_id)
        repository.update_step_status(db_session, session_id, "Address Question", "COMPLETED")
        return {"status": "COMPLETED", "feedback": "Completed query.", "transcript": []}

    with patch("src.cli.SessionLocal", return_value=db_session), \
         patch("src.cli.get_multiline_input", side_effect=mock_get_input), \
         patch("src.cli.classify_input", return_value={"type": "GENERAL_ENGINEERING_QUESTION", "question": None}), \
         patch("src.cli.execute_step_debate", side_effect=mock_execute_debate), \
         patch("src.cli.print_welcome_box"), \
         patch("src.cli.print_prompt_bar"), \
         patch("builtins.print") as mock_print:
         
         await interactive_cli()

         assert len(session_ids) == 2
         assert session_ids[0] == session_ids[1]

         printed_texts = [call[0][0] for call in mock_print.call_args_list if call[0]]
         assert any("Goodbye" in t for t in printed_texts)


@pytest.mark.asyncio
async def test_bug_workflow_completed_remains_open_and_new_task(db_session):


    session = repository.create_session(
        db_session,
        raw_input="Fix NameError in cli.py",
        session_type="BUG"
    )
    steps_list = bug_workflow.get_step_names()
    repository.add_steps(db_session, session.id, steps_list)

    call_count = 0
    async def mock_get_input(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "Fix NameError in cli.py"
        elif call_count == 2:
            return "input for step 1"
        elif call_count == 3:
            return "Explain how to write decorators"
        elif call_count == 4:
            return "/exit"
        raise AssertionError(f"get_multiline_input called too many times: {call_count}")

    session_ids = []
    async def mock_execute_debate(session_id, user_input, on_token_callback=None):
        session_ids.append(session_id)
        session = repository.get_session(db_session, session_id)
        for s in session.steps:
            if s.status == "PENDING":
                repository.update_step_status(db_session, session_id, s.name, "COMPLETED")
        return {"status": "COMPLETED", "feedback": "Step completed.", "transcript": []}

    classifications = [
        {"type": "BUG", "question": None},
        {"type": "GENERAL_ENGINEERING_QUESTION", "question": None}
    ]
    class_idx = 0
    async def mock_classify(user_input, on_token_callback=None):
        nonlocal class_idx
        res = classifications[class_idx]
        if class_idx == 0:
            class_idx += 1
        return res

    with patch("src.cli.SessionLocal", return_value=db_session), \
         patch("src.cli.get_multiline_input", side_effect=mock_get_input), \
         patch("src.cli.classify_input", side_effect=mock_classify), \
         patch("src.cli.execute_step_debate", side_effect=mock_execute_debate), \
         patch("src.cli.print_welcome_box"), \
         patch("src.cli.print_prompt_bar"), \
         patch("builtins.print") as mock_print:
         
         try:
             await interactive_cli()
         except Exception as e:
             import sys
             sys.stderr.write(f"interactive_cli raised: {e}\n")
             raise e

         import sys
         sys.stderr.write(f"CALL ARGS LIST: {mock_print.call_args_list}\n")
         assert len(session_ids) > 1
         assert len(set(session_ids)) == 1

         printed_texts = [str(call[0][0]) for call in mock_print.call_args_list if call[0]]
         assert any("Workflow complete" in t for t in printed_texts)
         assert any("Goodbye" in t for t in printed_texts)


@pytest.mark.asyncio
async def test_q_cleanly_exits(db_session):
    async def mock_get_input(*args, **kwargs):
        return "/q"

    with patch("src.cli.SessionLocal", return_value=db_session), \
         patch("src.cli.get_multiline_input", side_effect=mock_get_input), \
         patch("builtins.print") as mock_print:
         
         await interactive_cli()
         printed_texts = [call[0][0] for call in mock_print.call_args_list if call[0]]
         assert any("Goodbye" in t for t in printed_texts)
