from pydantic import BaseModel, Field
from typing import List, Literal

class CoordinatorOutput(BaseModel):
    workflow_type: Literal["BUG", "FEATURE", "MEETING", "GENERAL"]
    goal: str
    relevant_files: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    context_summary: str

class CoachOutput(BaseModel):
    step_name: str
    recommendations: str
    actions: List[str] = Field(default_factory=list)
    checks: List[str] = Field(default_factory=list)

class TestStrategyInput(BaseModel):
    __test__ = False
    workflow_type: str
    goal: str
    code_snippets: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)

class TestStrategyOutput(BaseModel):
    __test__ = False
    bdd_scenarios: List[str] = Field(default_factory=list)
    pytest_skeletons: List[str] = Field(default_factory=list)

class SkepticInput(BaseModel):
    goal: str
    summary_of_changes: str
    key_snippets: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)

class SkepticOutput(BaseModel):
    critique: str
    gaps: List[str] = Field(default_factory=list)
    challenges: List[str] = Field(default_factory=list)
