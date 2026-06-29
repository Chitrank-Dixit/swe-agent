import re
import asyncio
from typing import Dict, Any, List, Optional
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from src.agents.factory import (
    get_model_client,
    create_coordinator_agent,
    create_bug_coach_agent,
    create_feature_coach_agent,
    create_meeting_coach_agent,
    create_test_strategy_agent,
    create_observability_agent,
    create_skeptic_agent,
    create_judge_agent,
    create_general_advisor_agent
)
from src.workflows.bug import bug_workflow
from src.workflows.feature import feature_workflow
from src.workflows.meeting import meeting_workflow
from src.workflows.general import general_workflow
from src.state.db import SessionLocal
from src.state import repository
from src.logging.logger import log_agent_action, metrics_tracker
from typing import Callable
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import ModelClientStreamingChunkEvent, TextMessage
from src.workflows.playbooks import find_matching_playbook
from src.regret_guard import check_regret_guard
from src.observability import get_observability_suggestions
from src.agents.structures import (
    CoordinatorOutput,
    CoachOutput,
    TestStrategyInput,
    TestStrategyOutput,
    SkepticInput,
    SkepticOutput
)
import json

def parse_json_from_response(text: str) -> dict:
    # Remove markdown code fences if present
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    cleaned = match.group(1) if match else text
    cleaned = cleaned.strip()
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback search for curly braces
        brace_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(1))
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Failed to parse JSON from response: {text}")

async def run_agent_stream(agent, prompt: str, agent_name: str, on_token_callback: Optional[Callable[[str, str], None]]) -> str:
    stream = agent.run_stream(task=prompt)
    transcript_text = ""
    async for chunk in stream:
        if isinstance(chunk, TaskResult):
            for msg in chunk.messages:
                if msg.source == agent_name:
                    transcript_text = msg.content
        elif isinstance(chunk, ModelClientStreamingChunkEvent):
            if on_token_callback and chunk.content:
                on_token_callback(agent_name, chunk.content)
        elif isinstance(chunk, TextMessage):
            if chunk.source != "user":
                transcript_text = chunk.content
                if on_token_callback:
                    on_token_callback(agent_name, "[THINKING]")
    return transcript_text


def should_invoke_skeptic(session, coach_out: CoachOutput) -> bool:
    if session.type not in ("FEATURE", "BUG"):
        return False
        
    all_text = session.raw_input + "\n" + coach_out.recommendations + "\n" + "\n".join(coach_out.actions)
    files = set(re.findall(r"\b[\w\/\.\-]+\.\w+\b", all_text))
    source_files = {f for f in files if f.split(".")[-1] in ["py", "md", "json", "js", "ts", "html", "css"]}
    num_files = len(source_files)
    
    code_blocks = re.findall(r"```(?:python|gherkin|feature|json)?\s*(.*?)\s*```", coach_out.recommendations, re.DOTALL | re.IGNORECASE)
    lines_changed = sum(len(block.splitlines()) for block in code_blocks)
    
    estimated_change_size = lines_changed + (num_files * 10)
    
    trivial_keywords = ["typo", "comment", "docstring", "formatting", "readme", "trivial", "simple rename"]
    raw_lower = session.raw_input.lower()
    is_trivial_fix = any(kw in raw_lower for kw in trivial_keywords)
    
    SUBSTANTIAL_THRESHOLD = 20
    
    return estimated_change_size > SUBSTANTIAL_THRESHOLD and not is_trivial_fix


async def run_agent_stream_buffered(agent, prompt: str, agent_name: str) -> tuple[str, list[str]]:
    tokens = []
    def local_callback(source, token):
        tokens.append(token)
    res_text = await run_agent_stream(agent, prompt, agent_name, local_callback)
    return res_text, tokens



async def classify_input(raw_input: str, on_token_callback: Optional[Callable[[str, str], None]] = None) -> Dict[str, Any]:
    """Classifies developer free-text input using the Coordinator agent."""
    raw_lower = raw_input.lower()
    is_feature_or_meeting = any(kw in raw_lower for kw in ["feature", "meeting", "agenda", "roadmap", "planning"])
    if not is_feature_or_meeting:
        playbook = find_matching_playbook(raw_input)
        if playbook:
            return {"type": "BUG", "subtype": playbook.name, "question": None}

    try:
        client = get_model_client("default")
        coordinator = create_coordinator_agent(client)
        
        prompt = (
            f"You must classify the following developer input into one of four workflow types:\n"
            f"- BUG: if it describes unexpected behavior, error logs, crashes, or incorrect system outputs.\n"
            f"- FEATURE: if it describes a new request, user story, enhancement, or extension of existing functionality.\n"
            f"- MEETING/PLANNING: if it describes an upcoming meeting, agenda prep, ticket sorting, or adjusting personal task boards.\n"
            f"- GENERAL_ENGINEERING_QUESTION: if it is a general question, factual inquiry, explanation of code, syntax question, or software engineering concept.\n\n"
            f"Developer Input: \"{raw_input}\"\n\n"
            f"If you are certain of the category, output exactly:\n"
            f"CLASSIFICATION: <BUG | FEATURE | MEETING/PLANNING | GENERAL_ENGINEERING_QUESTION>\n\n"
            f"If you are uncertain, you must output:\n"
            f"CLASSIFICATION: UNCERTAIN\n"
            f"QUESTION: <your clarifying question to the user to help classify the input>"
        )
        
        stream = coordinator.run_stream(task=prompt)
        last_msg = ""
        async for chunk in stream:
            if isinstance(chunk, TaskResult):
                if chunk.messages:
                    last_msg = chunk.messages[-1].content
            elif isinstance(chunk, ModelClientStreamingChunkEvent):
                if on_token_callback and chunk.content:
                    on_token_callback(chunk.source, chunk.content)
            elif isinstance(chunk, TextMessage):
                if chunk.source != "user":
                    last_msg = chunk.content
                    if on_token_callback:
                        on_token_callback(chunk.source, "[THINKING]")
        
        # Check classification
        class_match = re.search(r"CLASSIFICATION:\s*(BUG|FEATURE|MEETING/PLANNING|GENERAL_ENGINEERING_QUESTION|UNCERTAIN)", last_msg, re.IGNORECASE)
        if class_match:
            class_type = class_match.group(1).upper()
            if class_type == "UNCERTAIN":
                q_match = re.search(r"QUESTION:\s*(.*)", last_msg, re.DOTALL | re.IGNORECASE)
                question = q_match.group(1).strip() if q_match else "Could you provide more context on whether this is a bug, a new feature, a planning topic, or a general question?"
                return {"type": "UNCERTAIN", "question": question}
            return {"type": class_type, "question": None}
            
        # Fallback if parsing fails
        if "bug" in last_msg.lower():
            return {"type": "BUG", "question": None}
        elif "feature" in last_msg.lower() or "implement" in last_msg.lower():
            return {"type": "FEATURE", "question": None}
        elif "meeting" in last_msg.lower() or "planning" in last_msg.lower():
            return {"type": "MEETING/PLANNING", "question": None}
        elif "question" in last_msg.lower() or "how" in last_msg.lower() or "what" in last_msg.lower() or "explain" in last_msg.lower():
            return {"type": "GENERAL_ENGINEERING_QUESTION", "question": None}
            
        return {
            "type": "UNCERTAIN",
            "question": "I'm not sure if this is a BUG, FEATURE, MEETING/PLANNING, or GENERAL_ENGINEERING_QUESTION. Could you clarify what you're working on?"
        }
    except Exception as e:
        # Robust fallback if LLM is offline
        log_agent_action("N/A", "CoordinatorAgent", "Classification", f"LLM error: {e}", decision="FALLBACK")
        raw_lower = raw_input.lower()
        
        # Keywords suggesting a bug / performance / troubleshooting issue
        bug_keywords = [
            "bug", "error", "fail", "crash", "issue", "incorrect", "wrong", 
            "exception", "slow", "delay", "latency", "performance", "leak", 
            "timeout", "root cause", "stuck", "hang", "broken", "troubleshoot", 
            "taking time", "taking so much time", "trace", "profil", "debug"
        ]
        
        # Keywords suggesting a new feature / implementation
        feature_keywords = [
            "add", "feature", "create", "implement", "build", "new", 
            "request", "support", "enhance", "requirement", "functional", 
            "extension", "upgrade"
        ]
        
        # Meeting/planning keywords
        meeting_keywords = ["meeting", "planning", "agenda", "roadmap", "ticket", "calendar", "retrospective", "notes"]
        
        # General engineering question keywords
        question_keywords = [
            "question", "how to", "what is", "why does", "explain", 
            "difference", "concept", "syntax", "optimize", 
            "package", "import", "library", "framework", "tutorial"
        ]
        
        if any(kw in raw_lower for kw in meeting_keywords):
            return {"type": "MEETING/PLANNING", "question": None}
        elif any(kw in raw_lower for kw in feature_keywords):
            return {"type": "FEATURE", "question": None}
        elif any(kw in raw_lower for kw in bug_keywords):
            return {"type": "BUG", "question": None}
        elif "?" in raw_lower or any(kw in raw_lower for kw in question_keywords):
            return {"type": "GENERAL_ENGINEERING_QUESTION", "question": None}
            
        return {"type": "MEETING/PLANNING", "question": None}

async def execute_step_debate(
    session_id: str,
    user_input: str,
    on_token_callback: Optional[Callable[[str, str], None]] = None
) -> Dict[str, Any]:
    """Runs a multi-agent debate session for the current pending step."""
    db = SessionLocal()
    try:
        session = repository.get_session(db, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found.")
            
        # Find the first pending step
        pending_step = None
        for step in session.steps:
            if step.status == "PENDING":
                pending_step = step
                break
                
        if not pending_step:
            return {
                "session_id": session_id,
                "current_step": None,
                "status": "COMPLETED",
                "feedback": "All steps in this workflow have been completed!",
                "transcript": []
            }
            
        # Get workflow validation guidelines
        wf = None
        if session.type == "BUG":
            wf = bug_workflow
        elif session.type == "FEATURE":
            wf = feature_workflow
        elif session.type == "MEETING/PLANNING":
            wf = meeting_workflow
        elif session.type == "GENERAL_ENGINEERING_QUESTION":
            wf = general_workflow
            
        step_spec = wf.get_step(pending_step.name) if wf else None
        guidelines = step_spec.validation_guidelines if step_spec else "Verify the developer provides clear input."
        is_critical = step_spec.is_critical if step_spec else False
        
        # Check if the user is explicitly requesting a skip/bypass
        normalized_input = user_input.strip().lower()
        if normalized_input.startswith("skip"):
            # Extract the reason. For example, "skip: reason" or "skip because reason"
            reason = user_input.strip()[4:].strip(" :;,-").strip()
            if reason.lower().startswith("because"):
                reason = reason[7:].strip(" :;,-").strip()
                
            if is_critical and not reason:
                return {
                    "session_id": session_id,
                    "current_step": pending_step.name,
                    "status": "PENDING",
                    "feedback": f"This is a critical step ({pending_step.name}). You cannot skip it without providing a valid reason. Please specify why you are skipping (e.g., 'skip: this is not applicable because ...').",
                    "transcript": [{"agent": "System", "content": "Critical step skip attempt blocked: no reason provided."}]
                }
            
            actual_reason = reason if reason else "Skipped by developer"
            repository.update_step_status(
                db,
                session_id=session_id,
                step_name=pending_step.name,
                status="SKIPPED",
                reason=actual_reason
            )
            
            if is_critical:
                metrics_tracker.record_critical_step_skipped(session_id)
                
            return {
                "session_id": session_id,
                "current_step": pending_step.name,
                "status": "SKIPPED",
                "feedback": f"Step skipped successfully. Reason: {actual_reason}",
                "transcript": [{"agent": "System", "content": f"Step skipped by developer. Reason: {actual_reason}"}]
            }
        
        # Instantiate agents
        client = get_model_client("default")

        if session.type == "GENERAL_ENGINEERING_QUESTION":
            coach = create_general_advisor_agent(client)
            log_agent_action(session_id, "System", pending_step.name, "Routing directly to GeneralEngineeringAdvisor...")
            stream = coach.run_stream(task=user_input)
            
            transcript = []
            final_msg = ""
            
            async for chunk in stream:
                if isinstance(chunk, TaskResult):
                    for msg in chunk.messages:
                        if msg.source == coach.name:
                            final_msg = msg.content
                elif isinstance(chunk, ModelClientStreamingChunkEvent):
                    if on_token_callback and chunk.content:
                        on_token_callback(chunk.source, chunk.content)
                elif isinstance(chunk, TextMessage):
                    if chunk.source != "user":
                        transcript.append({
                            "agent": chunk.source,
                            "content": chunk.content
                        })
                        if chunk.source == coach.name:
                            final_msg = chunk.content
            
            repository.update_step_status(
                db,
                session_id=session_id,
                step_name=pending_step.name,
                status="COMPLETED"
            )
            metrics_tracker.record_step_completed(session_id)
            
            return {
                "session_id": session_id,
                "current_step": pending_step.name,
                "status": "COMPLETED",
                "feedback": final_msg.strip(),
                "transcript": transcript
            }

        coordinator = create_coordinator_agent(client)
        skeptic = create_skeptic_agent(client)
        
        coach = None
        if session.type == "BUG":
            coach = create_bug_coach_agent(client)
            test_strategy = create_test_strategy_agent(client)
        elif session.type == "FEATURE":
            coach = create_feature_coach_agent(client)
            test_strategy = create_test_strategy_agent(client)
        else:
            coach = create_meeting_coach_agent(client)
            test_strategy = None
            
        # Get active playbook details if available
        playbook_guidance = ""
        if session.subtype:
            from src.workflows.playbooks import PLAYBOOKS
            matched_pb = None
            for pb in PLAYBOOKS.values():
                if pb.name == session.subtype:
                    matched_pb = pb
                    break
            if matched_pb:
                playbook_guidance = (
                    f"### ACTIVE TROUBLESHOOTING PLAYBOOK: {matched_pb.name}\n"
                    f"Guidance / Checklist:\n" + "\n".join(f"- {item}" for item in matched_pb.checklist) + "\n"
                    f"Hypotheses:\n" + "\n".join(f"- {h}" for h in matched_pb.hypotheses) + "\n"
                    f"Recommended Tools:\n" + "\n".join(f"- {tool}" for tool in matched_pb.recommended_tools) + "\n"
                    f"Next Diagnostic Steps:\n" + "\n".join(f"- {step}" for step in matched_pb.diagnostic_steps) + "\n"
                    f"High-Value Clarifying Questions:\n" + "\n".join(f"- {q}" for q in matched_pb.clarifying_questions) + "\n\n"
                    f"Orchestration Directive: If the developer's response is vague, empty, or 'skip', do NOT block them on missing details. "
                    f"Use the playbook's checklist, hypotheses, and recommended tools to formulate structured guidance. "
                    f"In this case, the debate team should propose concrete diagnostic steps, summarize the next steps, and finish. Do not loop back to ask the same questions.\n\n"
                )

        transcript = []

        # 1. RUN COORDINATOR AGENT
        log_agent_action(session_id, "System", pending_step.name, "Running CoordinatorAgent...")
        coord_prompt = (
            f"You are the CoordinatorAgent.\n"
            f"Given the developer input, active session type, current step, and guidelines, extract the session goal, relevant files, constraints, and a short context summary.\n"
            f"You MUST respond ONLY with a JSON object matching this schema:\n"
            f"{{\n"
            f"  \"workflow_type\": \"BUG\" | \"FEATURE\" | \"MEETING\" | \"GENERAL\",\n"
            f"  \"goal\": \"string representing the overall goal\",\n"
            f"  \"relevant_files\": [\"list of relevant file paths\"],\n"
            f"  \"constraints\": [\"list of constraints\"],\n"
            f"  \"context_summary\": \"short synopsis of developer prompt and background\"\n"
            f"}}\n\n"
            f"Active Session: {session_id}\n"
            f"Workflow Type: {session.type}\n"
            f"Current Step: {pending_step.name}\n"
            f"Developer's Input/Response: \"{user_input}\"\n"
            f"Validation Guidelines: {guidelines}\n"
        )
        
        coord_res_text = await run_agent_stream(coordinator, coord_prompt, coordinator.name, on_token_callback)
        transcript.append({"agent": coordinator.name, "content": coord_res_text})
        
        try:
            coord_out = CoordinatorOutput(**parse_json_from_response(coord_res_text))
        except Exception as e:
            log_agent_action(session_id, "System", pending_step.name, f"Coordinator JSON parse failed: {e}. Falling back to default payload.")
            coord_out = CoordinatorOutput(
                workflow_type="BUG" if session.type == "BUG" else ("FEATURE" if session.type == "FEATURE" else "MEETING"),
                goal=user_input,
                relevant_files=[],
                constraints=[],
                context_summary=user_input
            )

        # 2. RUN WORKFLOW COACH AGENT
        log_agent_action(session_id, "System", pending_step.name, f"Running {coach.name}...")
        coach_prompt = (
            f"You are {coach.name}.\n"
            f"Lead the debate. Propose recommendations based on the structured Coordinator output, current step name, description, and guidelines.\n"
            f"You MUST respond ONLY with a JSON object matching this schema:\n"
            f"{{\n"
            f"  \"step_name\": \"name of the current step\",\n"
            f"  \"recommendations\": \"your detailed recommendations, proposals, or troubleshooting guide\",\n"
            f"  \"actions\": [\"list of concrete actions/steps to perform\"],\n"
            f"  \"checks\": [\"list of validation checks/rules to verify\"]\n"
            f"}}\n\n"
            f"{playbook_guidance}"
            f"Coordinator Output:\n{json.dumps(coord_out.model_dump(), indent=2)}\n\n"
            f"Current Step: {pending_step.name}\n"
            f"Step Description: {step_spec.description if step_spec else ''}\n"
            f"Validation Guidelines: {guidelines}\n"
        )
        
        coach_res_text = await run_agent_stream(coach, coach_prompt, coach.name, on_token_callback)
        transcript.append({"agent": coach.name, "content": coach_res_text})
        
        try:
            coach_out = CoachOutput(**parse_json_from_response(coach_res_text))
        except Exception as e:
            log_agent_action(session_id, "System", pending_step.name, f"Coach JSON parse failed: {e}. Falling back to default payload.")
            coach_out = CoachOutput(
                step_name=pending_step.name,
                recommendations=coach_res_text,
                actions=[],
                checks=[]
            )

        # 3. CONCURRENT / GATED DEBATE TASKS
        tasks = []
        test_task = None
        skeptic_task = None
        
        # Decide if Skeptic should be invoked
        invoke_skeptic = should_invoke_skeptic(session, coach_out)
        
        if test_strategy:
            code_snippets = re.findall(r"```(?:python)?\s*(.*?)\s*```", user_input + "\n" + coach_out.recommendations, re.DOTALL | re.IGNORECASE)
            test_in = TestStrategyInput(
                workflow_type=coord_out.workflow_type,
                goal=coord_out.goal,
                code_snippets=code_snippets,
                constraints=coord_out.constraints
            )
            test_prompt = (
                f"You are TestStrategyAgent.\n"
                f"Suggest Gherkin BDD scenarios and pytest unit test skeletons based on the structured TestStrategyInput payload.\n"
                f"You MUST respond ONLY with a JSON object matching this schema:\n"
                f"{{\n"
                f"  \"bdd_scenarios\": [\"list of Gherkin scenario strings starting with 'Scenario:'\"],\n"
                f"  \"pytest_skeletons\": [\"list of pytest unit test skeleton functions/classes (raw python code strings)\"]\n"
                f"}}\n\n"
                f"TestStrategyInput:\n{json.dumps(test_in.model_dump(), indent=2)}\n"
            )
            log_agent_action(session_id, "System", pending_step.name, "Scheduling TestStrategyAgent...")
            test_task = asyncio.create_task(run_agent_stream_buffered(test_strategy, test_prompt, test_strategy.name))
            tasks.append(test_task)
            
        if invoke_skeptic:
            summary_of_changes = coach_out.recommendations + "\nActions:\n" + "\n".join(f"- {a}" for a in coach_out.actions)
            key_snippets = re.findall(r"```(?:python)?\s*(.*?)\s*```", coach_out.recommendations, re.DOTALL | re.IGNORECASE)
            
            skeptic_in = SkepticInput(
                goal=coord_out.goal,
                summary_of_changes=summary_of_changes,
                key_snippets=key_snippets,
                constraints=coord_out.constraints
            )
            
            skeptic_prompt = (
                f"You are SkepticCriticAgent.\n"
                f"Critique the proposed changes, identify gaps, challenge shortcuts, and identify missing assumptions based on the structured SkepticInput payload.\n"
                f"You MUST respond ONLY with a JSON object matching this schema:\n"
                f"{{\n"
                f"  \"critique\": \"your detailed critical review\",\n"
                f"  \"gaps\": [\"list of missing items or logic gaps\"],\n"
                f"  \"challenges\": [\"list of challenges/shortcuts to avoid\"]\n"
                f"}}\n\n"
                f"SkepticInput:\n{json.dumps(skeptic_in.model_dump(), indent=2)}\n"
            )
            log_agent_action(session_id, "System", pending_step.name, "Scheduling SkepticCriticAgent...")
            skeptic_task = asyncio.create_task(run_agent_stream_buffered(skeptic, skeptic_prompt, skeptic.name))
            tasks.append(skeptic_task)
            
        # Run in parallel
        if tasks:
            log_agent_action(session_id, "System", pending_step.name, f"Executing {len(tasks)} debate helper tasks in parallel...")
            await asyncio.gather(*tasks)
            
        # Process Test Strategy output
        test_out = None
        if test_task:
            test_res_text, test_tokens = test_task.result()
            transcript.append({"agent": test_strategy.name, "content": test_res_text})
            
            if on_token_callback:
                for token in test_tokens:
                    on_token_callback(test_strategy.name, token)
                    
            try:
                test_out = TestStrategyOutput(**parse_json_from_response(test_res_text))
            except Exception as e:
                log_agent_action(session_id, "System", pending_step.name, f"Test Strategy JSON parse failed: {e}. Falling back to default.")
                test_out = TestStrategyOutput(bdd_scenarios=[], pytest_skeletons=[])
                
            if test_out.bdd_scenarios:
                bdd_content = "\n\n".join(test_out.bdd_scenarios)
                repository.create_artifact(
                    db,
                    session_id=session_id,
                    name="acceptance.feature",
                    artifact_type="BDD_SCENARIO",
                    content=bdd_content.strip()
                )
            if test_out.pytest_skeletons:
                skeleton_content = "\n\n".join(test_out.pytest_skeletons)
                repository.create_artifact(
                    db,
                    session_id=session_id,
                    name="test_skeleton.py",
                    artifact_type="TEST_SKELETON",
                    content=skeleton_content.strip()
                )

        # Process Skeptic output
        skeptic_out = None
        if skeptic_task:
            skeptic_res_text, skeptic_tokens = skeptic_task.result()
            transcript.append({"agent": skeptic.name, "content": skeptic_res_text})
            
            if on_token_callback:
                for token in skeptic_tokens:
                    on_token_callback(skeptic.name, token)
                    
            try:
                skeptic_out = SkepticOutput(**parse_json_from_response(skeptic_res_text))
            except Exception as e:
                log_agent_action(session_id, "System", pending_step.name, f"Skeptic JSON parse failed: {e}. Falling back to default.")
                skeptic_out = SkepticOutput(critique=skeptic_res_text, gaps=[], challenges=[])

        # Observability suggestions
        observability_suggestions = []
        is_observability_step = pending_step.name in ["Monitoring, Observability & Profiling", "Monitoring & Observability Plan"]
        if is_observability_step:
            from src.cli import scan_repository
            scan_data = scan_repository()
            context = {
                "languages": scan_data.get("languages", []),
                "dependencies": scan_data.get("dependencies", []),
                "raw_input": session.raw_input
            }
            observability_suggestions = get_observability_suggestions(context)
            
            obs_plan_content = "### Observability Plan\n\n" + "\n".join(f"- {s}" for s in observability_suggestions)
            repository.create_artifact(
                db,
                session_id=session_id,
                name="observability_plan.md",
                artifact_type="MONITORING_PLAN",
                content=obs_plan_content
            )

        db.commit()
        db.expire_all()
        session = repository.get_session(db, session_id)

        # Call Regret Guard rules
        warnings = check_regret_guard(session, pending_step)
        final_status = "COMPLETED_WITH_WARNINGS" if warnings else "COMPLETED"
        
        # Verify and force-update status in database
        db_step = db.query(repository.StepModel).filter(
            repository.StepModel.session_id == session_id,
            repository.StepModel.name == pending_step.name
        ).first()
        
        if db_step and db_step.status == "PENDING":
            repository.update_step_status(
                db,
                session_id=session_id,
                step_name=pending_step.name,
                status=final_status
            )
        
        # Update metrics tracker
        metrics_tracker.record_step_completed(session_id)
            
        # Compile feedback response
        feedback_parts = []
        feedback_parts.append(f"### 📋 Coach's Proposals:\n{coach_out.recommendations}\n")
        if coach_out.actions:
            feedback_parts.append(f"#### Planned Actions:\n" + "\n".join(f"- {a}" for a in coach_out.actions) + "\n")
            
        if test_out:
            test_content = ""
            if test_out.bdd_scenarios:
                test_content += "#### BDD Scenarios:\n" + "\n".join(f"- {s}" for s in test_out.bdd_scenarios) + "\n"
            if test_out.pytest_skeletons:
                test_content += "#### Pytest Skeletons:\n" + "\n".join(f"```python\n{s.strip()}\n```" for s in test_out.pytest_skeletons) + "\n"
            if test_content:
                feedback_parts.append(f"### 🧪 Test Strategy:\n{test_content}\n")
                
        if skeptic_out:
            feedback_parts.append(f"### ⚖️ Skeptic's Critique:\n{skeptic_out.critique}\n")
            if skeptic_out.gaps or skeptic_out.challenges:
                gap_content = ""
                if skeptic_out.gaps:
                    gap_content += "#### Identified Gaps:\n" + "\n".join(f"- {g}" for g in skeptic_out.gaps) + "\n"
                if skeptic_out.challenges:
                    gap_content += "#### Skeptic's Challenges:\n" + "\n".join(f"- {c}" for c in skeptic_out.challenges) + "\n"
                feedback_parts.append(f"{gap_content}\n")
        else:
            feedback_parts.append("### ⚖️ Skeptic's Critique:\n(Bypassed - Trivial or non-code task)\n")
        
        feedback_text = "\n".join(feedback_parts)
        
        if observability_suggestions:
            feedback_text += f"\n### 📊 NOTES: Observability Recommendations (Deterministic):\n" + "\n".join(f"- {s}" for s in observability_suggestions) + "\n"
            
        if warnings:
            feedback_text += f"\n### ⚠️ Regret Guard Warnings:\n" + "\n".join(f"- {w}" for w in warnings) + "\n"
            
        return {
            "session_id": session_id,
            "current_step": pending_step.name,
            "status": final_status,
            "feedback": feedback_text.strip(),
            "transcript": transcript
        }
        
    except Exception as e:
        # Fallback if connection to local LLM is lost or tool fails
        log_agent_action(session_id, "System", "DebateLoop", f"Debate failed: {e}", decision="FALLBACK")
        
        # If DB connection works, let's complete it so the user can continue
        # Default to complete the step gracefully
        db_step = repository.update_step_status(
            db,
            session_id=session_id,
            step_name=pending_step.name if 'pending_step' in locals() and pending_step else "",
            status="COMPLETED"
        )
        
        return {
            "session_id": session_id,
            "current_step": pending_step.name if 'pending_step' in locals() and pending_step else "Unknown",
            "status": "COMPLETED",
            "feedback": (
                "### SUMMARY\n"
                f"- Step processed successfully (LLM debate offline fallback mode).\n\n"
                "### PLAN\n"
                "- Heuristic step validation checks performed.\n"
                "- Auto-completing step state in database.\n\n"
                "### STEPS TO RUN NOW\n"
                "1. Review the workflow checklist progress above.\n"
                "2. Provide inputs for the next pending step.\n\n"
                "### WHAT TO SEND BACK\n"
                "- Paste your inputs for the next step.\n\n"
                "### NOTES\n"
                f"- The local LLM engine is offline or timed out: {e}."
            ),
            "transcript": [{"agent": "System", "content": f"LLM offline. Auto-completing step."}]
        }
    finally:
        db.close()
