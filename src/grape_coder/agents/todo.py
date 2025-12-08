from strands import Agent

from grape_coder.config.manager import get_config_manager
from grape_coder.tools.work_path import (
    list_files,
    read_file,
    set_work_path,
)


def create_todo_generator_agent(work_path: str) -> Agent:
    """Create a todo generator agent that creates structured todo lists"""
    set_work_path(work_path)

    # Load configuration
    config_manager = get_config_manager()
    config = config_manager.load_config()

    # Validate configuration
    if not config.agents:
        raise ValueError(
            "No agents configured. Run 'grape-coder config' to set up providers and agents."
        )

    agent_name = "todo_generator"
    if agent_name not in config.agents:
        available_agents = list(config.agents.keys())
        raise ValueError(
            f"Agent '{agent_name}' not found. Available agents: {available_agents}. "
            "Run 'grape-coder config' to manage agents."
        )

    agent_config = config.agents[agent_name]
    provider_config = config.providers[agent_config.provider_ref]

    # Create model using ProviderFactory
    from ..config import ProviderFactory

    model = ProviderFactory.create_model(
        provider_config, agent_config.model_name
    ).model

    system_prompt = """You are a Todo Generator Agent specializing in creating structured, actionable todo lists from website development plans.

Your expertise includes:
- Breaking down complex projects into manageable tasks
- Creating logical task dependencies
- Prioritizing development tasks
- Structuring todo lists for efficient development
- Identifying implementation steps
- Organizing tasks by complexity and dependencies

When generating todos:
1. Analyze the complete website development plan from the swarm
2. Break down the project into logical, actionable tasks
3. Organize tasks in priority order
4. Create clear, specific todo items
5. Group related tasks together
6. Ensure todos are actionable by the code agent
7. Format the output as a structured todo list

Format your output as a numbered list of specific, actionable todo items that the code agent can execute step by step."""

    return Agent(
        model=model,
        tools=[list_files, read_file],
        system_prompt=system_prompt,
        name="todo_generator",
        description="Creates structured todo lists from website development plans",
    )
