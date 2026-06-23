from pytest_bdd import scenarios, given, when, then
from unittest.mock import patch
from src.state import repository

# Locate feature file relative to this test file
scenarios('../features/coach_workflow.feature')

@given("a developer has a description of a bug", target_fixture="bug_description")
def given_bug_description():
    return "The system crashes with 500 internal server error when parsing passwords."

@when("the developer submits it to the coach", target_fixture="session_state")
def when_developer_submits(db_session, bug_description):
    with patch("src.api.routes.classify_input") as mock_classify:
        mock_classify.return_value = {"type": "BUG", "question": None}
        
        # Simulate router creation
        session = repository.create_session(db_session, raw_input=bug_description, session_type="BUG")
        from src.workflows.bug import bug_workflow
        repository.add_steps(db_session, session.id, bug_workflow.get_step_names())
        return repository.get_session(db_session, session.id)

@then("a coaching session is created with the BUG workflow checklist")
def then_session_created(session_state):
    assert session_state.id is not None
    assert session_state.type == "BUG"
    assert len(session_state.steps) == 11

@then("the current step is Capture & Clarify")
def then_current_step(session_state):
    pending_step = None
    for step in session_state.steps:
        if step.status == "PENDING":
            pending_step = step.name
            break
    assert pending_step == "Capture & Clarify"
