# DevCoach (Software Engineering Workflow Coach)

DevCoach is a production-grade multi-agent coaching system designed to guide developers through rigorous software engineering workflows (TDD, BDD, monitoring, observability, and structured planning). The system takes free-text input, classifies the task, and orchestrates a team of specialized AI agents using FastAPI, local/remote LLMs (LM Studio/Qwen/OpenAI), and sequential structured output pipelines.

---

## Key Features

### 1. Sequential Structured Orchestration
Instead of passing full conversation logs between agents—which causes large prompts and cumulative latency—DevCoach parses and passes compact Pydantic objects between agents:
- **Coordinator** classifies task type and defines targets.
- **Workflow Coach** outlines steps and provides targeted instructions.
- **Test Strategy** produces BDD scenarios and test skeletons.
- **Skeptic Critic** audits proposed solutions for edge cases and safety.

### 2. Parallel Agent Execution & Skeptic Gating
- **Concurrent Runs**: Runs independent agents (e.g., Test Strategy and Skeptic Critic) in parallel using Python's `asyncio.gather`.
- **Stream Buffering**: Buffers streamed output tokens from concurrent tasks and plays them back sequentially to the user interface to ensure clear, non-interleaved console printing.
- **Skeptic Gating**: Bypasses the Skeptic Critic LLM agent entirely for trivial changes (e.g. documentation, comment updates, small line edits) to reduce response latency and token usage.

### 3. Persistent Interactive CLI (REPL)
- **Codex / Claude Code Style**: The interactive CLI session remains active after workflow steps or answers complete. Developers can continue typing follow-up questions or execute commands.
- **Slash Commands**: Rich in-session interactive commands are supported:
  - `/plan`: Switch session to Planning Mode (safety gate active, blocks modifications).
  - `/build`: Switch session to Build Mode (runs test suites and confirms file modifications).
  - `/status`: Render the current checklist status and metrics.
  - `/undo`: Revert the last completed step to PENDING.
  - `/skip`: Bypass the current step.
  - `/resume <session_id>`: Dynamically switch contexts and resume a past session.
  - `/quit` / `/exit` / `/q`: Terminate and exit the interactive loop.
- **Task Re-Classification**: Automatically detects if the developer switches task types (e.g. transitioning from a completed BUG workflow to starting a new FEATURE workflow) and adjusts the active checklist steps dynamically while preserving session context.

### 4. Direct Q&A Short-Circuit
General engineering queries containing code snippets or open questions skip the checklist workflow steps and are routed directly to the **General Engineering Advisor** for immediate feedback and stream responses.

---

## Architecture and Agents

The team consists of specialized agents orchestrating checks:
1. **CoordinatorAgent**: Entry point. Classifies input and routes dialogue.
2. **BugWorkflowCoach**: Leads BUG workflow steps.
3. **FeatureWorkflowCoach**: Leads FEATURE workflow steps.
4. **MeetingWorkflowCoach**: Leads MEETING workflow steps.
5. **TestStrategyAgent**: Generates pytest skeletons and BDD Gherkin scenarios.
6. **ObservabilityAgent**: Recommends logging schema, Prometheus metrics, and tracing setups.
7. **SkepticCriticAgent**: Constructively challenges decisions and checks edge cases.
8. **RegretGuardJudge**: Evaluates step completion, updates SQLite state, writes artifacts, and closes steps.

---

## Workflows

### 1. BUG Workflow
1. Capture & Clarify
2. Define Failing Behavior
3. BDD / Acceptance Scenario
4. Classify & Triage
5. Monitoring / Observability / Profiling *(Critical)*
6. Decide: Fix Now or Schedule
7. Write Failing TDD Test *(Critical)*
8. Implement Fix
9. Refactor Safely
10. Validate & Close *(Critical)*
11. Communicate Outcome

### 2. FEATURE Workflow
1. Understand Problem & Goals
2. Define BDD / Acceptance Criteria *(Critical)*
3. Shape & De-Scope
4. Plan Monitoring / Observability / Profiling *(Critical)*
5. Plan Implementation
6. Identify TDD Test Boundaries *(Critical)*
7. Implement in Vertical Slices with TDD
8. Verify Against Acceptance Criteria *(Critical)*
9. Launch & Document

### 3. MEETING / PLANNING Workflow
1. Review Agenda & Prepare
2. Participate & Drive Decisions *(Critical)*
3. Update Tickets & Notes *(Critical)*
4. Adjust Personal Plan

---

## Setup & Running

### Prerequisites
- Docker and Docker Compose installed.
- LM Studio or any OpenAI-compatible API running locally.

### Config in LM Studio
1. Open LM Studio.
2. Download a tool-calling supported model, such as `qwen2.5-coder-7b-instruct` or similar.
3. Start the Local Server (port `1234`).
4. **IMPORTANT**: In the server settings panel, make sure to change the binding address from `127.0.0.1` to `0.0.0.0` (all network interfaces). This is required so that Docker Compose containers can route traffic successfully to the host machine via `host.docker.internal`.
5. Ensure the system prompts and tool calling features are enabled.

> [!NOTE]
> The application uses a **5-second connection timeout** for LLM API calls. If the LM Studio server is offline or is binding only to localhost (preventing container connections), the client will time out after 5 seconds and automatically trigger local keyword-based heuristics to allow offline session testing.

---

### Run Application inside Docker Compose

We provide a `Makefile` to simplify all execution steps.

#### 1. Spin up the API Server
```bash
make up
```
This boots up the FastAPI container in detached mode, exposing the port at `http://localhost:8000`.

#### 2. Run the Interactive Coaching CLI
```bash
make run-cli
```
This boots up a containerized interactive coaching session right inside your terminal, letting you speak directly to the agent debate team.

#### 3. Resume an Existing Session
To resume a previous coaching session, use the `resume` command with the session ID:
```bash
make resume session=<session_id>
```
Or run directly via python:
```bash
python src/cli.py <session_id>
```
You can also dynamically switch to or resume another session mid-CLI by using the `/resume <session_id>` command in the input prompts.

#### 4. Run the Test Suites
```bash
make test
```
Runs the test suite inside the Docker container.

#### 5. Clean up Container Volumes & Caches
```bash
make clean
```
Stops the containers and wipes the SQLite database, logs, and caches cleanly.

---

## API Endpoints & Usage

### 1. Start a Session
**Endpoint**: `POST /api/sessions`  
**Payload**:
```json
{
  "raw_input": "We have a bug where the login endpoint returns 500 when the password has special characters like % or &."
}
```
**Response**:
```json
{
  "session_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "type": "BUG",
  "raw_input": "We have a bug where the login endpoint returns 500 when the password has special characters like % or &.",
  "current_step": "Capture & Clarify",
  "next_step": "Define Failing Behavior",
  "steps": [
    { "name": "Capture & Clarify", "status": "PENDING" },
    ...
  ],
  "artifacts": [],
  "metrics": {
    "session_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
    "elapsed_seconds": 0.5,
    "steps_completed": 0,
    "skipped_critical_steps": 0
  }
}
```

### 2. Complete a Step
Provide inputs for the current step. The AI agents will debate and update the state.
**Endpoint**: `POST /api/sessions/{id}/step`  
**Payload**:
```json
{
  "user_input": "The bug happens on macOS with python 3.11.2, main branch, version v2.1. The error occurs because the password URL parser fails when parsing raw % characters without escaping."
}
```

### 3. Check Session Status
**Endpoint**: `GET /api/sessions/{id}`  
Returns full session logs, status of checklist items, and links to created testing/monitoring artifacts.

---

## Multi-line Input Methods

By default, most terminal emulators send a standard carriage return (`\r`) when you press `Shift+Enter`. This causes the interactive CLI to immediately submit your input rather than inserting a newline.

To support developers in all environments, DevCoach supports three different methods to type multi-line inputs:

### Method 1: Backslash Line Continuation (No Configuration Needed)
End any line with a backslash (`\`) and press `Enter`. The CLI will automatically strip the backslash and open a newline for you to continue typing.
Example:
```
This is line 1 \
This is line 2 \
This is line 3
```

### Method 2: Alt+Enter / Escape + Enter (No Configuration Needed)
Press `Alt+Enter` (or press `Esc` then `Enter`) in your terminal to insert a newline.

### Method 3: Native Shift+Enter (Terminal/IDE Configuration Required)
Configure your terminal emulator to send a unique escape sequence when pressing `Shift+Enter`:

#### VS Code Integrated Terminal (Recommended)
Add the following keybinding to your `keybindings.json` file (Command Palette: `Preferences: Open Keyboard Shortcuts (JSON)`):
```json
{
    "key": "shift+enter",
    "command": "workbench.action.terminal.sendSequence",
    "args": { "text": "\u001b[13;2u" },
    "when": "terminalFocus"
}
```

#### iTerm2
1. Go to **Settings > Profiles > Keys**.
2. Click the **+** (plus) icon to add a new key binding.
3. In **Keyboard Shortcut**, press `Shift+Enter`.
4. In **Action**, select **Send Escape Sequence**.
5. In **Esc+**, type: `[13;2u`

#### Native macOS Terminal.app
1. Go to **Settings > Profiles > Keyboard**.
2. Click **+** to add a new key configuration.
3. Select Key: **Return**, Modifier: **Shift**.
4. Action: **Send Text**, and type `\x1b[13;2u` or map it using the escape character.
