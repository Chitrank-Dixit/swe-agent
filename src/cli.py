import asyncio
import sys
import os
from typing import Optional, List
import re
import glob
import subprocess
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import ANSI
from src.state.db import init_db, SessionLocal
from src.state import repository
from src.agents.team import classify_input, execute_step_debate
from src.agents.tools import undo_last_edit
from src.logging.logger import metrics_tracker
from src.workflows.bug import bug_workflow
from src.workflows.feature import feature_workflow
from src.workflows.meeting import meeting_workflow
from src.workflows.general import general_workflow

# Try to register custom Shift+Enter mappings
try:
    from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
    from prompt_toolkit.keys import Keys
    ANSI_SEQUENCES['\x1b[13;2u'] = Keys.F19      # Kitty keyboard protocol Shift+Enter
    ANSI_SEQUENCES['\x1b[27;2;13~'] = Keys.F20    # modifyOtherKeys Shift+Enter
    ANSI_SEQUENCES['\x1b[13;2~'] = Keys.F23       # Alternate Shift+Enter sequence
    ANSI_SEQUENCES['\x1b[13;5u'] = Keys.F21      # Kitty keyboard protocol Ctrl+Enter
    ANSI_SEQUENCES['\x1b[27;5;13~'] = Keys.F22    # modifyOtherKeys Ctrl+Enter
except (ImportError, AttributeError):
    pass

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
    "GeneralEngineeringAdvisor": CYAN,
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
    """Renders a Codex-style startup welcome header card with a clean outline box."""
    from src.config.loader import config
    prettified_cwd = get_prettified_cwd()
    model = config.default_model or "qwen3.5-9b"
    
    lines = [
        f"{BOLD}{CYAN}>_ DevCoach (v1.0.0){RESET}",
        "",
        f"{BOLD}model:{RESET}     {YELLOW}{model}{RESET}     {GREY}/model to change{RESET}",
        f"{BOLD}directory:{RESET} {BLUE}{prettified_cwd}{RESET}"
    ]
    
    # Calculate visible lengths of each line to find the maximum width
    visible_lengths = [len(re.sub(r'\033\[[0-9;]*m', '', line)) for line in lines]
    max_len = max(visible_lengths)
    width = max_len + 2
    
    print(f"\n{GREY}┌" + "─" * (width) + f"┐{RESET}")
    for line in lines:
        visible_len = len(re.sub(r'\033\[[0-9;]*m', '', line))
        padding = width - visible_len - 1
        if padding < 0:
            padding = 0
        print(f"{GREY}│{RESET} {line}" + " " * padding + f"{GREY}│{RESET}")
    print(f"{GREY}└" + "─" * (width) + f"┘{RESET}\n")

def print_prompt_bar(session_or_type, current_step: str = None):
    """Renders a slimmer single-line header and status bar, with no hints."""
    from src.config.loader import config
    prettified_cwd = get_prettified_cwd()
    
    active_mode = "PLAN"
    if hasattr(session_or_type, "active_mode"):
        active_mode = session_or_type.active_mode
        wf_type = session_or_type.type
    else:
        wf_type = str(session_or_type)
        
    mode_indicator = f"{YELLOW}PLAN{RESET}" if active_mode == "PLAN" else f"{GREEN}BUILD{RESET}"
    model = config.default_model or "qwen3.5-9b"
    
    header_str = f"{BOLD}{CYAN}DevCoach v1.0.0{RESET}  {GREY}│{RESET}  {BOLD}Mode: {mode_indicator}{RESET}  {GREY}│{RESET}  {BOLD}Model: {model}{RESET}  {GREY}│{RESET}  {BOLD}Dir: {prettified_cwd}{RESET}"
    if current_step:
        header_str += f"  {GREY}│{RESET}  {BOLD}{CYAN}Step: {current_step}{RESET}"
        
    print(f"\n{header_str}")
    print(f"{GREY}───────────────────────────────────────────────────────────────────────────────{RESET}")

def print_boxed_response(title: str, text: str):
    """Renders response as flat card text with indentation and bullets instead of borders."""
    print(f"\n{BOLD}{CYAN}# {title}{RESET}")
    print(f"{GREY}───────────────────────────────────────────────────────────────────────────────{RESET}\n")
    
    lines = text.split("\n")
    for line in lines:
        stripped = line.strip()
        if not stripped:
            print()
            continue
            
        # Parse markdown headings/sections
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            # Strip emojis
            heading = re.sub(r'[\u2600-\u27BF]|[\u1F300-\u1F9FF]|[\u1F600-\u1F64F]|[\u1F680-\u1F6FF]', '', heading).strip()
            print(f"{BOLD}{WHITE}{heading.upper()}:{RESET}")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            content = stripped[2:].strip()
            print(f"  • {content}")
        elif stripped.startswith("↳"):
            print(f"    {stripped}")
        else:
            print(f"  {line}")
    print()

async def get_multiline_input(prompt_symbol: str = "› ", prompt_text: str = None) -> str:
    """Reads multiline input, presenting it cleanly without boxes."""
    if prompt_text:
        print(f"{BOLD}{WHITE}{prompt_text}{RESET}")
        
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        buf = event.current_buffer
        current_line = buf.document.current_line_before_cursor
        if current_line.rstrip(' ').endswith('\\'):
            stripped = current_line.rstrip(' ')
            to_delete = len(current_line) - len(stripped) + 1
            buf.delete_before_cursor(to_delete)
            buf.insert_text('\n')
        else:
            buf.validate_and_handle()

    @kb.add("f19")
    @kb.add("f20")
    @kb.add("f21")
    @kb.add("f22")
    @kb.add("f23")
    def _(event):
        event.current_buffer.insert_text('\n')

    @kb.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text('\n')

    @kb.add("c-d")
    def _(event):
        buf = event.current_buffer
        if buf.text.strip():
            buf.validate_and_handle()

    prompt_text_formatted = f"{BOLD}{CYAN}{prompt_symbol}{RESET}"
    session = PromptSession(
        key_bindings=kb, 
        multiline=True,
        prompt_continuation=lambda width, line_number, wrap_around: "  "
    )
    try:
        user_input = await session.prompt_async(ANSI(prompt_text_formatted))
        print()
        return user_input.strip()
    except EOFError:
        return ""

async def spinner_task(message="Thinking"):
    """Displays a rotating spinner while waiting for background processing/streaming."""
    chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    idx = 0
    try:
        while True:
            if isinstance(message, dict):
                msg = message.get("message", "Processing")
            else:
                msg = message
            sys.stdout.write(f"\r{BOLD}{YELLOW}{chars[idx]}{RESET} {msg}...")
            sys.stdout.flush()
            idx = (idx + 1) % len(chars)
            await asyncio.sleep(0.08)
    except asyncio.CancelledError:
        pass

async def print_lines_gradually(lines: list, delay=0.1):
    """Prints a list of lines slowly one by one to create a smooth typewriter flow."""
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
        elif step.status == "COMPLETED_WITH_WARNINGS":
            lines.append(f"  {YELLOW}⚠  [COMPLETED WITH WARNINGS] {idx:02d}. {step.name}{RESET}")
        elif step.status == "SKIPPED":
            lines.append(f"  {GREY}✖  [SKIPPED]   {idx:02d}. {step.name} (Reason: {step.reason}){RESET}")
        else:
            lines.append(f"  {GREY}   [PENDING]   {idx:02d}. {step.name}{RESET}")
    lines.append(f"{GREY}────────────────────────────────────────────────────────────{RESET}\n")
    await print_lines_gradually(lines)

def get_workflow_steps_list(wf_type: str) -> list[str]:
    if wf_type == "BUG":
        return bug_workflow.get_step_names()
    elif wf_type == "FEATURE":
        return feature_workflow.get_step_names()
    elif wf_type in ("MEETING/PLANNING", "MEETING"):
        return meeting_workflow.get_step_names()
    elif wf_type == "GENERAL_ENGINEERING_QUESTION":
        return general_workflow.get_step_names()
    return []

def get_workflow_by_type(wf_type: str):
    if wf_type == "BUG":
        return bug_workflow
    elif wf_type == "FEATURE":
        return feature_workflow
    elif wf_type in ("MEETING/PLANNING", "MEETING"):
        return meeting_workflow
    elif wf_type == "GENERAL_ENGINEERING_QUESTION":
        return general_workflow
    return None

def print_session_status(session):
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════╗")
    print(f"║ 📋 SESSION STATE & STATUS                                ║")
    print(f"╚══════════════════════════════════════════════════════════╝{RESET}")
    print(f"  {BOLD}Session ID:{RESET}      {session.id}")
    print(f"  {BOLD}Workflow:{RESET}        {session.type}")
    print(f"  {BOLD}Active Mode:{RESET}     {session.active_mode}")
    
    pending_step = None
    completed_steps = []
    skipped_steps = []
    
    for step in session.steps:
        if step.status == "PENDING" and not pending_step:
            pending_step = step.name
        elif step.status in ("COMPLETED", "COMPLETED_WITH_WARNINGS"):
            suffix = " (with warnings)" if step.status == "COMPLETED_WITH_WARNINGS" else ""
            completed_steps.append(f"{step.name}{suffix}")
        elif step.status == "SKIPPED":
            skipped_steps.append(f"{step.name} (Reason: {step.reason})")
            
    print(f"  {BOLD}Current Step:{RESET}    {pending_step or 'None (All Completed)'}")
    print(f"  {BOLD}Completed:{RESET}       {', '.join(completed_steps) if completed_steps else 'None'}")
    print(f"  {BOLD}Skipped:{RESET}         {', '.join(skipped_steps) if skipped_steps else 'None'}")
    print(f"{GREY}────────────────────────────────────────────────────────────{RESET}\n")

def print_active_agents(wf_type: str):
    print(f"\n{BOLD}{CYAN}╔══════════════════════════════════════════════════════════╗")
    print(f"║ 🤖 ACTIVE AGENTS & ROLES                                 ║")
    print(f"╚══════════════════════════════════════════════════════════╝{RESET}")
    
    agents = [
        ("CoordinatorAgent", "Moderator, routes input and manages turns"),
        ("SkepticCriticAgent", "Challenges assumptions, checks edge cases"),
        ("RegretGuardJudge", "Enforces checklists, validates/updates DB state"),
    ]
    
    if wf_type == "BUG":
        agents.append(("BugWorkflowCoach", "Guides bug investigation and resolution"))
        agents.extend([
            ("TestStrategyAgent", "Generates TDD test skeletons and BDD scenarios"),
            ("ObservabilityAgent", "Advises on metrics, logging and profiling")
        ])
    elif wf_type == "FEATURE":
        agents.append(("FeatureWorkflowCoach", "Guides feature MVP planning and implementation"))
        agents.extend([
            ("TestStrategyAgent", "Generates TDD test skeletons and BDD scenarios"),
            ("ObservabilityAgent", "Advises on metrics, logging and profiling")
        ])
    elif wf_type in ("MEETING/PLANNING", "MEETING"):
        agents.append(("MeetingWorkflowCoach", "Guides meeting agenda prep and action-item updates"))
    elif wf_type == "GENERAL_ENGINEERING_QUESTION":
        agents.append(("GeneralEngineeringAdvisor", "Answers direct engineering/coding questions"))
        
    for idx, (name, role) in enumerate(agents, 1):
        print(f"  {idx}. {BOLD}{AGENT_COLORS.get(name, WHITE)}{name}{RESET}: {role}")
    print(f"{GREY}────────────────────────────────────────────────────────────{RESET}\n")

async def handle_slash_command(user_input: str, session_id: str, db) -> tuple[bool, Optional[str]]:
    """Handles slash commands. Returns (is_command, next_action)."""
    parts = user_input.strip().split(maxsplit=2)
    cmd = parts[0].lower()
    
    session = repository.get_session(db, session_id)
    if not session:
        return False, None

    if cmd in ("/quit", "/exit", "/q"):
        print(f"\n{BOLD}{GREEN}👋 Goodbye!{RESET}\n")
        return True, "exit"

    elif cmd == "/plan":
        repository.update_session_mode(db, session_id, "PLAN")
        session = repository.get_session(db, session_id)
        print_prompt_bar(session)
        return True, "continue"
        
    elif cmd == "/build":
        repository.update_session_mode(db, session_id, "BUILD")
        session = repository.get_session(db, session_id)
        print_prompt_bar(session)
        return True, "continue"
        
    elif cmd in ("/bug", "/feature", "/meeting", "/ask"):
        mapping = {
            "/bug": "BUG",
            "/feature": "FEATURE",
            "/meeting": "MEETING/PLANNING",
            "/ask": "GENERAL_ENGINEERING_QUESTION"
        }
        target_type = mapping[cmd]
        print(f"\n{BOLD}{CYAN}Switching workflow to {target_type}...{RESET}\n")
        return True, f"new_session:{target_type}"
        
    elif cmd == "/undo":
        success = undo_last_edit()
        if success:
            print(f"\n{BOLD}{GREEN}Reverted last file edit successfully!{RESET}\n")
        else:
            print(f"\n{BOLD}{RED}No previous file edits found to revert.{RESET}\n")
        return True, "continue"
        
    elif cmd == "/status":
        print_session_status(session)
        return True, "continue"
        
    elif cmd == "/skip":
        step_name = None
        reason = "Skipped via slash command"
        
        pending_step = None
        for step in session.steps:
            if step.status == "PENDING":
                pending_step = step
                break
                
        if len(parts) > 1:
            arg_text = parts[1]
            if len(parts) > 2:
                arg_text += " " + parts[2]
                
            matched_step = None
            for s in session.steps:
                if arg_text.lower().startswith(s.name.lower()):
                    matched_step = s
                    reason = arg_text[len(s.name):].strip(" :;,-").strip()
                    break
            
            if matched_step:
                step_name = matched_step.name
            else:
                step_name = pending_step.name if pending_step else None
                reason = arg_text
        else:
            step_name = pending_step.name if pending_step else None
            
        if not step_name:
            print(f"\n{BOLD}{RED}No pending step to skip.{RESET}\n")
            return True, "continue"
            
        if step_name == "Address Question":
            confirm = input(f"{BOLD}{YELLOW}⚠️ Skipping this step will close the session without an answer. Continue? (y/N){RESET}").strip().lower()
            if confirm != "y":
                print(f"\n{BOLD}{GREEN}Skip cancelled. Returning to the step.{RESET}\n")
                return True, "continue"
                
        wf = get_workflow_by_type(session.type)
        step_spec = wf.get_step(step_name) if wf else None
        is_critical = step_spec.is_critical if step_spec else False
        
        if is_critical and (not reason or reason == "Skipped via slash command"):
            print(f"\n{BOLD}{RED}Step '{step_name}' is critical. You must provide a reason: /skip [step] [reason]{RESET}\n")
            return True, "continue"
            
        repository.update_step_status(db, session_id, step_name, "SKIPPED", reason=reason)
        if is_critical:
            metrics_tracker.record_critical_step_skipped(session_id)
        print(f"\n{BOLD}{YELLOW}Skipped step '{step_name}'. Reason: {reason}{RESET}\n")
        return True, "continue"
        
    elif cmd == "/agents":
        print_active_agents(session.type)
        return True, "continue"
        
    elif cmd == "/model":
        from src.config.loader import config
        if len(parts) > 1:
            new_model = parts[1]
            config.default_model = new_model
            config.judge_model = new_model
            print(f"\n{BOLD}{GREEN}Model switched to: {new_model}{RESET}\n")
        else:
            print(f"\n{BOLD}Current default model: {YELLOW}{config.default_model}{RESET}")
            print(f"{BOLD}Current judge model:   {YELLOW}{config.judge_model}{RESET}\n")
        return True, "continue"
        
    return False, None

def scan_repository() -> dict:
    """Scans repository structure to discover languages, test frameworks, CI configurations, and dependencies."""
    languages = set()
    test_framework = "Unknown"
    ci_config = "None"
    dependencies = []
    
    file_extensions = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".go": "Go",
        ".rs": "Rust",
        ".java": "Java",
        ".cpp": "C++",
        ".c": "C",
        ".rb": "Ruby",
        ".php": "PHP"
    }
    
    for root, dirs, files in os.walk("."):
        if any(ignored in root for ignored in [".venv", "venv", "env", ".git", "node_modules", "__pycache__", ".pytest_cache"]):
            continue
        for file in files:
            _, ext = os.path.splitext(file)
            if ext in file_extensions:
                languages.add(file_extensions[ext])
                
    if os.path.exists("pyproject.toml"):
        dependencies.append("pyproject.toml")
        try:
            with open("pyproject.toml", "r", encoding="utf-8") as f:
                content = f.read()
                if "pytest" in content:
                    test_framework = "pytest (Python)"
                elif "unittest" in content:
                    test_framework = "unittest (Python)"
        except Exception:
            pass
            
    if os.path.exists("requirements.txt"):
        dependencies.append("requirements.txt")
        try:
            with open("requirements.txt", "r", encoding="utf-8") as f:
                content = f.read()
                if "pytest" in content:
                    test_framework = "pytest (Python)"
        except Exception:
            pass
            
    if os.path.exists("package.json"):
        dependencies.append("package.json")
        try:
            with open("package.json", "r", encoding="utf-8") as f:
                content = f.read()
                if "jest" in content:
                    test_framework = "jest (JavaScript)"
                elif "mocha" in content:
                    test_framework = "mocha (JavaScript)"
        except Exception:
            pass

    if os.path.exists(".github/workflows"):
        ci_config = "GitHub Actions"
    elif os.path.exists(".gitlab-ci.yml"):
        ci_config = "GitLab CI"
        
    return {
        "languages": list(languages) or ["Python (Default)"],
        "test_framework": test_framework,
        "ci_config": ci_config,
        "dependencies": dependencies
    }

def generate_agents_md(scan_data: dict) -> str:
    """Generates the initial AGENTS.md content based on repository scan data."""
    languages_str = ", ".join(scan_data["languages"])
    deps_str = ", ".join(scan_data["dependencies"]) if scan_data["dependencies"] else "None found"
    
    return f"""# Agent Architecture & Instructions System

This document outlines the global rules, orchestration policies, and agent specifications for DevCoach.

## Project Description
A dynamic software project utilizing {languages_str}.
- **Detected Main Dependencies**: {deps_str}

## Architecture Overview
- **Orchestration**: AutoGen-based multi-agent group chat debate engine.
- **Workflow State**: SQLite-backed session persistence.

## Coding Conventions
- Ensure clean, idiomatic code adhering to best practices in {languages_str}.
- Adhere to clean coding principles, descriptive naming, and separation of concerns.

## Preferred Test Approach
- **Test Framework**: {scan_data["test_framework"]}
- **Methodology**: Strict Test-Driven Development (TDD) and Behavior-Driven Development (BDD/ATDD).
- Write failing unit/integration tests before writing production code.

## Logging & Observability Norms
- Implement structured JSON logging formats.
- Instrument latency tracing and track critical SLA/SLI metrics.

## Workflow Expectations
- Follow the plan-build architecture strictly.
- Propose plans in PLAN mode; execute destructive file and test runs in BUILD mode.
"""

def init_repository():
    """Implements 'devcoach init' logic."""
    print(f"\n{BOLD}{CYAN}🔍 Scanning repository structure...{RESET}")
    scan_data = scan_repository()
    
    agents_md_path = "AGENTS.md"
    if os.path.exists(agents_md_path):
        print(f"{BOLD}{YELLOW}⚠️  AGENTS.md already exists in this repository.{RESET}")
        confirm = input(f"{BOLD}{WHITE}Do you want to overwrite it with auto-generated defaults? (y/n): {RESET}").strip().lower()
        if confirm != 'y':
            print(f"\n{BOLD}{GREEN}Initialization skipped. Please review/edit your existing AGENTS.md before running.{RESET}\n")
            return
            
    content = generate_agents_md(scan_data)
    with open(agents_md_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"\n{BOLD}{GREEN}✔ Successfully generated AGENTS.md!{RESET}")
    print(f"{GREY}Path: {os.path.abspath(agents_md_path)}{RESET}")
    print(f"\n{BOLD}{YELLOW}IMPORTANT: Please review and edit AGENTS.md to match your project conventions before starting your first session.{RESET}\n")

async def interactive_cli():
    """Starts an interactive command-line session for the Software Engineering Workflow Coach."""
    # Ensure AGENTS.md exists
    if not os.path.exists("AGENTS.md"):
        print(f"\n{BOLD}{RED}⚠️  AGENTS.md is missing in this repository!{RESET}")
        print(f"{BOLD}Please run {YELLOW}devcoach init{RESET}{BOLD} first to initialize the coach configuration.{RESET}\n")
        return
        
    init_db()
    db = SessionLocal()
    
    # Reload AGENTS.md rules
    from src.config.loader import config
    config.load_agents_rules()
    
    # Render startup welcome box
    print_welcome_box()
    print(f"{BOLD}{WHITE}Tip: You can describe a {RED}BUG{RESET}{BOLD}{WHITE}, {GREEN}FEATURE{RESET}{BOLD}{WHITE}, {BLUE}MEETING{RESET}{BOLD}{WHITE}, or {YELLOW}GENERAL QUESTION{RESET}{BOLD}{WHITE} in natural language.{RESET}")
    print(f"{GREY}Hints: Enter=send  ·  Alt+Enter=new line  ·  /help for commands{RESET}\n")
    
    # 1. Capture Raw Input
    raw_input = await get_multiline_input(prompt_symbol="› ", prompt_text="Describe your task (bug, feature, meeting, question):")
    if not raw_input:
        print(f"{BOLD}{RED}Task description cannot be empty. Exiting.{RESET}")
        return

    # Handle slash commands on first input
    if raw_input.strip().lower() in ("/quit", "/exit", "/q"):
        print(f"\n{BOLD}{GREEN}👋 Goodbye!{RESET}\n")
        db.close()
        return
    elif raw_input.startswith("/"):
        print(f"{BOLD}{RED}Slash commands cannot be executed as the initial task description.{RESET}")
        return

    # 2. Perform Classification
    current_agent = [None]
    spinner = [None]
    spinner_state = {"message": "Processing"}
    
    def stop_spinner():
        if spinner[0]:
            spinner[0].cancel()
            spinner[0] = None
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

    def cli_token_callback(agent: str, token: str):
        spinner_state["message"] = f"[{agent}] is processing"

    # Start spinner and run classification
    spinner_state["message"] = "Classifying task category"
    spinner[0] = asyncio.create_task(spinner_task(spinner_state))
    try:
        class_res = await classify_input(raw_input, on_token_callback=cli_token_callback)
    finally:
        stop_spinner()
    
    task_type = class_res["type"]
    clarifying_question = class_res["question"]
    task_subtype = class_res.get("subtype")
    
    # Handle uncertainty
    while task_type == "UNCERTAIN":
        print(f"\n{BOLD}{MAGENTA}💬 [CoordinatorAgent]{RESET}: {clarifying_question}\n")
        answer = await get_multiline_input(prompt_text="Provide clarifying details:")
        current_agent[0] = None
        
        spinner_state["message"] = "Analyzing clarifying response"
        spinner[0] = asyncio.create_task(spinner_task(spinner_state))
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
    session = repository.create_session(db, raw_input=raw_input, session_type=task_type, subtype=task_subtype, active_mode="PLAN")
    metrics_tracker.start_session(session.id)
    
    # Add steps
    steps_list = get_workflow_steps_list(task_type)
    repository.add_steps(db, session_id=session.id, step_names=steps_list)
    
    print(f"{GREY}Session initialized with ID: {session.id}{RESET}")
    print(f"{BOLD}Total workflow steps to complete: {len(steps_list)}{RESET}")
    print(f"{GREY}────────────────────────────────────────────────────────────{RESET}")
    
    # 4. Interactive Step Progression Loop
    is_first_general_run = True
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
            if session.type == "GENERAL_ENGINEERING_QUESTION":
                address_step = next((s for s in session.steps if s.name == "Address Question"), None)
                if address_step and address_step.status == "SKIPPED":
                    print(f"\n{BOLD}{YELLOW}⚠️ Session closed. No answer was given.{RESET}\n")
                else:
                    print(f"\n{BOLD}{GREEN}✅ Answer complete.{RESET}\n")
            else:
                print(f"\n{BOLD}{GREEN}✅ Workflow complete.{RESET}\n")
            
            print(f"{BOLD}{CYAN}Ready for next input…  {RESET}{GREY}(/quit to exit){RESET}")
            follow_up_input = await get_multiline_input(prompt_symbol="› ")
            if not follow_up_input:
                continue
                
            # Intercept slash commands / exit commands
            if follow_up_input.strip().lower() in ("/quit", "/exit", "/q"):
                print(f"\n{BOLD}{GREEN}👋 Goodbye!{RESET}\n")
                db.close()
                return
                
            if follow_up_input.startswith("/"):
                is_cmd, action = await handle_slash_command(follow_up_input, session.id, db)
                if is_cmd:
                    if action == "exit":
                        db.close()
                        return
                    continue

            # Classify follow-up
            spinner_state["message"] = "Analyzing input"
            spinner[0] = asyncio.create_task(spinner_task(spinner_state))
            try:
                class_res = await classify_input(follow_up_input, on_token_callback=cli_token_callback)
            finally:
                stop_spinner()
                
            new_type = class_res["type"]
            new_subtype = class_res.get("subtype")
            
            # Reset session context based on classification
            if new_type in ("BUG", "FEATURE", "MEETING/PLANNING", "MEETING"):
                # Clean delete old steps
                db.query(repository.StepModel).filter(repository.StepModel.session_id == session.id).delete()
                
                session.type = "MEETING" if new_type == "MEETING/PLANNING" else new_type
                session.raw_input = follow_up_input
                session.subtype = new_subtype
                session.auto_execute = False
                db.commit()
                
                steps_list = get_workflow_steps_list(session.type)
                repository.add_steps(db, session_id=session.id, step_names=steps_list)
                print(f"\n{BOLD}{GREEN}✔ Task started: {session.type}{RESET}\n")
                continue
            elif new_type == "GENERAL_ENGINEERING_QUESTION":
                # Clean delete old steps
                db.query(repository.StepModel).filter(repository.StepModel.session_id == session.id).delete()
                
                session.type = "GENERAL_ENGINEERING_QUESTION"
                session.raw_input = follow_up_input
                session.subtype = None
                session.auto_execute = True
                db.commit()
                
                steps_list = get_workflow_steps_list("GENERAL_ENGINEERING_QUESTION")
                repository.add_steps(db, session_id=session.id, step_names=steps_list)
                continue
            else:
                # Uncertain / same workflow follow-up
                if session.type == "GENERAL_ENGINEERING_QUESTION":
                    # For general, any follow-up goes directly to General Advisor
                    db.query(repository.StepModel).filter(repository.StepModel.session_id == session.id).delete()
                    session.raw_input = follow_up_input
                    session.auto_execute = True
                    db.commit()
                    steps_list = get_workflow_steps_list("GENERAL_ENGINEERING_QUESTION")
                    repository.add_steps(db, session_id=session.id, step_names=steps_list)
                    continue
                else:
                    # Alert the user they should start a new task
                    print(f"\n{BOLD}{YELLOW}⚠️ Workflow complete. Please start a new task (e.g. '/bug', '/feature', or ask a question).{RESET}\n")
                    continue
            
        step_spec = get_workflow_by_type(session.type).get_step(pending_step.name)
        
        # Show playbook on first step if applicable
        if pending_step.name == "Capture & Clarify" and session.subtype:
            from src.workflows.playbooks import PLAYBOOKS
            matched_pb = PLAYBOOKS.get(session.subtype.lower())
            if not matched_pb:
                for pb in PLAYBOOKS.values():
                    if pb.name.lower() == session.subtype.lower():
                        matched_pb = pb
                        break
            if matched_pb:
                print(f"\n{BOLD}{YELLOW}🔥 ACTIVE TROUBLESHOOTING PLAYBOOK: {matched_pb.name.upper()}{RESET}")
                print(f"{GREY}────────────────────────────────────────────────────────────{RESET}")

                checklist_lines = [f"### 📋 IMMEDIATE {matched_pb.name.upper()} PLAYBOOK CHECKLIST"]
                for item in matched_pb.checklist:
                    checklist_lines.append(f"- [ ] {item}")
                checklist_lines.append("")
                await print_lines_gradually(checklist_lines)

                hypotheses_lines = ["### 🔍 PRIORITIZED HYPOTHESES"]
                for idx, h in enumerate(matched_pb.hypotheses, 1):
                    hypotheses_lines.append(f"{idx}. {h}")
                hypotheses_lines.append("")
                await print_lines_gradually(hypotheses_lines)

                tools_lines = ["### 🛠️ RECOMMENDED DIAGNOSTIC TOOLS"]
                for tool in matched_pb.recommended_tools:
                    tools_lines.append(f"- {tool}")
                tools_lines.append("")
                await print_lines_gradually(tools_lines)

                steps_lines = ["### 👣 NEXT DIAGNOSTIC STEPS"]
                for idx, ds in enumerate(matched_pb.diagnostic_steps, 1):
                    steps_lines.append(f"{idx}. {ds}")
                steps_lines.append("")
                await print_lines_gradually(steps_lines)

                questions_lines = ["### ❓ HIGH-VALUE CLARIFYING QUESTIONS"]
                for q in matched_pb.clarifying_questions:
                    questions_lines.append(f"- {q}")
                questions_lines.append("")
                await print_lines_gradually(questions_lines)
                print(f"{GREY}────────────────────────────────────────────────────────────{RESET}\n")

        # Render checklist progress
        if session.type != "GENERAL_ENGINEERING_QUESTION":
            await print_workflow_checklist(session, pending_step.name)

        is_general_short_circuit = (
            session.type == "GENERAL_ENGINEERING_QUESTION"
            and pending_step.name == "Address Question"
            and getattr(session, "auto_execute", False)
        )

        if is_general_short_circuit:
            user_input = session.original_input
            session.auto_execute = False
            db.commit()
        else:
            print(f"{BOLD}{CYAN}>>> CURRENT STEP: {pending_step.name}{RESET}")
            print(f"{BOLD}Description: {step_spec.description}{RESET}")
            if step_spec.is_critical:
                print(f"⚠️  {BOLD}{RED}CRITICAL STEP: Cannot be skipped without providing a reason.{RESET}")
            
            print_prompt_bar(session, pending_step.name)
            user_input = await get_multiline_input(prompt_text="Enter your inputs for this step (or 'skip' to bypass):")
            if not user_input:
                print(f"{RED}Input cannot be empty. Try again.{RESET}")
                continue
                
            # Intercept slash commands
            if user_input.startswith("/"):
                is_cmd, action = await handle_slash_command(user_input, session.id, db)
                if is_cmd:
                    if action == "exit":
                        db.close()
                        return
                    elif action == "continue":
                        continue
                    elif action and action.startswith("new_session:"):
                        target_type = action.split(":")[1]
                        desc = await get_multiline_input(prompt_text=f"Describe your {target_type} task:")
                        if not desc:
                            print(f"{RED}Description cannot be empty. Switch cancelled.{RESET}")
                            continue
                        session = repository.create_session(db, raw_input=desc, session_type=target_type, active_mode="PLAN")
                        task_type = target_type
                        steps_list = get_workflow_steps_list(task_type)
                        repository.add_steps(db, session_id=session.id, step_names=steps_list)
                        print(f"\n{BOLD}{GREEN}✔ Switch successful. New {target_type} session started with ID: {session.id}{RESET}\n")
                        continue
            
            # Skip Guard for 'Address Question' step
            if pending_step.name == "Address Question" and user_input.strip().lower().startswith("skip"):
                confirm = input(f"{BOLD}{YELLOW}⚠️ Skipping this step will close the session without an answer. Continue? (y/N){RESET}").strip().lower()
                if confirm != "y":
                    print(f"\n{BOLD}{GREEN}Skip cancelled. Returning to the step.{RESET}\n")
                    continue
            
        # Execute debate loop
        current_agent[0] = None
        spinner_state["message"] = f"Initiating Agent debate for {pending_step.name}"
        spinner[0] = asyncio.create_task(spinner_task(spinner_state))
        try:
            debate_res = await execute_step_debate(session.id, user_input, on_token_callback=cli_token_callback)
        finally:
            stop_spinner()
        
        title = f"DevCoach Response ({session.active_mode})"
        if session.type == "GENERAL_ENGINEERING_QUESTION":
            title = "DevCoach Response (GENERAL)"
            
        if debate_res['status'] in ["COMPLETED", "SKIPPED"]:
            status_color = GREEN
        elif debate_res['status'] == "COMPLETED_WITH_WARNINGS":
            status_color = YELLOW
        else:
            status_color = RED
            
        status_str = f"⚖️  {BOLD}Decision Status:{RESET} {status_color}{debate_res['status']}{RESET}"
        box_content = f"{status_str}\n\n{debate_res['feedback']}"
        
        print_boxed_response(title, box_content)
            
    db.close()

def main():
    try:
        # Handle command-line arguments (e.g. devcoach init)
        if len(sys.argv) > 1:
            cmd = sys.argv[1].lower()
            if cmd == "init":
                init_repository()
            else:
                print(f"Unknown command: {cmd}")
                print("Usage: devcoach [init]")
            sys.exit(0)
            
        asyncio.run(interactive_cli())
    except KeyboardInterrupt:
        print(f"\n{BOLD}{RED}DevCoach session terminated by user.{RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
