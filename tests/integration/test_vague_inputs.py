import pytest
from unittest.mock import patch, MagicMock
from src.state import repository
from src.agents import team
from src.state.db import init_db, SessionLocal
from src.state.models import SessionModel

@pytest.mark.asyncio
async def test_classify_vague_input_resolves_to_bug_with_subtype():
    # Vague input "my program is slow" should map directly to Performance Investigation
    res = await team.classify_input("my program is slow")
    assert res["type"] == "BUG"
    assert res["subtype"] == "Performance Investigation"
    assert res["question"] is None

    # Vague input "app is crashing with exception" should map directly to Crash Investigation
    res_crash = await team.classify_input("app is crashing with exception")
    assert res_crash["type"] == "BUG"
    assert res_crash["subtype"] == "Crash Investigation"

    # Explicit planning mentions should bypass playbook matching
    # We patch LLM to raise Exception to verify the fallback type
    with patch("src.agents.team.get_model_client", side_effect=Exception("Offline")):
        res_fall = await team.classify_input("Schedule a planning meeting to discuss slowness")
        assert res_fall["type"] == "MEETING/PLANNING"

def test_db_session_persists_subtype(db_session):
    # Setup session with subtype
    session = repository.create_session(
        db_session, 
        raw_input="database query is taking too long", 
        session_type="BUG", 
        subtype="Database Investigation"
    )
    
    # Retrieve from DB and verify
    session_db = repository.get_session(db_session, session.id)
    assert session_db is not None
    assert session_db.type == "BUG"
    assert session_db.subtype == "Database Investigation"

    # Verify update session type preserves/writes subtype
    session_updated = repository.update_session_type(
        db_session, 
        session.id, 
        new_type="BUG", 
        subtype="Performance Investigation"
    )
    assert session_updated.subtype == "Performance Investigation"
