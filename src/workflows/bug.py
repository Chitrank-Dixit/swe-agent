from src.workflows.base import BaseWorkflow, WorkflowStep, SessionType

bug_workflow = BaseWorkflow(
    type=SessionType.BUG,
    steps=[
        WorkflowStep(
            name="Capture & Clarify",
            description="Clarify observed vs expected behavior, environment details (OS, branch, version, dependencies).",
            is_critical=False,
            validation_guidelines="Ensure observed behavior, expected behavior, and environment details are documented."
        ),
        WorkflowStep(
            name="Define Failing Behavior",
            description="Express the bug as a precise failing behavior (e.g. system should do X but does Y when Z).",
            is_critical=False,
            validation_guidelines="Ensure there is a clear, concise statement of what fails under what condition."
        ),
        WorkflowStep(
            name="BDD Scenario (where useful)",
            description="Create Given/When/Then style scenario representing the bug from a user or system perspective.",
            is_critical=False,
            validation_guidelines="Check if a Gherkin-style Given/When/Then scenario was generated or provided."
        ),
        WorkflowStep(
            name="Classify & Triage",
            description="Assign severity (Critical, High, Medium, Low) and priority (P0, P1, P2) for fixing/scheduling.",
            is_critical=False,
            validation_guidelines="Ensure severity and priority are explicitly stated."
        ),
        WorkflowStep(
            name="Monitoring, Observability & Profiling",
            description="Suggest logs, metrics, traces, and profiling configurations to detect or prevent this bug in production.",
            is_critical=True,
            validation_guidelines="Verify that concrete observability recommendations (logs, metrics, traces) are documented."
        ),
        WorkflowStep(
            name="Decision Gate",
            description="Determine whether the bug needs immediate hotfixing or can be scheduled in the backlog.",
            is_critical=False,
            validation_guidelines="Verify a clear decision is reached ('Fix Now' or 'Schedule') with context."
        ),
        WorkflowStep(
            name="Write Failing TDD Test",
            description="Generate/write a candidate unit or integration test reproducing the bug (red test).",
            is_critical=True,
            validation_guidelines="Ensure a red pytest test skeleton is created and stored in the artifacts."
        ),
        WorkflowStep(
            name="Implement Fix",
            description="Guide the developer to implement the minimal fix required to make the failing test pass.",
            is_critical=False,
            validation_guidelines="Ensure a code fix is proposed or referenced."
        ),
        WorkflowStep(
            name="Refactor Safely",
            description="Clean up code and tests while keeping tests green.",
            is_critical=False,
            validation_guidelines="Verify that refactoring recommendations are made or acknowledged."
        ),
        WorkflowStep(
            name="Validate & Close",
            description="Verify behavior against original repro and acceptance scenarios, then close.",
            is_critical=True,
            validation_guidelines="Confirm that validation has been verified against the failing TDD test and BDD scenario."
        ),
        WorkflowStep(
            name="Communicate Outcome",
            description="Prepare a short summary of the fix to send to stakeholders (PR comments, Slack, Jira).",
            is_critical=False,
            validation_guidelines="Ensure a template or message draft for communication exists."
        )
    ]
)
