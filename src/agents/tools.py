import json
from typing import Annotated, Optional
from src.state.db import SessionLocal
from src.state import repository
from src.logging.logger import log_agent_action

def get_session_state(
    session_id: Annotated[str, "The unique UUID of the coaching session"]
) -> str:
    """Retrieves the full status of a coaching session, including all steps (with their status) and generated artifacts."""
    db = SessionLocal()
    try:
        session = repository.get_session(db, session_id)
        if not session:
            return json.dumps({"error": f"Session {session_id} not found."})
        
        steps_data = []
        for step in session.steps:
            steps_data.append({
                "name": step.name,
                "status": step.status,
                "reason": step.reason,
                "data": step.data
            })
            
        artifacts_data = []
        for art in session.artifacts:
            artifacts_data.append({
                "name": art.name,
                "type": art.type,
                "created_at": art.created_at.isoformat()
            })
            
        return json.dumps({
            "session_id": session.id,
            "type": session.type,
            "raw_input": session.raw_input,
            "steps": steps_data,
            "artifacts": artifacts_data
        }, indent=2)
    finally:
        db.close()

def update_step_status(
    session_id: Annotated[str, "The unique UUID of the coaching session"],
    step_name: Annotated[str, "The exact name of the workflow step to update"],
    status: Annotated[str, "The target status (COMPLETED or SKIPPED)"],
    reason: Annotated[Optional[str], "Required if status is SKIPPED. The explanation for skipping the step."] = None
) -> str:
    """Updates the status (COMPLETED or SKIPPED) of a workflow step in the database."""
    db = SessionLocal()
    try:
        step = repository.update_step_status(
            db,
            session_id=session_id,
            step_name=step_name,
            status=status,
            reason=reason
        )
        if not step:
            return json.dumps({"error": f"Step '{step_name}' not found for session {session_id}."})
            
        log_agent_action(
            session_id=session_id,
            agent_name="RegretGuardJudge",
            step_name=step_name,
            message=f"Step status updated to {status}",
            decision=status,
            extra_data={"reason": reason} if reason else None
        )
        
        return json.dumps({
            "success": True,
            "step_name": step_name,
            "status": step.status,
            "reason": step.reason
        })
    finally:
        db.close()

def create_artifact(
    session_id: Annotated[str, "The unique UUID of the coaching session"],
    name: Annotated[str, "Name of the artifact (e.g. 'failing_tdd_test.py')"],
    artifact_type: Annotated[str, "Type of artifact (BDD_SCENARIO, TEST_SKELETON, MONITORING_PLAN, SUMMARY)"],
    content: Annotated[str, "Text content of the artifact"]
) -> str:
    """Creates and persists a generated artifact (e.g., test skeletons, BDD scenarios, dashboards) in the database."""
    db = SessionLocal()
    try:
        artifact = repository.create_artifact(
            db,
            session_id=session_id,
            name=name,
            artifact_type=artifact_type,
            content=content
        )
        log_agent_action(
            session_id=session_id,
            agent_name="RegretGuardJudge",
            step_name="Create Artifact",
            message=f"Artifact created: {name} (Type: {artifact_type})"
        )
        return json.dumps({
            "success": True,
            "artifact_id": artifact.id,
            "name": artifact.name,
            "type": artifact.type
        })
    finally:
        db.close()
