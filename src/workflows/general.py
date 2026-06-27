from src.workflows.base import BaseWorkflow, WorkflowStep, SessionType

general_workflow = BaseWorkflow(
    # Use standard string representation matching the enum value
    type=SessionType.GENERAL_ENGINEERING_QUESTION,
    steps=[
        WorkflowStep(
            name="Address Question",
            description="Provide a direct answer if the question is clear and narrow, or prompt for clarification if crucial context is missing.",
            is_critical=False,
            validation_guidelines="Verify that a clear, helpful response has been provided, and that clarifying questions are only asked when necessary."
        )
    ]
)
