import asyncio
import sys
import os
import re
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import ANSI
from src.state.db import init_db, SessionLocal
from src.state import repository
from src.agents.team import classify_input, execute_step_debate
from src.logging.logger import metrics_tracker
from src.workflows.bug import bug_workflow
from src.workflows.feature import feature_workflow
from src.workflows.meeting import meeting_workflow

# ---------------------------------------------------------------------------
# Register Shift+Enter escape sequences so prompt_toolkit can distinguish
# Shift+Enter from plain Enter.  This must happen BEFORE any PromptSession
# is created so the parser trie includes the new sequences.
#
# Kitty keyboard protocol  : \x1b[13;2u   (Kitty, Ghostty, WezTerm, iTerm2)
# xterm modifyOtherKeys    : \x1b[27;2;13~ (some xterm-compatible terminals)
#
# Terminals that already map Shift+Enter to ESC+CR (\x1b\r) are handled
# automatically via the ("escape", "enter") key binding below.
# ---------------------------------------------------------------------------
try:
    from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
    from prompt_toolkit.keys import Keys
    ANSI_SEQUENCES['\x1b[13;2u'] = Keys.ControlJ
    ANSI_SEQUENCES['\x1b[27;2;13~'] = Keys.ControlJ
except (ImportError, AttributeError):
    pass  # graceful fallback if prompt_toolkit internals change

# ANSI Colors for premium terminal UI
BOLD = "\033[1m"
UNDERLINE = "\033[4m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
GREY = "\033[90m"
WHITE = "\033[37m"
RESET = "\033[0m"

AGENT_COLORS = {
    "CoordinatorAgent": MAGENTA,
    "BugWorkflowCoach": CYAN,
    "FeatureWorkflowCoach": CYAN,
    "MeetingWorkflowCoach": CYAN,
    "TestStrategyAgent": BLUE,
    "ObservabilityAgent": GREEN,
    "SkepticCriticAgent": YELLOW,
    "RegretGuardJudge": RED,
    "System": GREY
}

def get_prettified_cwd() -> str:
    """Gets the current working directory, replacing the home prefix with ~ for cleaner display."""
    cwd = os.getcwd()
    home = os.path.expanduser("~")
    if cwd.startswith(home):
        cwd = cwd.replace(home, "~", 1)
    return cwd

def print_welcome_box():
    """Renders a Codex-style startup welcome box with dynamically padded interior space."""
    width = 58  # interior width
    prettified_cwd = get_prettified_cwd()
    
    lines = [
        f"{BOLD}{CYAN}>_ SWE Workflow Coach (v1.0.0){RESET}",
        "",
        f"{BOLD}model:{RESET}     {YELLOW}qwen/qwen3.5-9b{RESET}",
        f"{BOLD}directory:{RESET} {BLUE}{prettified_cwd}{RESET}"
    ]
    
    print(f"\n{GREY}┌" + "─" * (width + 2) + f"┐{RESET}")
    for line in lines:
        visible_len = len(re.sub(r'\033\[[0-9;]*m', '', line))
        padding = width - visible_len
        print(f"{GREY}│{RESET} {line}" + " " * padding + f" {GREY}│{RESET}")
    print(f"{GREY}└" + "─" * (width + 2) + f"┘{RESET}")

def print_prompt_bar(workflow_type: str, current_step: str = None):
    """Renders a Codex-style status/metadata bar directly preceding input prompt."""
    prettified_cwd = get_prettified_cwd()
    
    if workflow_type == "BUG":
        type_str = f"{RED}🔴 BUG{RESET}"
    elif workflow_type == "FEATURE":
        type_str = f"{GREEN}🟢 FEATURE{RESET}"
    elif workflow_type == "MEETING/PLANNING":
        type_str = f"{BLUE}🔵 MEETING/PLANNING{RESET}"
    else:
        type_str = f"{MAGENTA}🤖 SWE Coach{RESET}"
        
    step_str = f" · {BOLD}{CYAN}{current_step}{RESET}" if current_step else ""
    
    print(f"{BOLD}{type_str}{step_str} · {GREY}qwen/qwen3.5-9b · {prettified_cwd}{RESET}")

async def get_multiline_input(prompt_symbol: str = "> ") -> str:
    """Reads multiline input with a natural double-Enter-to-submit convention.

    Key bindings:
      Enter          → new line  (type naturally, paste code snippets)
      Enter on empty → submit    (press Enter twice when done)
      Ctrl+J         → force a blank line without submitting
      Ctrl+D         → submit immediately (standard EOF)
    """
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        buf = event.current_buffer
        # If the current line is empty and there's already content above,
        # treat this as "done" and submit the input.
        if buf.document.current_line_before_cursor == '' and buf.text.strip():
            buf.validate_and_handle()
        else:
            buf.insert_text('\n')

    @kb.add("c-j")
    def _(event):
        # Force-insert a blank line (bypass the submit check)
        event.current_buffer.insert_text('\n')

    @kb.add("c-d")
    def _(event):
        # Ctrl+D: submit immediately (standard EOF convention)
        buf = event.current_buffer
        if buf.text.strip():
            buf.validate_and_handle()

    prompt_text = f"{BOLD}{CYAN}{prompt_symbol}{RESET}"
    session = PromptSession(key_bindings=kb, multiline=True)
    try:
        user_input = await session.prompt_async(ANSI(prompt_text))
        return user_input.strip()
    except EOFError:
        return ""

async def spinner_task(message="Thinking"):
    """Displays a rotating spinner while waiting for background processing/streaming."""
    chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    idx = 0
    try:
        while True:
            sys.stdout.write(f"\r{BOLD}{YELLOW}{chars[idx]}{RESET} {message}...")
            sys.stdout.flush()
            idx = (idx + 1) % len(chars)
            await asyncio.sleep(0.08)
    except asyncio.CancelledError:
        pass

async def print_lines_gradually(lines: list, delay=0.1):
    """Prints a list of lines slowly one by one to create a smooth, premium typewriter flow."""
    for line in lines:
        print(line)
        await asyncio.sleep(delay)

async def print_workflow_checklist(session, current_step_name):
    """Renders a beautifully structured representation of the current workflow steps gradually."""
    lines = []
    lines.append(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════╗")
    lines.append(f"║ 📋 WORKFLOW PROGRESS CHECKLIST                           ║")
    lines.append(f"╚══════════════════════════════════════════════════════════╝{RESET}")
    for idx, step in enumerate(session.steps, 1):
        if step.name == current_step_name:
            lines.append(f"  {BOLD}{YELLOW}➡️  [PENDING]   {idx:02d}. {step.name}{RESET}")
        elif step.status == "COMPLETED":
            lines.append(f"  {GREEN}✔  [COMPLETED] {idx:02d}. {step.name}{RESET}")
        elif step.status == "SKIPPED":
            lines.append(f"  {GREY}✖  [SKIPPED]   {idx:02d}. {step.name} (Reason: {step.reason}){RESET}")
        else:
            lines.append(f"  {GREY}   [PENDING]   {idx:02d}. {step.name}{RESET}")
    lines.append(f"{GREY}────────────────────────────────────────────────────────────{RESET}\n")
    
    await print_lines_gradually(lines)

async def interactive_cli():
    """Starts an interactive command-line session for the Software Engineering Workflow Coach."""
    init_db()
    db = SessionLocal()
    
    # Render startup Codex welcome box
    print_welcome_box()
    print(f"{BOLD}Modes: Identify a {RED}BUG{RESET}{BOLD}, plan a {GREEN}FEATURE{RESET}{BOLD}, or capture {BLUE}MEETING/PLANNING{RESET}{BOLD} notes.{RESET}")
    print(f"{GREY}  ⌨  Enter = new line  |  Enter twice = submit  |  Ctrl+D = submit now{RESET}\n")
    
    # 1. Capture Raw Input
    print_prompt_bar("INITIAL")
    print(f"{BOLD}{WHITE}Describe your task (e.g., bug error details, feature idea, agenda):{RESET}")
    print(f"{GREY}  Enter = new line  |  Enter twice = submit{RESET}")
    raw_input = await get_multiline_input()
    if not raw_input:
        print(f"{BOLD}{RED}Task description cannot be empty. Exiting.{RESET}")
        return

    # 2. Perform Classification
    current_agent = [None]
    spinner = [None]
    
    def stop_spinner():
        if spinner[0]:
            spinner[0].cancel()
            spinner[0] = None
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

    def cli_token_callback(agent: str, token: str):
        stop_spinner()
        color = AGENT_COLORS.get(agent, CYAN)
        if current_agent[0] != agent:
            current_agent[0] = agent
            print(f"\n{BOLD}{color}💬 [{agent}]{RESET}: ", end="")
        print(token, end="")
        sys.stdout.flush()

    # Start spinner and run classification
    spinner[0] = asyncio.create_task(spinner_task("Classifying task category"))
    try:
        class_res = await classify_input(raw_input, on_token_callback=cli_token_callback)
    finally:
        stop_spinner()
    
    task_type = class_res["type"]
    clarifying_question = class_res["question"]
    task_subtype = class_res.get("subtype")
    
    # Handle uncertainty
    while task_type == "UNCERTAIN":
        print(f"\n{BOLD}{MAGENTA}💬 [CoordinatorAgent]{RESET}: {clarifying_question}")
        print_prompt_bar("INITIAL")
        answer = await get_multiline_input()
        current_agent[0] = None  # Reset current agent tracker for next query
        
        spinner[0] = asyncio.create_task(spinner_task("Analyzing clarifying response"))
        try:
            class_res = await classify_input(answer, on_token_callback=cli_token_callback)
        finally:
            stop_spinner()
            
        task_type = class_res["type"]
        clarifying_question = class_res["question"]
        task_subtype = class_res.get("subtype")
        
    print(f"\n\n{BOLD}{GREEN}✔ Resolved task workflow type: {task_type}{RESET}")
    if task_subtype:
        print(f"{BOLD}{CYAN}📂 Active playbook path: {task_subtype}{RESET}")
    
    # 3. Create Session in SQLite DB
    session = repository.create_session(db, raw_input=raw_input, session_type=task_type, subtype=task_subtype)
    metrics_tracker.start_session(session.id)
    
    # Add steps
    steps_list = []
    if task_type == "BUG":
        steps_list = bug_workflow.get_step_names()
    elif task_type == "FEATURE":
        steps_list = feature_workflow.get_step_names()
    elif task_type == "MEETING/PLANNING":
        steps_list = meeting_workflow.get_step_names()
        
    repository.add_steps(db, session_id=session.id, step_names=steps_list)
    
    print(f"{GREY}Session initialized with ID: {session.id}{RESET}")
    print(f"{BOLD}Total workflow steps to complete: {len(steps_list)}{RESET}")
    print(f"{GREY}────────────────────────────────────────────────────────────{RESET}")
    
    # 4. Interactive Step Progression Loop
    while True:
        db.expire_all()
        # Re-fetch session state
        session = repository.get_session(db, session.id)
        
        # Find next pending step
        pending_step = None
        for step in session.steps:
            if step.status == "PENDING":
                pending_step = step
                break
                
        if not pending_step:
            print("\n" + f"{BOLD}{GREEN}╔══════════════════════════════════════════════════════════╗")
            print(f"║ 🎉 CONGRATULATIONS! ALL WORKFLOW STEPS ARE COMPLETED.    ║")
            print(f"╚══════════════════════════════════════════════════════════╝{RESET}")
            metrics = metrics_tracker.get_session_metrics(session.id)
            print(f"🏆 {BOLD}Steps Completed: {metrics['steps_completed']}{RESET}")
            print(f"⚠️  {BOLD}Skipped Critical Steps: {metrics['skipped_critical_steps']}{RESET}")
            print(f"⏱️  {BOLD}Time Elapsed: {metrics['elapsed_seconds']} seconds{RESET}")
            break
            
        # Get step specification
        wf = None
        if task_type == "BUG":
            wf = bug_workflow
        elif task_type == "FEATURE":
            wf = feature_workflow
        else:
            wf = meeting_workflow
            
        step_spec = wf.get_step(pending_step.name)
        
        # Show matching playbook checklist and clarifying questions on first step
        if pending_step.name == "Capture & Clarify" and session.subtype:
            from src.workflows.playbooks import PLAYBOOKS
            matched_pb = None
            for pb in PLAYBOOKS.values():
                if pb.name == session.subtype:
                    matched_pb = pb
                    break
            if matched_pb:
                print(f"\n{BOLD}{YELLOW}🔥 ACTIVE TROUBLESHOOTING PLAYBOOK: {matched_pb.name.upper()}{RESET}")
                print(f"{GREY}────────────────────────────────────────────────────────────{RESET}")

                # 1. Checklist
                spinner[0] = asyncio.create_task(spinner_task("Analyzing immediate playbook checklist"))
                await asyncio.sleep(1.2)
                stop_spinner()
                checklist_lines = [f"### 📋 IMMEDIATE {matched_pb.name.upper()} PLAYBOOK CHECKLIST"]
                for item in matched_pb.checklist:
                    checklist_lines.append(f"- [ ] {item}")
                checklist_lines.append("")
                await print_lines_gradually(checklist_lines)

                # 2. Hypotheses
                spinner[0] = asyncio.create_task(spinner_task("Formulating prioritized hypotheses"))
                await asyncio.sleep(1.2)
                stop_spinner()
                hypotheses_lines = ["### 🔍 PRIORITIZED HYPOTHESES"]
                for idx, h in enumerate(matched_pb.hypotheses, 1):
                    hypotheses_lines.append(f"{idx}. {h}")
                hypotheses_lines.append("")
                await print_lines_gradually(hypotheses_lines)

                # 3. Tools
                spinner[0] = asyncio.create_task(spinner_task("Identifying recommended diagnostic tools"))
                await asyncio.sleep(1.2)
                stop_spinner()
                tools_lines = ["### 🛠️ RECOMMENDED DIAGNOSTIC TOOLS"]
                for tool in matched_pb.recommended_tools:
                    tools_lines.append(f"- {tool}")
                tools_lines.append("")
                await print_lines_gradually(tools_lines)

                # 4. Next steps
                spinner[0] = asyncio.create_task(spinner_task("Determining next diagnostic steps"))
                await asyncio.sleep(1.2)
                stop_spinner()
                steps_lines = ["### 👣 NEXT DIAGNOSTIC STEPS"]
                for idx, step in enumerate(matched_pb.diagnostic_steps, 1):
                    steps_lines.append(f"{idx}. {step}")
                steps_lines.append("")
                await print_lines_gradually(steps_lines)

                # 5. Clarifying questions
                spinner[0] = asyncio.create_task(spinner_task("Compiling high-value clarifying questions"))
                await asyncio.sleep(1.2)
                stop_spinner()
                questions_lines = ["### ❓ HIGH-VALUE CLARIFYING QUESTIONS"]
                for q in matched_pb.clarifying_questions:
                    questions_lines.append(f"- {q}")
                questions_lines.append("")
                await print_lines_gradually(questions_lines)
                
                print(f"{GREY}────────────────────────────────────────────────────────────{RESET}\n")

        # Render checklist progress with spinner
        spinner[0] = asyncio.create_task(spinner_task("Loading workflow progress checklist"))
        await asyncio.sleep(1.2)
        stop_spinner()
        await print_workflow_checklist(session, pending_step.name)

        print(f"{BOLD}{CYAN}>>> CURRENT STEP: {pending_step.name}{RESET}")
        print(f"{BOLD}Description: {step_spec.description}{RESET}")
        if step_spec.is_critical:
            print(f"⚠️  {BOLD}{RED}CRITICAL STEP: Cannot be skipped without providing a reason.{RESET}")
        
        # Codex-style formatted prompt
        print()
        print_prompt_bar(task_type, pending_step.name)
        print(f"{BOLD}{WHITE}Enter your inputs for this step (or type 'skip' to bypass):{RESET}")
        print(f"{GREY}  Enter = new line  |  Enter twice = submit{RESET}")
        user_input = await get_multiline_input()
        if not user_input:
            print(f"{RED}Input cannot be empty. Try again.{RESET}")
            continue
            
        # Execute debate loop with spinner
        current_agent[0] = None  # Reset current agent tracker for new debate session
        spinner[0] = asyncio.create_task(spinner_task("Initiating Agent debate & preparing checklist"))
        try:
            debate_res = await execute_step_debate(session.id, user_input, on_token_callback=cli_token_callback)
        finally:
            stop_spinner()
        
        summary_lines = [
            "\n" + f"{GREY}────────────────────────────────────────────────────────────{RESET}",
            f"{BOLD}{BLUE}📋 FINAL DEBATE SUMMARY ({pending_step.name}):{RESET}",
            f"{GREY}────────────────────────────────────────────────────────────{RESET}"
        ]
        status_color = GREEN if debate_res['status'] in ["COMPLETED", "SKIPPED"] else YELLOW
        summary_lines.append(f"⚖️  {BOLD}Decision Status: {status_color}{debate_res['status']}{RESET}")
        summary_lines.append(f"💬 {BOLD}Feedback: {RESET}{debate_res['feedback']}")
        summary_lines.append(f"{GREY}────────────────────────────────────────────────────────────{RESET}")
        
        await print_lines_gradually(summary_lines)
            
    db.close()

if __name__ == "__main__":
    try:
        asyncio.run(interactive_cli())
    except KeyboardInterrupt:
        print(f"\n{BOLD}{RED}CLI Coach session terminated by user.{RESET}")
        sys.exit(0)
