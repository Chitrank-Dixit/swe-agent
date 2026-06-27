import pytest
from src.observability import get_observability_suggestions
from src.regret_guard import check_regret_guard

class MockArtifact:
    def __init__(self, type_name):
        self.type = type_name

class MockStep:
    def __init__(self, name, status="PENDING"):
        self.name = name
        self.status = status

class MockSession:
    def __init__(self, type_name, steps, artifacts):
        self.type = type_name
        self.steps = steps
        self.artifacts = artifacts

def test_get_observability_suggestions_fastapi():
    # Test fastapi specific suggestions
    context = {
        "dependencies": ["fastapi", "uvicorn"],
        "raw_input": "Add a new avatar upload endpoint"
    }
    suggestions = get_observability_suggestions(context)
    assert any("FastAPI" in s or "X-Request-ID" in s for s in suggestions)
    # Check default suggestions are also present
    assert any("JSON" in s for s in suggestions)

def test_get_observability_suggestions_database():
    context = {
        "dependencies": ["sqlalchemy"],
        "raw_input": "We have a slow query in reports"
    }
    suggestions = get_observability_suggestions(context)
    assert any("Slow Query" in s or "EXPLAIN ANALYZE" in s for s in suggestions)

def test_get_observability_suggestions_async():
    context = {
        "dependencies": [],
        "raw_input": "Optimize concurrent requests using asyncio"
    }
    suggestions = get_observability_suggestions(context)
    assert any("asyncio" in s or "ThreadPoolExecutor" in s for s in suggestions)

def test_check_regret_guard_no_warnings():
    # Setup session with all required artifacts
    steps = [
        MockStep("BDD / Acceptance Criteria", "COMPLETED"),
        MockStep("Monitoring & Observability Plan", "COMPLETED"),
        MockStep("TDD Test Boundaries", "COMPLETED"),
        MockStep("Verify Against Acceptance Criteria", "PENDING")
    ]
    artifacts = [
        MockArtifact("BDD_SCENARIO"),
        MockArtifact("MONITORING_PLAN"),
        MockArtifact("TEST_SKELETON")
    ]
    session = MockSession("FEATURE", steps, artifacts)
    
    # Check "Verify Against Acceptance Criteria" step
    warnings = check_regret_guard(session, steps[3])
    assert len(warnings) == 0

def test_check_regret_guard_missing_bdd():
    steps = [
        MockStep("BDD / Acceptance Criteria", "PENDING"),
        MockStep("Monitoring & Observability Plan", "PENDING"),
        MockStep("TDD Test Boundaries", "PENDING")
    ]
    # No BDD scenario artifact
    artifacts = []
    session = MockSession("FEATURE", steps, artifacts)
    
    warnings = check_regret_guard(session, steps[0])
    assert "BDD acceptance criteria missing" in warnings

def test_check_regret_guard_missing_observability():
    steps = [
        MockStep("BDD / Acceptance Criteria", "COMPLETED"),
        MockStep("Monitoring & Observability Plan", "PENDING")
    ]
    # BDD scenario exists, but no monitoring plan
    artifacts = [MockArtifact("BDD_SCENARIO")]
    session = MockSession("FEATURE", steps, artifacts)
    
    warnings = check_regret_guard(session, steps[1])
    assert "Observability not considered for this feature" in warnings
    assert "BDD acceptance criteria missing" not in warnings

def test_check_regret_guard_missing_tdd():
    steps = [
        MockStep("BDD / Acceptance Criteria", "COMPLETED"),
        MockStep("Monitoring & Observability Plan", "COMPLETED"),
        MockStep("TDD Test Boundaries", "PENDING")
    ]
    # BDD and monitoring exist, but no test skeleton
    artifacts = [MockArtifact("BDD_SCENARIO"), MockArtifact("MONITORING_PLAN")]
    session = MockSession("FEATURE", steps, artifacts)
    
    warnings = check_regret_guard(session, steps[2])
    assert "Missing failing TDD test before implementation" in warnings
