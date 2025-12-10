import os

from strands import Agent, tool

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)


def create_text_agent(work_path: str) -> Agent:
    """Create an agent for generating text content for web pages"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.TEXT)

    # Create agent with text generation tools
    system_prompt = """You are a professional copywriter and content specialist.
Your role is to generate compelling, clear, and engaging text content for web pages.

Available tools:
- list_files: List files and directories in a path
- read_file: Read contents of one or more files
- edit_file: Edit or create a file with new content
- grep_files: Search for patterns in files
- glob_files: Find files using glob patterns

Best practices:
- Write clear, concise, and engaging copy
- Use active voice and action verbs
- Tailor tone to the target audience
- Include relevant keywords naturally
- Keep accessibility in mind (clear language)
- Create scannable content with varied sentence lengths
- Organize content in files (e.g., headings.md, paragraphs.md)

Always match the brand voice and target audience specified.

Use tools to create all MarkDown files in . folder.
"""

    return Agent(
        model=model,
        tools=[
            list_files_contents,
            read_file_contents,
            edit_file_contents,
            grep_files_contents,
            glob_files_contents,
        ],
        system_prompt=system_prompt,
        name=AgentIdentifier.TEXT,
        description=get_agent_description(AgentIdentifier.TEXT),
    )


@tool
def list_files_contents(path: str = ".", recursive: bool = False) -> str:
    path = os.path.join("contents", path)
    return list_files(path, recursive)


@tool
def read_file_contents(path: str) -> str:
    path = os.path.join("contents", path)
    return read_file(path)


@tool
def edit_file_contents(path: str, content: str) -> str:
    path = os.path.join("contents", path)
    return edit_file(path, content)


@tool
def grep_files_contents(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    path = os.path.join("contents", path)
    return grep_files(pattern, path, file_pattern)


@tool
def glob_files_contents(pattern: str, path: str = ".") -> str:
    path = os.path.join("contents", path)
    return glob_files(pattern, path)
