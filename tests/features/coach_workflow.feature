Feature: Coaching Session Workflow
    Scenario: A developer starts a session for a new bug
        Given a developer has a description of a bug
        When the developer submits it to the coach
        Then a coaching session is created with the BUG workflow checklist
        And the current step is Capture & Clarify
