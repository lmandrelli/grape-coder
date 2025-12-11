import os
import re
import xml.etree.ElementTree as ET
from io import StringIO

from strands import Agent, tool

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_tool_tracker
from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)


def create_svg_agent(work_path: str) -> Agent:
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

Available tools:
- list_files_svg: List files and directories in the svg folder
- read_file_svg: Read contents of one or more SVG files from the svg folder
- edit_file_svg: Create or edit an SVG file (ONLY .svg files allowed), will send back an error if svg not built correctly
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
4. If validation fails, fix the errors and re-validate
5. Ensure graphics are accessible and performant

Always output clean, well-documented, production-ready SVG code that passes validation.
"""
    return Agent(
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
        hooks=[get_tool_tracker(AgentIdentifier.SVG)],
    )


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

    path = os.path.join("svg", path)
    return edit_file(path, content)


@tool
def validate_svg(path: str) -> str:
    """Validate SVG file for syntax and structure errors."""
    path = os.path.join("svg", path)

    try:
        # Read the SVG file
        content = read_file(path)

        # Basic XML structure validation
        if not content.strip().startswith("<?xml"):
            return 'WARNING: Missing XML declaration. Recommended: <?xml version="1.0" encoding="UTF-8"?>'

        if 'xmlns="http://www.w3.org/2000/svg"' not in content:
            return 'ERROR: Missing SVG namespace. Required: xmlns="http://www.w3.org/2000/svg"'

        # Parse XML to check for well-formedness
        try:
            ET.parse(StringIO(content))
        except ET.ParseError as e:
            return f"ERROR: XML parsing failed - {str(e)}"

        # Check for accessibility elements
        if "<title>" not in content:
            return "WARNING: Missing <title> element for accessibility"

        if "<desc>" not in content:
            return "WARNING: Missing <desc> element for accessibility"

        # Check for viewBox
        if "viewBox=" not in content:
            return "WARNING: Missing viewBox attribute for scalability"

        # Check for common SVG elements
        svg_elements = [
            "<rect",
            "<circle",
            "<ellipse",
            "<line",
            "<polyline",
            "<polygon",
            "<path",
            "<text",
        ]
        has_content = any(element in content for element in svg_elements)
        if not has_content:
            return "WARNING: SVG appears to be empty (no visible elements found)"

        # Check for proper closing tags
        open_tags = re.findall(r"<(\w+)[^>/]*?>", content)
        self_closing = re.findall(r"<(\w+)[^>]*/>", content)

        for tag in open_tags:
            if tag not in self_closing and not re.search(f"</{tag}>", content):
                return f"ERROR: Unclosed tag detected: <{tag}>"

        return "SUCCESS: SVG file is valid and well-structured"

    except FileNotFoundError:
        return f"ERROR: SVG file not found at {path}"
    except Exception as e:
        return f"ERROR: Unexpected validation error - {str(e)}"


@tool
def grep_files_svg(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    path = os.path.join("svg", path)
    return grep_files(pattern, path, file_pattern)


@tool
def glob_files_svg(pattern: str, path: str = ".") -> str:
    path = os.path.join("svg", path)
    return glob_files(pattern, path)
