from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from src.state.models import SessionModel, StepModel, ArtifactModel

def create_session(db: Session, raw_input: str, session_type: str, subtype: Optional[str] = None, active_mode: str = "PLAN") -> SessionModel:
    """Creates a new coaching session."""
    session = SessionModel(
        raw_input=raw_input,
        type=session_type,
        subtype=subtype,
        active_mode=active_mode
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def get_session(db: Session, session_id: str) -> Optional[SessionModel]:
    """Retrieves a coaching session with joined steps and artifacts."""
    return db.query(SessionModel).filter(SessionModel.id == session_id).first()

def update_session_type(db: Session, session_id: str, new_type: str, subtype: Optional[str] = None) -> Optional[SessionModel]:
    """Updates the classification of a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session:
        session.type = new_type
        session.subtype = subtype
        db.commit()
        db.refresh(session)
    return session

def add_steps(db: Session, session_id: str, step_names: List[str]) -> List[StepModel]:
    """Creates initial steps in PENDING state for a session."""
    steps = []
    for name in step_names:
        step = StepModel(
            session_id=session_id,
            name=name,
            status="PENDING"
        )
        db.add(step)
        steps.append(step)
    db.commit()
    return steps

def update_step_status(
    db: Session,
    session_id: str,
    step_name: str,
    status: str,
    reason: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None
) -> Optional[StepModel]:
    """Updates the status and data of a specific workflow step."""
    step = db.query(StepModel).filter(
        StepModel.session_id == session_id,
        StepModel.name == step_name
    ).first()
    
    if step:
        step.status = status
        if reason:
            step.reason = reason
        if data:
            if step.data:
                # Merge existing JSON data with updates
                merged = dict(step.data)
                merged.update(data)
                step.data = merged
            else:
                step.data = data
        db.commit()
        db.refresh(step)
    return step

def create_artifact(
    db: Session,
    session_id: str,
    name: str,
    artifact_type: str,
    content: str
) -> ArtifactModel:
    """Creates a new text artifact linked to a session."""
    artifact = ArtifactModel(
        session_id=session_id,
        name=name,
        type=artifact_type,
        content=content
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)
    return artifact

def get_artifacts(db: Session, session_id: str) -> List[ArtifactModel]:
    """Gets all artifacts created for a session."""
    return db.query(ArtifactModel).filter(ArtifactModel.session_id == session_id).all()

def update_session_mode(db: Session, session_id: str, active_mode: str) -> Optional[SessionModel]:
    """Updates the active mode (PLAN / BUILD) of a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session:
        session.active_mode = active_mode
        db.commit()
        db.refresh(session)
    return session

