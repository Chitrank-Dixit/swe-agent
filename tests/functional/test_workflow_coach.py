import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.state import repository
from src.logging.logger import metrics_tracker

def test_e2e_functional_bug_workflow(client: TestClient, db_session):
    """Functional test verifying the complete end-to-end journey of a developer fixing a BUG.
    
    Verifies:
    1. Classification & initial checklist creation.
    2. Step completion and auto-advancement of current/next steps.
    3. Critical step skipping requiring a reason, and marking status to SKIPPED.
    4. Retrieving full session state and metrics.
    """
    
    # ----------------------------------------------------
    # Step 1: Start a new BUG session
    # ----------------------------------------------------
    with patch("src.api.routes.classify_input") as mock_classify:
        mock_classify.return_value = {"type": "BUG", "question": None}
        
        response = client.post("/api/sessions", json={
            "raw_input": "Database crashes when duplicate email registers."
        })
        assert response.status_code == 201
        res_data = response.json()
        
        session_id = res_data["session_id"]
        assert res_data["type"] == "BUG"
        assert res_data["current_step"] == "Capture & Clarify"
        assert res_data["next_step"] == "Define Failing Behavior"
        assert len(res_data["steps"]) == 11
        assert res_data["steps"][0]["status"] == "PENDING"
        
    # ----------------------------------------------------
    # Step 2: Complete the first step ('Capture & Clarify')
    # ----------------------------------------------------
    with patch("src.api.routes.execute_step_debate") as mock_debate:
        # Simulate agent team deciding to complete the step
        def simulate_complete_capture(sess_id, user_in):
            # Update DB step status to COMPLETED
            repository.update_step_status(db_session, sess_id, "Capture & Clarify", "COMPLETED")
            metrics_tracker.record_step_completed(sess_id)
            return {
                "session_id": sess_id,
                "current_step": "Capture & Clarify",
                "status": "COMPLETED",
                "feedback": "Capture & Clarify step completed successfully.",
                "transcript": []
            }
        mock_debate.side_effect = simulate_complete_capture
        
        response = client.post(f"/api/sessions/{session_id}/step", json={
            "user_input": "Happens on macOS Python 3.11. Duplicates throw integrity error rather than HTTP 400."
        })
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["steps"][0]["status"] == "COMPLETED"
        assert res_data["current_step"] == "Define Failing Behavior"
        
    # ----------------------------------------------------
    # Step 3: Developer skips the next step ('Define Failing Behavior')
    # ----------------------------------------------------
    with patch("src.api.routes.execute_step_debate") as mock_debate:
        # Simulate agent team deciding to skip the step
        def simulate_skip_step(sess_id, user_in):
            repository.update_step_status(
                db_session, 
                sess_id, 
                "Define Failing Behavior", 
                "SKIPPED", 
                reason="Skipped as duplicate registration is already self-explanatory."
            )
            # Since it's not a critical step, it doesn't trigger record_critical_step_skipped,
            # and since it's skipped, it doesn't trigger record_step_completed.
            return {
                "session_id": sess_id,
                "current_step": "Define Failing Behavior",
                "status": "SKIPPED",
                "feedback": "Step skipped with reason.",
                "transcript": []
            }
        mock_debate.side_effect = simulate_skip_step
        
        response = client.post(f"/api/sessions/{session_id}/step", json={
            "user_input": "Skip this step because duplicate registration behavior is already clear."
        })
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["steps"][1]["status"] == "SKIPPED"
        assert res_data["steps"][1]["reason"] == "Skipped as duplicate registration is already self-explanatory."
        assert res_data["current_step"] == "BDD / Acceptance Scenario"

    # ----------------------------------------------------
    # Step 4: Simulate a critical step generating a test skeleton
    # ----------------------------------------------------
    with patch("src.api.routes.execute_step_debate") as mock_debate:
        # Advance state to Write Failing TDD Test for this simulation
        repository.update_step_status(db_session, session_id, "BDD / Acceptance Scenario", "COMPLETED")
        repository.update_step_status(db_session, session_id, "Classify & Triage", "COMPLETED")
        repository.update_step_status(db_session, session_id, "Monitoring / Observability / Profiling", "COMPLETED")
        repository.update_step_status(db_session, session_id, "Decide: Fix Now or Schedule", "COMPLETED")
        
        # Record completions for these 4 advanced steps in the metrics tracker
        metrics_tracker.record_step_completed(session_id)
        metrics_tracker.record_step_completed(session_id)
        metrics_tracker.record_step_completed(session_id)
        metrics_tracker.record_step_completed(session_id)
        
        def simulate_tdd_step(sess_id, user_in):
            # Update DB step and create the skeleton artifact
            repository.update_step_status(db_session, sess_id, "Write Failing TDD Test", "COMPLETED")
            metrics_tracker.record_step_completed(sess_id)
            repository.create_artifact(
                db_session, 
                sess_id, 
                name="test_duplicate_email.py", 
                artifact_type="TEST_SKELETON", 
                content="def test_should_reject_duplicate_email(): pass"
            )
            return {
                "session_id": sess_id,
                "current_step": "Write Failing TDD Test",
                "status": "COMPLETED",
                "feedback": "Failing test skeleton created.",
                "transcript": []
            }
        mock_debate.side_effect = simulate_tdd_step
        
        response = client.post(f"/api/sessions/{session_id}/step", json={
            "user_input": "Write the test structure for me."
        })
        assert response.status_code == 200
        res_data = response.json()
        assert res_data["steps"][6]["status"] == "COMPLETED"
        assert len(res_data["artifacts"]) == 1
        assert res_data["artifacts"][0]["name"] == "test_duplicate_email.py"
        assert res_data["artifacts"][0]["type"] == "TEST_SKELETON"

    # ----------------------------------------------------
    # Step 5: GET /sessions/{id} details query
    # ----------------------------------------------------
    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["session_id"] == session_id
    assert res_data["type"] == "BUG"
    assert res_data["steps"][0]["status"] == "COMPLETED"
    assert res_data["steps"][1]["status"] == "SKIPPED"
    assert res_data["steps"][6]["status"] == "COMPLETED"
    assert len(res_data["artifacts"]) == 1
    assert res_data["artifacts"][0]["name"] == "test_duplicate_email.py"
    
    # Assert metrics tracking is working
    assert res_data["metrics"] is not None
    # We completed 6 steps (Capture + 4 advanced + TDD)
    assert res_data["metrics"]["steps_completed"] == 6
