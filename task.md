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
