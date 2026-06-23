from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.state.db import get_db
from src.state import repository
from src.agents.team import classify_input, execute_step_debate
from src.workflows.bug import bug_workflow
from src.workflows.feature import feature_workflow
from src.workflows.meeting import meeting_workflow
from src.logging.logger import metrics_tracker

router = APIRouter()

# Pydantic Schemas
class SessionCreateRequest(BaseModel):
    raw_input: str

class SessionStepRequest(BaseModel):
    user_input: str

class StepResponseSchema(BaseModel):
    name: str
    status: str
    reason: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class ArtifactResponseSchema(BaseModel):
    name: str
    type: str
    created_at: str

class SessionResponse(BaseModel):
    session_id: str
    type: str
    raw_input: str
    current_step: Optional[str] = None
    next_step: Optional[str] = None
    steps: List[StepResponseSchema]
    artifacts: List[ArtifactResponseSchema]
    metrics: Optional[Dict[str, Any]] = None
    clarifying_question: Optional[str] = None

def get_next_and_current_steps(session) -> tuple[Optional[str], Optional[str]]:
    """Helper to resolve current step and next step in sequence."""
    current_step = None
    next_step = None
    
    for idx, step in enumerate(session.steps):
        if step.status == "PENDING":
            current_step = step.name
            if idx + 1 < len(session.steps):
                next_step = session.steps[idx + 1].name
            break
            
    return current_step, next_step

@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_new_session(payload: SessionCreateRequest, db: Session = Depends(get_db)):
    """Starts a session by classifying user input and initializing the workflow checklist."""
    classification_res = await classify_input(payload.raw_input)
    session_type = classification_res["type"]
    session_subtype = classification_res.get("subtype")
    clarifying_question = classification_res["question"]
    
    # If type is uncertain, save session as UNCERTAIN first and return question
    session = repository.create_session(db, raw_input=payload.raw_input, session_type=session_type, subtype=session_subtype)
    metrics_tracker.start_session(session.id)
    
    steps_list = []
    if session_type == "BUG":
        steps_list = bug_workflow.get_step_names()
    elif session_type == "FEATURE":
        steps_list = feature_workflow.get_step_names()
    elif session_type == "MEETING/PLANNING":
        steps_list = meeting_workflow.get_step_names()
        
    if steps_list:
        repository.add_steps(db, session_id=session.id, step_names=steps_list)
        # Fetch session again to load relations
        session = repository.get_session(db, session.id)

    # Format steps
    steps = [
        StepResponseSchema(
            name=s.name,
            status=s.status,
            reason=s.reason,
            data=s.data
        ) for s in session.steps
    ]
    
    current_step, next_step = get_next_and_current_steps(session)
    
    return SessionResponse(
        session_id=session.id,
        type=session.type,
        raw_input=session.raw_input,
        current_step=current_step,
        next_step=next_step,
        steps=steps,
        artifacts=[],
        metrics=metrics_tracker.get_session_metrics(session.id),
        clarifying_question=clarifying_question
    )

@router.post("/sessions/{id}/step", response_model=SessionResponse)
async def process_session_step(id: str, payload: SessionStepRequest, db: Session = Depends(get_db)):
    """Submits the developer's inputs for the current step and executes the agent debate."""
    session = repository.get_session(db, id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {id} not found.")
        
    # If the session is currently UNCERTAIN, use developer response to resolve type
    if session.type == "UNCERTAIN":
        # Resolve type
        resolved = await classify_input(payload.user_input)
        if resolved["type"] == "UNCERTAIN":
            # Still uncertain, return question
            return SessionResponse(
                session_id=session.id,
                type=session.type,
                raw_input=session.raw_input,
                steps=[],
                artifacts=[],
                metrics=metrics_tracker.get_session_metrics(session.id),
                clarifying_question=resolved["question"]
            )
        else:
            # Set resolved type and add steps
            session = repository.update_session_type(db, session.id, resolved["type"], subtype=resolved.get("subtype"))
            steps_list = []
            if resolved["type"] == "BUG":
                steps_list = bug_workflow.get_step_names()
            elif resolved["type"] == "FEATURE":
                steps_list = feature_workflow.get_step_names()
            elif resolved["type"] == "MEETING/PLANNING":
                steps_list = meeting_workflow.get_step_names()
            
            repository.add_steps(db, session_id=session.id, step_names=steps_list)
            # Re-fetch session
            session = repository.get_session(db, session.id)
            
    # Run multi-agent debate
    debate_res = await execute_step_debate(session.id, payload.user_input)
    
    # Reload session state after debate modifications
    session = repository.get_session(db, id)
    
    steps = [
        StepResponseSchema(
            name=s.name,
            status=s.status,
            reason=s.reason,
            data=s.data
        ) for s in session.steps
    ]
    
    artifacts = [
        ArtifactResponseSchema(
            name=a.name,
            type=a.type,
            created_at=a.created_at.isoformat()
        ) for a in session.artifacts
    ]
    
    current_step, next_step = get_next_and_current_steps(session)
    
    return SessionResponse(
        session_id=session.id,
        type=session.type,
        raw_input=session.raw_input,
        current_step=current_step,
        next_step=next_step,
        steps=steps,
        artifacts=artifacts,
        metrics=metrics_tracker.get_session_metrics(session.id)
    )

@router.get("/sessions/{id}", response_model=SessionResponse)
def get_session_details(id: str, db: Session = Depends(get_db)):
    """Retrieves full session history, checklists, and outputs."""
    session = repository.get_session(db, id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {id} not found.")
        
    steps = [
        StepResponseSchema(
            name=s.name,
            status=s.status,
            reason=s.reason,
            data=s.data
        ) for s in session.steps
    ]
    
    artifacts = [
        ArtifactResponseSchema(
            name=a.name,
            type=a.type,
            created_at=a.created_at.isoformat()
        ) for a in session.artifacts
    ]
    
    current_step, next_step = get_next_and_current_steps(session)
    
    return SessionResponse(
        session_id=session.id,
        type=session.type,
        raw_input=session.raw_input,
        current_step=current_step,
        next_step=next_step,
        steps=steps,
        artifacts=artifacts,
        metrics=metrics_tracker.get_session_metrics(session.id)
    )
