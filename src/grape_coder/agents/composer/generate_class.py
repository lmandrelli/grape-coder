import os

from strands import Agent, tool
from strands.multiagent.base import MultiAgentBase

from grape_coder.config import get_config_manager
from grape_coder.nodes.taskfiltering import TaskFilteringNode
from grape_coder.agents.identifiers import AgentIdentifier

from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)


def create_class_agent(work_path: str) -> MultiAgentBase:
    """Create an agent for creating reusable CSS classes and HTML components"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.GENERATE_CLASS)

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
    agent =  Agent(
        model=model,
        tools=[
            list_files_css,
            read_file_css,
            edit_file_css,
            grep_files_css,
            glob_files_css,
        ],
        system_prompt=system_prompt,
        name="class_generator",
        description="AI assistant for creating reusable CSS classes and components",
    )
    return TaskFilteringNode(agent=agent, agent_xml_tag="class_agent")


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
