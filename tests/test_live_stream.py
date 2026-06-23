import asyncio
import sys
from src.state.db import init_db, SessionLocal
from src.state import repository
from src.agents.team import classify_input, execute_step_debate

async def test_streaming():
    init_db()
    db = SessionLocal()
    
    current_agent = [None]
    
    def token_callback(agent: str, token: str):
        if current_agent[0] != agent:
            current_agent[0] = agent
            print(f"\n💬 [{agent}]: ", end="")
        print(token, end="")
        sys.stdout.flush()

    print("\n--- STAGE 1: CLASSIFICATION STREAMING TEST ---")
    raw_input = "I am getting some delay in my python program, how to find the root cause in the code, I want to know which part of the program is taking time?"
    print(f"User Input: {raw_input}")
    
    # Run classification with token callback
    class_res = await classify_input(raw_input, on_token_callback=token_callback)
    task_type = class_res["type"]
    print(f"\n\n[System] Resolved task workflow type: {task_type}")
    
    print("\n--- STAGE 2: DEBATE STREAMING TEST (Capture & Clarify) ---")
    # Create session and steps
    session = repository.create_session(db, raw_input=raw_input, session_type=task_type)
    from src.workflows.bug import bug_workflow
    repository.add_steps(db, session_id=session.id, step_names=bug_workflow.get_step_names())
    
    # Run first step debate with token callback
    user_response = "I am on macOS 14.3, Python 3.11. The program hangs when reading a large 10GB CSV file using pandas read_csv without chunking."
    print(f"User Response: {user_response}")
    
    current_agent[0] = None
    debate_res = await execute_step_debate(session.id, user_response, on_token_callback=token_callback)
    
    print(f"\n\n[System] Debate Finished!")
    print(f"Decision Status: {debate_res['status']}")
    print(f"Feedback: {debate_res['feedback']}")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(test_streaming())
