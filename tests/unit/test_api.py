from unittest.mock import patch
from fastapi.testclient import TestClient

def test_api_session_lifecycle(client: TestClient, db_session):
    # Mock classification to return BUG
    with patch("src.api.routes.classify_input") as mock_classify:
        mock_classify.return_value = {"type": "BUG", "question": None}
        
        # 1. POST /sessions
        # Note: routes.py will query `Depends(get_db)` which yields `db_session` from conftest
        response = client.post("/api/sessions", json={"raw_input": "I found a crash in Auth module."})
        assert response.status_code == 201
        data = response.json()
        assert data["session_id"] is not None
        assert data["type"] == "BUG"
        assert len(data["steps"]) == 11
        assert data["current_step"] == "Capture & Clarify"
        assert data["next_step"] == "Define Failing Behavior"
        session_id = data["session_id"]

    # Mock step debate to complete current step
    with patch("src.api.routes.execute_step_debate") as mock_debate:
        mock_debate.return_value = {
            "session_id": session_id,
            "current_step": "Capture & Clarify",
            "status": "COMPLETED",
            "feedback": "Step completed. Let's move to Define Failing Behavior.",
            "transcript": []
        }
        
        # 2. POST /sessions/{id}/step
        # First step completion
        # We need to simulate the database state changes that would happen during the debate
        def simulate_debate(sess_id, user_in):
            from src.state import repository
            repository.update_step_status(db_session, sess_id, "Capture & Clarify", "COMPLETED")
            return {
                "session_id": sess_id,
                "current_step": "Capture & Clarify",
                "status": "COMPLETED",
                "feedback": "Capture step completed.",
                "transcript": []
            }
        
        mock_debate.side_effect = simulate_debate
        
        response = client.post(f"/api/sessions/{session_id}/step", json={"user_input": "happens on staging"})
        assert response.status_code == 200
        data = response.json()
        assert data["steps"][0]["name"] == "Capture & Clarify"
        assert data["steps"][0]["status"] == "COMPLETED"
        assert data["current_step"] == "Define Failing Behavior"
        
    # 3. GET /sessions/{id}
    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["steps"][0]["status"] == "COMPLETED"
    assert data["steps"][1]["status"] == "PENDING"
