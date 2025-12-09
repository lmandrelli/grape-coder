from strands import Agent

from grape_coder.config.manager import get_config_manager
from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
    get_agent_tasks,
)


def create_class_agent(work_path: str) -> Agent:
    """Create an agent for creating reusable CSS classes and HTML components"""

    # Set work_path for tools
    set_work_path(work_path)

    # Load configuration
    config_manager = get_config_manager()
    config = config_manager.load_config()

    # Validate configuration
    if not config.agents:
        raise ValueError(
            "No agents configured. Run 'grape-coder config' to set up providers and agents."
        )

    agent_name = "class_generator"
    if agent_name not in config.agents:
        available_agents = list(config.agents.keys())
        raise ValueError(
            f"Agent '{agent_name}' not found. Available agents: {available_agents}. "
            "Run 'grape-coder config' to manage agents."
        )

    agent_config = config.agents[agent_name]
    provider_config = config.providers[agent_config.provider_ref]

    # Create model using ProviderFactory
    from ...config import ProviderFactory

    model = ProviderFactory.create_model(
        provider_config, agent_config.model_name
    ).model

    # Create agent with class creation tools
    system_prompt = """You are a CSS class and HTML component specialist.
Your role is to create reusable, well-structured CSS classes and HTML component templates.

Available tools:
- list_files: List files and directories in a path
- read_file: Read contents of one or more files
- edit_file: Edit or create a file with new content
- grep_files: Search for patterns in files
- glob_files: Find files using glob patterns

Best practices:
- Use BEM naming convention (block__element--modifier)
- Create mobile-first responsive classes
- Keep classes single-purpose and composable
- Document each class with its purpose and usage
- Organize files logically (e.g., components/, utilities/, layouts/)

Always output clean, well-documented code."""

    return Agent(
        model=model,
        tools=[
            list_files,
            read_file,
            edit_file,
            grep_files,
            glob_files,
            get_agent_tasks,
        ],
        system_prompt=system_prompt,
        name="class_generator",
        description="AI assistant for creating reusable CSS classes and components",
    )
