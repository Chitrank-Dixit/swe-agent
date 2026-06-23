from src.workflows.bug import bug_workflow
from src.workflows.feature import feature_workflow
from src.workflows.meeting import meeting_workflow

def test_bug_workflow_checklist():
    assert len(bug_workflow.steps) == 11
    names = bug_workflow.get_step_names()
    assert "Capture & Clarify" in names
    assert "Write Failing TDD Test" in names
    
    # Check critical steps
    tdd_step = bug_workflow.get_step("Write Failing TDD Test")
    assert tdd_step.is_critical is True
    
    clarify_step = bug_workflow.get_step("Capture & Clarify")
    assert clarify_step.is_critical is False

def test_feature_workflow_checklist():
    assert len(feature_workflow.steps) == 9
    names = feature_workflow.get_step_names()
    assert "Understand Problem & Goals" in names
    assert "Define BDD / Acceptance Criteria" in names
    
    bdd_step = feature_workflow.get_step("Define BDD / Acceptance Criteria")
    assert bdd_step.is_critical is True

def test_meeting_workflow_checklist():
    assert len(meeting_workflow.steps) == 4
    names = meeting_workflow.get_step_names()
    assert "Review Agenda & Prepare" in names
    
    decisions_step = meeting_workflow.get_step("Participate & Drive Decisions")
    assert decisions_step.is_critical is True
