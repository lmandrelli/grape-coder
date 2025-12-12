import os
import re
import xml.etree.ElementTree as ET

from strands import Agent, tool
from strands.multiagent.base import MultiAgentBase

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_conversation_tracker, get_tool_tracker
from grape_coder.nodes.noinput import NoInputGraphNode
from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)


def create_svg_agent(work_path: str) -> MultiAgentBase:
    """Create an agent for creating and validating SVG graphics"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.SVG)

    # Create agent with SVG creation and validation tools
    system_prompt = """You are an SVG specialist working in a multi-agent system.

CONTEXT:
You are part of a collaborative multi-agent workflow dedicated to creating complete websites.
You will receive a list of specific tasks to accomplish.
Your sole responsibility is to create and validate SVG graphics by writing SVG (.svg) files.

YOUR ROLE:
Generate well-structured, optimized, and accessible SVG graphics based on the tasks you receive.
Each task will specify what graphics or icons need to be created (e.g., logos, icons, illustrations, etc.).

IMPORTANT CONSTRAINTS:
- You can ONLY create and edit SVG (.svg) files
- All files you create MUST have the .svg extension
- You are NOT allowed to create files with other extensions (e.g., .html, .js, .png, .jpg)
- If you need to create multiple graphics, organize them in separate .svg files
- Each .svg files should only contain one graphic or icon

Available tools:
- list_files_svg: List files and directories in the svg folder
- read_file_svg: Read contents of one or more SVG files from the svg folder
- edit_file_svg: Rewrite or create an SVG file (ONLY .svg files allowed), automatically validates SVG syntax and will return an error if the SVG is not properly formatted
- grep_files_svg: Search for patterns in SVG files in the svg folder
- glob_files_svg: Find SVG files using glob patterns in the svg folder

Best practices for SVG creation:
- Use semantic and meaningful IDs for elements
- Optimize for file size (remove unnecessary elements, use efficient paths)
- Ensure accessibility with proper titles and descriptions
- Use viewBox for scalability and responsiveness
- Group related elements with <g> tags
- Use CSS within SVG for styling when appropriate
- Consider browser compatibility
- Use proper namespace declarations
- Implement proper color contrast for accessibility

SVG STRUCTURE REQUIREMENTS:
- Always include proper XML declaration: <?xml version="1.0" encoding="UTF-8"?>
- Include SVG namespace: xmlns="http://www.w3.org/2000/svg"
- Set appropriate viewBox for scalability
- Add <title> and <desc> elements for accessibility
- Use semantic structure and grouping

WORKFLOW:
1. Read the task list you receive
2. For each task, understand what graphics or icons are needed
3. Create appropriate .svg files with well-structured, optimized code
4. The edit_file_svg tool automatically validates SVG syntax - if validation fails, fix the XML/SVG errors and try again
5. Ensure graphics are accessible and performant

Always output clean, well-documented, production-ready SVG code that passes validation.
"""
    agent = Agent(
        model=model,
        tools=[
            list_files_svg,
            read_file_svg,
            edit_file_svg,
            grep_files_svg,
            glob_files_svg,
        ],
        system_prompt=system_prompt,
        name=AgentIdentifier.SVG,
        description=get_agent_description(AgentIdentifier.SVG),
        hooks=[
            get_tool_tracker(AgentIdentifier.SVG),
            get_conversation_tracker(AgentIdentifier.SVG),
        ],
    )

    return NoInputGraphNode(agent=agent)


@tool
def list_files_svg(path: str = ".", recursive: bool = False) -> str:
    path = os.path.join("svg", path)
    return list_files(path, recursive)


@tool
def read_file_svg(path: str) -> str:
    path = os.path.join("svg", path)
    return read_file(path)


@tool
def edit_file_svg(path: str, content: str) -> str:
    """Edit or create an SVG file. Only .svg files are allowed."""
    # Validate that the file has .svg extension
    if not path.endswith(".svg"):
        return f"ERROR: You are only allowed to create and edit SVG (.svg) files. The path '{path}' does not have a .svg extension. Please use a .svg file instead."

    # Validate SVG content
    is_valid, error_message = is_valid_svg(content)
    if not is_valid:
        return f"ERROR: Invalid SVG content: {error_message}. Please fix the SVG syntax and try again."

    path = os.path.join("svg", path)
    return edit_file(path, content)


@tool
def grep_files_svg(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    path = os.path.join("svg", path)
    return grep_files(pattern, path, file_pattern)


@tool
def glob_files_svg(pattern: str, path: str = ".") -> str:
    path = os.path.join("svg", path)
    return glob_files(pattern, path)


def is_valid_svg(svg_content: str) -> tuple[bool, str]:
    """
    Validate if the given string is a valid SVG.

    Args:
        svg_content: The SVG content to validate

    Returns:
        tuple: (is_valid, error_message)
    """
    if not svg_content or not isinstance(svg_content, str):
        return False, "SVG content must be a non-empty string"

    # Check if it contains basic SVG structure
    if not svg_content.strip().startswith("<"):
        return False, "SVG content must start with '<' (XML opening tag)"

    # Check for SVG namespace or root element
    svg_patterns = [
        r'<svg[^>]*xmlns="http://www\.w3\.org/2000/svg"',
        r"<svg[^>]*xmlns=\'http://www\.w3\.org/2000/svg\'",
        r"<svg[^>]*>",  # Basic SVG tag without namespace
    ]

    has_svg_root = any(
        re.search(pattern, svg_content, re.IGNORECASE) for pattern in svg_patterns
    )
    if not has_svg_root:
        return False, "SVG must have a root <svg> element with proper namespace"

    # Try to parse as XML
    try:
        # Remove potential BOM and normalize whitespace
        content = svg_content.strip()
        if content.startswith("\ufeff"):
            content = content[1:]

        # Parse the XML
        ET.fromstring(content)
        return True, "Valid SVG"

    except ET.ParseError as e:
        return False, f"Invalid XML/SVG syntax: {str(e)}"
    except Exception as e:
        return False, f"SVG validation error: {str(e)}"
