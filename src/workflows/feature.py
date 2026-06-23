from src.workflows.base import BaseWorkflow, WorkflowStep, SessionType

feature_workflow = BaseWorkflow(
    type=SessionType.FEATURE,
    steps=[
        WorkflowStep(
            name="Understand Problem & Goals",
            description="Clarify user problem, constraints, target audience, and success metrics.",
            is_critical=False,
            validation_guidelines="Verify that success metrics, constraints, and target audience are written down."
        ),
        WorkflowStep(
            name="Define BDD / Acceptance Criteria",
            description="Produce Gherkin-style Given/When/Then scenarios defining what is 'done'.",
            is_critical=True,
            validation_guidelines="Ensure that detailed Gherkin Given/When/Then BDD scenario files or artifacts are created."
        ),
        WorkflowStep(
            name="Shape & De-Scope",
            description="Propose the smallest valuable version (MVP) and list explicitly non-goals.",
            is_critical=False,
            validation_guidelines="Ensure there is an MVP outline and a list of descope/non-goals."
        ),
        WorkflowStep(
            name="Plan Monitoring / Observability / Profiling",
            description="Outline logging schema, custom metrics (SLAs/SLIs), tracing context, and potential profile bottlenecks.",
            is_critical=True,
            validation_guidelines="Verify that concrete metric names, log events, and trace-ids are structured in an artifact."
        ),
        WorkflowStep(
            name="Plan Implementation",
            description="Break the MVP into development tasks (backend, frontend, DB, infra, docs).",
            is_critical=False,
            validation_guidelines="Verify a breakdown of tasks with clear deliverables exists."
        ),
        WorkflowStep(
            name="Identify TDD Test Boundaries",
            description="Identify modules, classes, and edge cases to implement via strict Test-Driven Development.",
            is_critical=True,
            validation_guidelines="Ensure boundaries and specific pytest test skeleton names are identified and written."
        ),
        WorkflowStep(
            name="Implement in Vertical Slices with TDD",
            description="Develop component by component using Red-Green-Refactor loop.",
            is_critical=False,
            validation_guidelines="Verify that TDD code structure or skeleton implementations are produced."
        ),
        WorkflowStep(
            name="Verify Against Acceptance Criteria",
            description="Verify implementation against the BDD/acceptance scenarios.",
            is_critical=True,
            validation_guidelines="Confirm that code passes the BDD scenarios defined in step 2."
        ),
        WorkflowStep(
            name="Launch & Document",
            description="Outline release notes, internal architecture docs, and user docs.",
            is_critical=False,
            validation_guidelines="Verify drafts of release notes or docs are stored in the artifacts."
        )
    ]
)
