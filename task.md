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
# Phase 5 Checklist: Persistent Interactive Sessions
- [x] Implement exit commands (/quit, /exit, /q) at start of interactive_cli
- [x] Update completion and follow-up wait prompts when pending_step is None
- [x] Implement command dispatching and classification of new tasks inside the wait state
- [x] Reuse the same session_id and update workflow steps when task-switching or follow-ups occur
- [x] Create tests/unit/test_persistent_session.py to verify persistence, command exits, and session ID reuse
- [x] Verify unit, integration, and BDD test suites pass

# Phase 6 Checklist: Terminal UI (TUI) Upgrades
- [x] Refactor print_welcome_box to show slim header
- [x] Refactor print_prompt_bar to show slim header/status and helper hints
- [x] Refactor get_multiline_input to support bordered input box and continuation characters
- [x] Refactor print_boxed_response and integrate into debate summary output
- [x] Update persistent footers and all input capture loops in cli.py
- [x] Verify test suite passes successfully

# Phase 7 Checklist: Codex-style TUI Redesign
- [x] Refactor print_welcome_box to show Codex card
- [x] Refactor print_prompt_bar to omit hints line
- [x] Refactor print_boxed_response to output flat bullets and headings with no borders
- [x] Refactor get_multiline_input to print flat text and use › prefix without borders
- [x] Update handle_slash_command to print prompt bar status immediately on mode changes
- [x] Update startup and all input loops in cli.py
- [x] Verify test suite passes successfully

