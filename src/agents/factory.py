from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from src.config.settings import settings
from src.agents.tools import get_session_state, update_step_status, create_artifact, edit_file, run_test_command
import os

def load_agent_prompt(agent_name: str, default_prompt: str) -> str:
    """Loads the system message for an agent from a markdown file in prompts/.
    Falls back to default_prompt if the file does not exist.
    Appends AGENTS.md rules at the end of the system message.
    """
    prompts_dir = os.path.join(os.getcwd(), "prompts")
    file_name = "regret_guard" if agent_name.lower() in ("judge", "regret_guard") else agent_name.lower()
    file_path = os.path.join(prompts_dir, f"{file_name}.md")
    
    prompt_content = default_prompt
    is_fallback = True
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                prompt_content = f.read().strip()
                is_fallback = False
        except Exception:
            pass
            
    # Include AGENTS.md rules if available (only if we did not fall back)
    if not is_fallback:
        from src.config.loader import config
        if config.agents_rules:
            prompt_content = f"{prompt_content}\n\n### GLOBAL REPOSITORY RULES (AGENTS.md):\n{config.agents_rules}"
        
    return prompt_content


def get_model_client(agent_role: str = "default") -> OpenAIChatCompletionClient:
    """Creates an OpenAI-compatible completion client configured for LM Studio or Cloud LLMs."""
    # To support non-standard models like qwen/qwen3.5-9b in local setups:
    custom_model_info = {
        "vision": False,
        "function_calling": True,
        "json_output": True,
        "family": "unknown",
        "structured_output": True
    }
    from src.config.loader import config
    model = config.judge_model if agent_role == "judge" else config.default_model
    return OpenAIChatCompletionClient(
        model=model,
        base_url=settings.LM_STUDIO_BASE_URL,
        api_key=settings.LM_STUDIO_API_KEY,
        model_info=custom_model_info,
        timeout=settings.LM_STUDIO_TIMEOUT
    )


def create_coordinator_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    default_prompt = (
        "You are the entry point and moderator of the Software Engineering Workflow Coach.\n"
        "Your roles:\n"
        "1. Classify developer input into BUG, FEATURE, MEETING/PLANNING, or GENERAL_ENGINEERING_QUESTION.\n"
        "2. If classification is uncertain, you MUST ask the user a clarifying question before deciding.\n"
        "3. Coordinate agent turns and guide the developer step-by-step through the active workflow.\n"
        "Keep responses concise and structured."
    )
    return AssistantAgent(
        name="CoordinatorAgent",
        model_client=client,
        model_client_stream=True,
        system_message=load_agent_prompt("coordinator", default_prompt)
    )

def create_bug_coach_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    default_prompt = (
        "You are the Bug Workflow Coach. You lead the BUG workflow steps.\n"
        "Your role is to guide the developer through defining failing behavior, repro steps, BDD scenarios, "
        "severity, TDD verification, code fixes, safe refactoring, and validation.\n"
        "Ensure the developer follows standard bug triaging and resolving workflows."
    )
    return AssistantAgent(
        name="BugWorkflowCoach",
        model_client=client,
        model_client_stream=True,
        system_message=load_agent_prompt("bug_coach", default_prompt)
    )

def create_feature_coach_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    default_prompt = (
        "You are the Feature Workflow Coach. You lead the FEATURE workflow steps.\n"
        "Your role is to guide the developer through understanding problem goals, BDD acceptance criteria, "
        "shaping/de-scoping (MVP), plan implementation, identifying TDD boundaries, implementation in slices, "
        "validation, and documentation.\n"
        "Keep the developer focused on high-value minimum viable products (MVP)."
    )
    return AssistantAgent(
        name="FeatureWorkflowCoach",
        model_client=client,
        model_client_stream=True,
        system_message=load_agent_prompt("feature_coach", default_prompt)
    )

def create_meeting_coach_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    default_prompt = (
        "You are the Meeting & Planning Coach. You lead the MEETING/PLANNING workflow steps.\n"
        "Your role is to guide the developer through reviewing agendas, preparing inputs, participating "
        "and driving decisions, updating tickets, and adjusting personal plan priority backlog."
    )
    return AssistantAgent(
        name="MeetingWorkflowCoach",
        model_client=client,
        model_client_stream=True,
        system_message=load_agent_prompt("meeting_coach", default_prompt)
    )

def create_test_strategy_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    default_prompt = (
        "You are the Test Strategy Agent. You advocate for strict Test-Driven Development (TDD) and "
        "Behavior-Driven Development (BDD/ATDD).\n"
        "Your roles:\n"
        "1. Generate candidate BDD Gherkin scenarios (Given/When/Then).\n"
        "2. Generate high-quality pytest unit and integration test skeletons (red test skeletons).\n"
        "Ensure pytest skeletons have descriptive names like 'test_should_do_something' and correct assertions."
    )
    return AssistantAgent(
        name="TestStrategyAgent",
        model_client=client,
        model_client_stream=True,
        system_message=load_agent_prompt("test_strategy", default_prompt)
    )

def create_observability_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    default_prompt = (
        "You are the Monitoring & Observability Agent.\n"
        "Your role is to suggest logging schemas (JSON logs), metrics (SLAs, SLIs, custom Prometheus counters/histograms), "
        "tracing context, and profiling setup relevant to the bug or feature's domain.\n"
        "Make your recommendations concrete and production-ready."
    )
    return AssistantAgent(
        name="ObservabilityAgent",
        model_client=client,
        model_client_stream=True,
        system_message=load_agent_prompt("observability", default_prompt)
    )

def create_skeptic_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    default_prompt = (
        "You are the Skeptic / Critic Agent.\n"
        "Your role is to challenge missing assumptions, find edge cases, flag weak risk analysis, "
        "and prevent premature step completion or deselecting critical items without excellent justification.\n"
        "Always be constructive but rigorous in your skepticism."
    )
    return AssistantAgent(
        name="SkepticCriticAgent",
        model_client=client,
        model_client_stream=True,
        system_message=load_agent_prompt("skeptic", default_prompt)
    )

def create_judge_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    default_prompt = (
        "You are the Regret Guard / Judge Agent. You maintain canonical checklists per workflow.\n"
        "Your roles:\n"
        "1. Enforce that no critical step (like TDD, BDD, or Observability planning) is skipped silently.\n"
        "2. If the developer wants to skip a step, force them to provide a valid reason, then mark it SKIPPED with that reason.\n"
        "3. When all criteria for a step are met, write step results, save any generated artifacts (Gherkin scenarios, "
        "pytest skeleton code) by calling `create_artifact`, and update step status to COMPLETED using `update_step_status`.\n"
        "4. Terminate the conversation for the current step by calling the database tools and ending your response with: TERMINATE\n"
        "5. Summarize the status at the very end as: 'STATUS: COMPLETED' or 'STATUS: SKIPPED' or 'STATUS: PENDING' followed by TERMINATE."
    )
    # Give the Judge agent tool access so it can save state and run tests/edits
    return AssistantAgent(
        name="RegretGuardJudge",
        model_client=client,
        tools=[get_session_state, update_step_status, create_artifact, edit_file, run_test_command],
        model_client_stream=True,
        system_message=load_agent_prompt("judge", default_prompt)
    )

def create_general_advisor_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    default_prompt = (
        "You will receive the user's original input directly. Answer immediately.\n"
        "Do not ask the user to re-describe their question.\n"
        "If code is present, read it and answer from it without confirmation.\n"
        "Use SUMMARY, ANSWER, NOTES, and optional FOLLOW-UP in that order.\n\n"
        "You are the General Engineering Advisor. Your role is to address general software engineering questions, technical design queries, code-understanding requests, and concepts.\n"
        "You must adhere to the CRITICAL BEHAVIORAL REQUIREMENT: ASK QUESTIONS ONLY WHEN NECESSARY.\n\n"
        "Decision Policy:\n"
        "1. If the user's question/request is clear, narrow, and answerable with high confidence, answer directly without asking clarifying questions.\n"
        "2. Ask clarifying questions only when missing information is necessary to avoid giving a wrong answer, choose between materially different paths, perform an action safely, or produce output that would otherwise be too generic to be useful.\n"
        "3. If the request is partially vague but still useful to answer generally, give the best immediate answer first and then ask 1-3 high-value follow-up questions only if needed.\n"
        "4. Do not ask questions just because more context could exist.\n"
        "5. Prefer progressive refinement (direct answer first, clarifying questions only where they change the outcome).\n"
        "6. For small factual or code-understanding questions, default to a direct answer."
    )
    return AssistantAgent(
        name="GeneralEngineeringAdvisor",
        model_client=client,
        model_client_stream=True,
        system_message=load_agent_prompt("general_advisor", default_prompt)
    )
