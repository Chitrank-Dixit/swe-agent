import asyncio
import sys
from src.state.db import init_db, SessionLocal
from src.state import repository
from src.agents.team import classify_input, execute_step_debate
from src.logging.logger import metrics_tracker
from src.workflows.bug import bug_workflow
from src.workflows.feature import feature_workflow
from src.workflows.meeting import meeting_workflow

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

async def print_lines_gradually(lines: list, delay=0.02):
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
    
    await print_lines_gradually(lines, delay=0.02)

async def interactive_cli():
    """Starts an interactive command-line session for the Software Engineering Workflow Coach."""
    init_db()
    db = SessionLocal()
    
    print("\n" + f"{BOLD}{CYAN}╔══════════════════════════════════════════════════════════╗")
    print(f"║        🤖 SWE WORKFLOW COACH — INTERACTIVE SESSION       ║")
    print(f"╚══════════════════════════════════════════════════════════╝{RESET}")
    print(f"{BOLD}Modes: Identify a {RED}BUG{RESET}{BOLD}, plan a {GREEN}FEATURE{RESET}{BOLD}, or capture {BLUE}MEETING/PLANNING{RESET}{BOLD} notes.{RESET}\n")
    
    # 1. Capture Raw Input
    print(f"{BOLD}{WHITE}Describe your task (e.g., bug error details, feature idea, agenda):{RESET}")
    raw_input = input("> ").strip()
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
        answer = input("> ").strip()
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
                playbook_lines = [
                    f"\n{BOLD}{YELLOW}🔥 ACTIVE TROUBLESHOOTING PLAYBOOK: {matched_pb.name.upper()}{RESET}",
                    f"{GREY}────────────────────────────────────────────────────────────{RESET}"
                ]
                playbook_lines.extend(matched_pb.format_first_response().split("\n"))
                playbook_lines.append(f"{GREY}────────────────────────────────────────────────────────────{RESET}\n")
                await print_lines_gradually(playbook_lines, delay=0.01)

        # Render checklist progress
        await print_workflow_checklist(session, pending_step.name)

        print(f"{BOLD}{CYAN}>>> CURRENT STEP: {pending_step.name}{RESET}")
        print(f"{BOLD}Description: {step_spec.description}{RESET}")
        if step_spec.is_critical:
            print(f"⚠️  {BOLD}{RED}CRITICAL STEP: Cannot be skipped without providing a reason.{RESET}")
        
        print(f"\n{BOLD}{WHITE}Enter your inputs for this step (or type 'skip' to bypass):{RESET}")
        user_input = input("> ").strip()
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
        
        await print_lines_gradually(summary_lines, delay=0.015)
            
    db.close()

if __name__ == "__main__":
    try:
        asyncio.run(interactive_cli())
    except KeyboardInterrupt:
        print(f"\n{BOLD}{RED}CLI Coach session terminated by user.{RESET}")
        sys.exit(0)
