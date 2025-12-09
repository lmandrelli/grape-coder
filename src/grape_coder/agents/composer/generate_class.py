import os

from strands import Agent, tool

from grape_coder.config.manager import get_config_manager
from grape_coder.tools.agents import get_agent_tasks
from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
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

    model = ProviderFactory.create_model(provider_config, agent_config.model_name).model

    # Create agent with class creation tools
    system_prompt = """You are a CSS class specialist.
Your role is to create reusable, well-structured CSS classes.

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

Always output clean, well-documented code.

Use tools to create all css files in . folder.
"""

    return Agent(
        model=model,
        tools=[
            list_files_css,
            read_file_css,
            edit_file_css,
            grep_files_css,
            glob_files_css,
            get_agent_tasks,
        ],
        system_prompt=system_prompt,
        name="class_generator",
        description="AI assistant for creating reusable CSS classes and components",
    )


@tool
def list_files_css(path: str = ".", recursive: bool = False) -> str:
    path = os.path.join("style", path)
    return list_files(path, recursive)


@tool
def read_file_css(path: str) -> str:
    path = os.path.join("style", path)
    return read_file(path)


@tool
def edit_file_css(path: str, content: str) -> str:
    path = os.path.join("style", path)
    return edit_file(path, content)


@tool
def grep_files_css(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    path = os.path.join("style", path)
    return grep_files(pattern, path, file_pattern)


@tool
def glob_files_css(pattern: str, path: str = ".") -> str:
    path = os.path.join("style", path)
    return glob_files(pattern, path)
