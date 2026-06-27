# Task Checklist: Parallel multi-agent execution & Skeptic Gating

- [x] Implement `should_invoke_skeptic` gating function in `src/agents/team.py`
  - [x] Extract touched files and lines changed from Coach output
  - [x] Determine if the fix is trivial based on keywords and size
  - [x] Implement gating conditions (estimated size > 20, BUG or FEATURE, not trivial)
- [x] Implement concurrent execution & token buffering in `src/agents/team.py`
  - [x] Create `run_agent_stream_buffered` to stream to local buffers
  - [x] Run Test Strategy and Skeptic Critic concurrently in `execute_step_debate` using `asyncio.gather`
  - [x] Play back token buffers sequentially to the callback function
  - [x] Handle merging outputs when Skeptic Critic is bypassed or active
- [x] Run & verify testing
  - [x] Create unit tests in `tests/unit/test_parallel_orchestration.py`
  - [x] Run all unit, integration, and BDD tests

# Phase 4 Checklist: Fix GENERAL_ENGINEERING_QUESTION workflow path
- [x] Orchestrator short-circuiting logic
  - [x] Add auto_execute database column alteration on startup in db.py and SessionModel definition
  - [x] Automatically set auto_execute = True for General Engineering Questions in create_session & update_session_type
  - [x] Short-circuit Address Question step using session.original_input directly as user input, bypassing interactive prompts
- [x] Suppress checklist UI for GENERAL session type
- [x] Clean completion message rules (show Answer complete vs No answer given based on step status, suppress Congratulations)
- [x] Guard skip commands with y/N warnings for GENERAL session Address Question steps
- [x] Update General Advisor system and default prompts to emphasize direct execution and format constraints
- [x] Write regression unit tests in tests/unit/test_general_question.py and verify correctness
