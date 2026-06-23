from src.state import repository

def test_session_lifecycle(db_session):
    # 1. Create a session
    raw_input = "We need to fix the auth timeout."
    session = repository.create_session(db_session, raw_input=raw_input, session_type="BUG")
    assert session.id is not None
    assert session.type == "BUG"
    assert session.raw_input == raw_input

    # 2. Add steps
    steps = ["Step A", "Step B"]
    added_steps = repository.add_steps(db_session, session_id=session.id, step_names=steps)
    assert len(added_steps) == 2
    assert added_steps[0].name == "Step A"
    assert added_steps[0].status == "PENDING"

    # 3. Retrieve session
    fetched = repository.get_session(db_session, session.id)
    assert fetched is not None
    assert len(fetched.steps) == 2

    # 4. Update step status
    updated = repository.update_step_status(
        db_session,
        session_id=session.id,
        step_name="Step A",
        status="COMPLETED",
        data={"metrics_tracked": ["latency"]}
    )
    assert updated is not None
    assert updated.status == "COMPLETED"
    assert updated.data["metrics_tracked"] == ["latency"]

    # 5. Create and get artifacts
    artifact = repository.create_artifact(
        db_session,
        session_id=session.id,
        name="test_skeleton.py",
        artifact_type="TEST_SKELETON",
        content="def test_should_pass(): pass"
    )
    assert artifact.id is not None
    assert artifact.name == "test_skeleton.py"

    artifacts = repository.get_artifacts(db_session, session.id)
    assert len(artifacts) == 1
    assert artifacts[0].name == "test_skeleton.py"
