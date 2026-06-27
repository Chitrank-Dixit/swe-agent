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
    assert "BDD / Acceptance Criteria" in names
    
    bdd_step = feature_workflow.get_step("BDD / Acceptance Criteria")
    assert bdd_step.is_critical is True

def test_meeting_workflow_checklist():
    assert len(meeting_workflow.steps) == 4
    names = meeting_workflow.get_step_names()
    assert "Prepare" in names
    
    decisions_step = meeting_workflow.get_step("Drive Decisions")
    assert decisions_step.is_critical is True

def test_config_timeout():
    from unittest.mock import patch
    from src.config.loader import DevCoachConfig
    # Default config without json file or env
    with patch("os.path.exists", return_value=False):
        c = DevCoachConfig()
        assert c.timeout == 600.0

    # Override via environment variable
    with patch("os.path.exists", return_value=False), \
         patch.dict("os.environ", {"LM_STUDIO_TIMEOUT": "120.0"}):
        c = DevCoachConfig()
        assert c.timeout == 120.0
