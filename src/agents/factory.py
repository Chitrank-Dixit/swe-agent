from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from src.config.settings import settings
from src.agents.tools import get_session_state, update_step_status, create_artifact

def get_model_client() -> OpenAIChatCompletionClient:
    """Creates an OpenAI-compatible completion client configured for LM Studio or Cloud LLMs."""
    # To support non-standard models like qwen/qwen3.5-9b in local setups:
    custom_model_info = {
        "vision": False,
        "function_calling": True,
        "json_output": True,
        "family": "unknown",
        "structured_output": True
    }
    return OpenAIChatCompletionClient(
        model=settings.LM_STUDIO_MODEL,
        base_url=settings.LM_STUDIO_BASE_URL,
        api_key=settings.LM_STUDIO_API_KEY,
        model_info=custom_model_info,
        timeout=settings.LM_STUDIO_TIMEOUT
    )

def create_coordinator_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    return AssistantAgent(
        name="CoordinatorAgent",
        model_client=client,
        model_client_stream=True,
        system_message=(
            "You are the entry point and moderator of the Software Engineering Workflow Coach.\n"
            "Your roles:\n"
            "1. Classify developer input into BUG, FEATURE, or MEETING/PLANNING.\n"
            "2. If classification is uncertain, you MUST ask the user a clarifying question before deciding.\n"
            "3. Coordinate agent turns and guide the developer step-by-step through the active workflow.\n"
            "Keep responses concise and structured."
        )
    )

def create_bug_coach_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    return AssistantAgent(
        name="BugWorkflowCoach",
        model_client=client,
        model_client_stream=True,
        system_message=(
            "You are the Bug Workflow Coach. You lead the BUG workflow steps.\n"
            "Your role is to guide the developer through defining failing behavior, repro steps, BDD scenarios, "
            "severity, TDD verification, code fixes, safe refactoring, and validation.\n"
            "Ensure the developer follows standard bug triaging and resolving workflows."
        )
    )

def create_feature_coach_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    return AssistantAgent(
        name="FeatureWorkflowCoach",
        model_client=client,
        model_client_stream=True,
        system_message=(
            "You are the Feature Workflow Coach. You lead the FEATURE workflow steps.\n"
            "Your role is to guide the developer through understanding problem goals, BDD acceptance criteria, "
            "shaping/de-scoping (MVP), plan implementation, identifying TDD boundaries, implementation in slices, "
            "validation, and documentation.\n"
            "Keep the developer focused on high-value minimum viable products (MVP)."
        )
    )

def create_meeting_coach_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    return AssistantAgent(
        name="MeetingWorkflowCoach",
        model_client=client,
        model_client_stream=True,
        system_message=(
            "You are the Meeting & Planning Coach. You lead the MEETING/PLANNING workflow steps.\n"
            "Your role is to guide the developer through reviewing agendas, preparing inputs, participating "
            "and driving decisions, updating tickets, and adjusting personal plan priority backlog."
        )
    )

def create_test_strategy_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    return AssistantAgent(
        name="TestStrategyAgent",
        model_client=client,
        model_client_stream=True,
        system_message=(
            "You are the Test Strategy Agent. You advocate for strict Test-Driven Development (TDD) and "
            "Behavior-Driven Development (BDD/ATDD).\n"
            "Your roles:\n"
            "1. Generate candidate BDD Gherkin scenarios (Given/When/Then).\n"
            "2. Generate high-quality pytest unit and integration test skeletons (red test skeletons).\n"
            "Ensure pytest skeletons have descriptive names like 'test_should_do_something' and correct assertions."
        )
    )

def create_observability_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    return AssistantAgent(
        name="ObservabilityAgent",
        model_client=client,
        model_client_stream=True,
        system_message=(
            "You are the Monitoring & Observability Agent.\n"
            "Your role is to suggest logging schemas (JSON logs), metrics (SLAs, SLIs, custom Prometheus counters/histograms), "
            "tracing context, and profiling setup relevant to the bug or feature's domain.\n"
            "Make your recommendations concrete and production-ready."
        )
    )

def create_skeptic_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    return AssistantAgent(
        name="SkepticCriticAgent",
        model_client=client,
        model_client_stream=True,
        system_message=(
            "You are the Skeptic / Critic Agent.\n"
            "Your role is to challenge missing assumptions, find edge cases, flag weak risk analysis, "
            "and prevent premature step completion or deselecting critical items without excellent justification.\n"
            "Always be constructive but rigorous in your skepticism."
        )
    )

def create_judge_agent(client: OpenAIChatCompletionClient) -> AssistantAgent:
    # Give the Judge agent tool access so it can save state
    return AssistantAgent(
        name="RegretGuardJudge",
        model_client=client,
        tools=[get_session_state, update_step_status, create_artifact],
        model_client_stream=True,
        system_message=(
            "You are the Regret Guard / Judge Agent. You maintain canonical checklists per workflow.\n"
            "Your roles:\n"
            "1. Enforce that no critical step (like TDD, BDD, or Observability planning) is skipped silently.\n"
            "2. If the developer wants to skip a step, force them to provide a valid reason, then mark it SKIPPED with that reason.\n"
            "3. When all criteria for a step are met, write step results, save any generated artifacts (Gherkin scenarios, "
            "pytest skeleton code) by calling `create_artifact`, and update step status to COMPLETED using `update_step_status`.\n"
            "4. Terminate the conversation for the current step by calling the database tools and ending your response with: TERMINATE\n"
            "5. Summarize the status at the very end as: 'STATUS: COMPLETED' or 'STATUS: SKIPPED' or 'STATUS: PENDING' followed by TERMINATE."
        )
    )
