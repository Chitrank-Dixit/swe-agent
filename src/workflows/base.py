from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class SessionType(str, Enum):
    BUG = "BUG"
    FEATURE = "FEATURE"
    MEETING = "MEETING/PLANNING"
    GENERAL_ENGINEERING_QUESTION = "GENERAL_ENGINEERING_QUESTION"
    UNCERTAIN = "UNCERTAIN"

class StepStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"

class WorkflowStep(BaseModel):
    name: str
    description: str
    is_critical: bool = False
    validation_guidelines: str

class BaseWorkflow(BaseModel):
    type: SessionType
    steps: List[WorkflowStep]

    def get_step_names(self) -> List[str]:
        return [s.name for s in self.steps]

    def get_step(self, name: str) -> Optional[WorkflowStep]:
        for step in self.steps:
            if step.name == name:
                return step
        return None
