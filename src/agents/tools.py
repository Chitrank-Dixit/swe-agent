import json
import os
import shutil
import subprocess
from typing import Annotated, Optional
from src.state.db import SessionLocal
from src.state import repository
from src.logging.logger import log_agent_action

# ANSI Colors for UI print in tools
BOLD = "\033[1m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
WHITE = "\033[37m"
RED = "\033[31m"
RESET = "\033[0m"

UNDO_BACKUP_DIR = ".devcoach_backup"

def backup_file(filepath: str):
    """Backs up a file to the undo backup directory before editing."""
    if not os.path.exists(filepath):
        return
    os.makedirs(UNDO_BACKUP_DIR, exist_ok=True)
    # Save a copy with the path flattened
    safe_name = filepath.replace(os.sep, "_")
    shutil.copy2(filepath, os.path.join(UNDO_BACKUP_DIR, safe_name))
    # Keep track of the last edited file path
    with open(os.path.join(UNDO_BACKUP_DIR, "last_edit.txt"), "w", encoding="utf-8") as f:
        f.write(filepath)

def undo_last_edit() -> bool:
    """Restores the last backed up file."""
    last_edit_path = os.path.join(UNDO_BACKUP_DIR, "last_edit.txt")
    if not os.path.exists(last_edit_path):
        return False
    try:
        with open(last_edit_path, "r", encoding="utf-8") as f:
            filepath = f.read().strip()
        safe_name = filepath.replace(os.sep, "_")
        backup_path = os.path.join(UNDO_BACKUP_DIR, safe_name)
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, filepath)
            os.remove(backup_path)
            os.remove(last_edit_path)
            return True
    except Exception:
        pass
    return False

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
            "artifacts": artifacts_data,
            "active_mode": session.active_mode
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

def edit_file(
    session_id: Annotated[str, "The unique UUID of the coaching session"],
    filepath: Annotated[str, "The path of the file to write/modify"],
    content: Annotated[str, "The complete code content to write to the file"]
) -> str:
    """Writes or modifies a file in the workspace. Requires BUILD mode."""
    db = SessionLocal()
    try:
        session = repository.get_session(db, session_id)
        if not session:
            return "Error: Session not found."
            
        if session.active_mode != "BUILD":
            return "Execution Blocked: DevCoach is in PLAN MODE. Switch to BUILD MODE via '/build' to execute file edits."
            
        # Pause and ask for user confirmation
        print(f"\n{BOLD}{YELLOW}🔨 [BUILD MODE] Agent wants to write to file: {CYAN}{filepath}{RESET}")
        print(f"{BOLD}Content size: {len(content)} characters.{RESET}")
        confirm = input(f"{BOLD}{WHITE}Confirm file change? (y/n): {RESET}").strip().lower()
        if confirm != 'y':
            return "Execution Rejected: User did not confirm the file edit."
            
        # Backup before modification
        backup_file(filepath)
        
        # Write to file
        if os.path.dirname(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
            
        return f"Success: File '{filepath}' written successfully."
    except Exception as e:
        return f"Error writing file: {e}"
    finally:
        db.close()

def run_test_command(
    session_id: Annotated[str, "The unique UUID of the coaching session"],
    command: Annotated[str, "The test/shell command to execute"]
) -> str:
    """Runs a test or diagnostics shell command. Requires BUILD mode."""
    db = SessionLocal()
    try:
        session = repository.get_session(db, session_id)
        if not session:
            return "Error: Session not found."
            
        if session.active_mode != "BUILD":
            return "Execution Blocked: DevCoach is in PLAN MODE. Switch to BUILD MODE via '/build' to run commands."
            
        # Pause and ask for user confirmation
        print(f"\n{BOLD}{YELLOW}🔨 [BUILD MODE] Agent wants to run command: {CYAN}{command}{RESET}")
        confirm = input(f"{BOLD}{WHITE}Confirm execution? (y/n): {RESET}").strip().lower()
        if confirm != 'y':
            return "Execution Rejected: User did not confirm command execution."
            
        # Run command
        try:
            result = subprocess.run(command, shell=True, text=True, capture_output=True, timeout=30)
            output = f"Exit code: {result.returncode}\n\nStdout:\n{result.stdout}\n\nStderr:\n{result.stderr}"
            return output
        except Exception as e:
            return f"Error running command: {e}"
    finally:
        db.close()
