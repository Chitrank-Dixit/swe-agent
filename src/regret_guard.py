def check_regret_guard(session, step) -> list[str]:
    """Inspects session state and step metadata to verify critical workflow requirements.
    
    Returns a list of human-readable warnings when critical requirements are missing.
    """
    warnings = []
    
    # Check if BDD scenario artifact exists
    bdd_exists = any(art.type == "BDD_SCENARIO" for art in session.artifacts)
    # Check if TDD test skeleton exists
    tdd_exists = any(art.type == "TEST_SKELETON" for art in session.artifacts)
    # Check if Monitoring/observability plan exists
    obs_exists = any(art.type == "MONITORING_PLAN" for art in session.artifacts)
    
    step_name = step.name if hasattr(step, "name") else str(step)
    
    # 1. BDD Acceptance Criteria Check
    bdd_steps = ["BDD Scenario (where useful)", "BDD / Acceptance Criteria", "Validate & Close", "Verify Against Acceptance Criteria"]
    if step_name in bdd_steps or any(s.name in ["BDD Scenario (where useful)", "BDD / Acceptance Criteria"] and s.status in ("COMPLETED", "COMPLETED_WITH_WARNINGS") for s in session.steps):
        if not bdd_exists and session.type in ("BUG", "FEATURE"):
            is_bdd_step = step_name in ["BDD Scenario (where useful)", "BDD / Acceptance Criteria"]
            if is_bdd_step or any(s.name in ["BDD Scenario (where useful)", "BDD / Acceptance Criteria"] and s.status != "PENDING" for s in session.steps):
                warnings.append("BDD acceptance criteria missing")

    # 2. Observability Check
    obs_steps = ["Monitoring, Observability & Profiling", "Monitoring & Observability Plan", "Validate & Close", "Verify Against Acceptance Criteria"]
    if step_name in obs_steps or any(s.name in ["Monitoring, Observability & Profiling", "Monitoring & Observability Plan"] and s.status in ("COMPLETED", "COMPLETED_WITH_WARNINGS") for s in session.steps):
        is_obs_step = step_name in ["Monitoring, Observability & Profiling", "Monitoring & Observability Plan"]
        if not obs_exists and session.type in ("BUG", "FEATURE"):
            if is_obs_step or any(s.name in ["Monitoring, Observability & Profiling", "Monitoring & Observability Plan"] and s.status != "PENDING" for s in session.steps):
                warnings.append("Observability not considered for this feature")

    # 3. TDD Test Check
    tdd_steps = ["Write Failing TDD Test", "TDD Test Boundaries", "Implement Fix", "Implement in Slices", "Validate & Close", "Verify Against Acceptance Criteria"]
    if step_name in tdd_steps or any(s.name in ["Write Failing TDD Test", "TDD Test Boundaries"] and s.status in ("COMPLETED", "COMPLETED_WITH_WARNINGS") for s in session.steps):
        is_tdd_step = step_name in ["Write Failing TDD Test", "TDD Test Boundaries"]
        if not tdd_exists and session.type in ("BUG", "FEATURE"):
            if is_tdd_step or any(s.name in ["Write Failing TDD Test", "TDD Test Boundaries"] and s.status != "PENDING" for s in session.steps):
                warnings.append("Missing failing TDD test before implementation")
                
    return warnings
