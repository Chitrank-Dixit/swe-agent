from src.workflows.base import BaseWorkflow, WorkflowStep, SessionType

meeting_workflow = BaseWorkflow(
    type=SessionType.MEETING,
    steps=[
        WorkflowStep(
            name="Prepare",
            description="Clarify agenda, meeting purpose, needed inputs, and desired outcomes.",
            is_critical=False,
            validation_guidelines="Ensure the meeting goals and agenda notes are documented."
        ),
        WorkflowStep(
            name="Drive Decisions",
            description="Actively participate and document decisions made, action item owners, and deadlines.",
            is_critical=True,
            validation_guidelines="Confirm decisions, owners, and deadlines are recorded in the data."
        ),
        WorkflowStep(
            name="Update Tickets",
            description="Translate the meeting decisions and action items into Jira tickets, GitHub issues, or tasks.",
            is_critical=True,
            validation_guidelines="Verify that concrete tasks/tickets with priority are drafted or updated."
        ),
        WorkflowStep(
            name="Adjust Plan",
            description="Re-prioritize own backlog and schedule based on new action items and meeting decisions.",
            is_critical=False,
            validation_guidelines="Ensure there is a stated plan of action for personal tasks."
        )
    ]
)
