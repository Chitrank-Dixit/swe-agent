import asyncio
import sys
from src.state.db import init_db, SessionLocal
from src.state import repository
from src.agents.team import classify_input, execute_step_debate
from src.logging.logger import metrics_tracker
from src.workflows.bug import bug_workflow
from src.workflows.feature import feature_workflow
from src.workflows.meeting import meeting_workflow

async def interactive_cli():
    """Starts an interactive command-line session for the Software Engineering Workflow Coach."""
    init_db()
    db = SessionLocal()
    
    print("\n" + "="*60)
    print("   SOFTWARE ENGINEERING WORKFLOW COACH (CLI INTERACTIVE)")
    print("="*60)
    print("Identify a BUG, plan a FEATURE, or capture MEETING/PLANNING notes.\n")
    
    # 1. Capture Raw Input
    raw_input = input("Describe your task (e.g., bug error details, feature idea, agenda):\n> ").strip()
    if not raw_input:
        print("Task description cannot be empty. Exiting.")
        return

    # 2. Perform Classification
    print("\n[System] Classifying task category...")
    
    current_agent = [None]
    
    def cli_token_callback(agent: str, token: str):
        if current_agent[0] != agent:
            current_agent[0] = agent
            print(f"\n💬 [{agent}]: ", end="")
        print(token, end="")
        sys.stdout.flush()

    class_res = await classify_input(raw_input, on_token_callback=cli_token_callback)
    
    task_type = class_res["type"]
    clarifying_question = class_res["question"]
    task_subtype = class_res.get("subtype")
    
    # Handle uncertainty
    while task_type == "UNCERTAIN":
        print(f"\n[Coordinator] {clarifying_question}")
        answer = input("> ").strip()
        current_agent[0] = None  # Reset current agent tracker for next query
        class_res = await classify_input(answer, on_token_callback=cli_token_callback)
        task_type = class_res["type"]
        clarifying_question = class_res["question"]
        task_subtype = class_res.get("subtype")
        
    print(f"\n[System] Resolved task workflow type: {task_type}")
    if task_subtype:
        print(f"[System] Active playbook path: {task_subtype}")
    
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
    
    print(f"Session initialized with ID: {session.id}")
    print(f"Total workflow checklist steps to complete: {len(steps_list)}")
    print("-"*60)
    
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
            print("\n" + "="*60)
            print("   CONGRATULATIONS! ALL WORKFLOW STEPS ARE COMPLETED.")
            print("="*60)
            metrics = metrics_tracker.get_session_metrics(session.id)
            print(f"Steps Completed: {metrics['steps_completed']}")
            print(f"Skipped Critical Steps: {metrics['skipped_critical_steps']}")
            print(f"Time Elapsed: {metrics['elapsed_seconds']} seconds")
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
                print("\n" + "="*60)
                print(f"🔥 ACTIVE TROUBLESHOOTING PLAYBOOK: {matched_pb.name.upper()}")
                print("="*60)
                print(matched_pb.format_first_response())
                print("="*60 + "\n")

        print(f"\n>>> CURRENT STEP: {pending_step.name}")
        print(f"Description: {step_spec.description}")
        if step_spec.is_critical:
            print("⚠️  CRITICAL STEP: Cannot be skipped without providing a reason.")
        
        print("\nEnter your inputs for this step (or type 'skip' to bypass):")
        user_input = input("> ").strip()
        if not user_input:
            print("Input cannot be empty. Try again.")
            continue
            
        # Execute debate loop
        print("\n[System] Initiating Agent debate. Analyzing checklist guidelines...")
        current_agent[0] = None  # Reset current agent tracker for new debate session
        debate_res = await execute_step_debate(session.id, user_input, on_token_callback=cli_token_callback)
        
        print("\n" + "-"*40)
        print(f"📋 FINAL DEBATE SUMMARY ({pending_step.name}):")
        print("-"*40)
        print(f">>> DECISION STATUS: {debate_res['status']}")
        print(f"Feedback: {debate_res['feedback']}")
        print("-"*40)
            
    db.close()

if __name__ == "__main__":
    try:
        asyncio.run(interactive_cli())
    except KeyboardInterrupt:
        print("\nCLI Coach session terminated by user.")
        sys.exit(0)
