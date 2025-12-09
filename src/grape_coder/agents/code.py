from typing import cast

from strands import Agent
from strands.models.model import Model

from grape_coder.tools.agents import get_agent_tasks
from grape_coder.tools.web import fetch_url
from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)

from ..config import ProviderFactory, get_config_manager


def create_code_agent(work_path: str) -> Agent:
    """Create a code agent with file system tools"""

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

    agent_name = "code"

    if agent_name not in config.agents:
        available_agents = list(config.agents.keys())
        raise ValueError(
            f"Agent '{agent_name}' not found. Available agents: {available_agents}. "
            "Run 'grape-coder config' to manage agents."
        )

    agent_config = config.agents[agent_name]
    provider_config = config.providers[agent_config.provider_ref]

    # Create model using LiteLLM integration
    model = cast(
        Model, ProviderFactory.create_model(provider_config, agent_config.model_name)
    )

    # Create agent with file system tools
    system_prompt = """You are a code assistant with access to file system tools.
You can list files, read files, edit/create files, search for content, use glob patterns, and fetch web content.

Available tools:
- list_files: List files and directories in a path
- read_file: Read contents of one or more files
- edit_file: Edit or create a file with new content
- grep_files: Search for patterns in files
- glob_files: Find files using glob patterns
- fetch_url: Fetch content from a URL

Always be helpful and provide clear explanations of what you're doing."""

    agent = Agent(
        model=model,
        tools=[
            list_files,
            read_file,
            edit_file,
            grep_files,
            glob_files,
            fetch_url,
            get_agent_tasks,
        ],
        system_prompt=system_prompt,
        name="Code Agent",
        description="AI assistant for code and file operations",
    )

    return agent
