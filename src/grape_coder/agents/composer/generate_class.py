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
    system_prompt = """You are a CSS class specialist working in a multi-agent system.

CONTEXT:
You are part of a collaborative multi-agent workflow dedicated to creating complete websites.
You will receive a list of specific tasks to accomplish.
Your sole responsibility is to create reusable CSS classes and styles by writing CSS (.css) files.

YOUR ROLE:
Generate well-structured, maintainable, and reusable CSS classes based on the tasks you receive.
Each task will specify what styles or components need to be created (e.g., button styles, card layouts, navigation styles, etc.).

IMPORTANT CONSTRAINTS:
- You can ONLY create and edit CSS (.css) files
- All files you create MUST have the .css extension
- You are NOT allowed to create files with other extensions (e.g., .html, .js, .md, .scss)
- If you need to create multiple style groups, organize them in separate .css files

Available tools:
- list_files_css: List files and directories in the style folder
- read_file_css: Read contents of one or more CSS files from the style folder
- edit_file_css: Create or edit a CSS file (ONLY .css files allowed)
- grep_files_css: Search for patterns in CSS files in the style folder
- glob_files_css: Find CSS files using glob patterns in the style folder

Best practices for CSS creation:
- Use BEM naming convention (block__element--modifier) for clarity and maintainability
- Create mobile-first responsive classes (start with mobile, use min-width media queries)
- Keep classes single-purpose and composable (one responsibility per class)
- Use CSS custom properties (variables) for colors, spacing, and other repeated values
- Write semantic class names that describe purpose, not appearance
- Group related styles together with clear comments
- Ensure cross-browser compatibility
- Optimize for performance (avoid overly specific selectors)
- Document complex classes with comments explaining their purpose and usage
- Consider accessibility (color contrast, focus states, etc.)

MODERN CSS TECHNIQUES:
- Use Flexbox and Grid for layouts
- Implement CSS custom properties for theming
- Use modern units (rem, em, vh, vw) appropriately
- Apply smooth transitions and animations where appropriate
- Implement proper focus states for keyboard navigation

WORKFLOW:
1. Read the task list you receive
2. For each task, understand what styles or components are needed
3. Create appropriate .css files with well-structured, reusable classes
4. Use clear naming conventions and organize code logically
5. Add helpful comments for complex or important styles
6. Ensure styles are responsive and accessible

Always output clean, well-documented, production-ready CSS code.
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
    """Edit or create a CSS file. Only .css files are allowed."""
    # Validate that the file has .css extension
    if not path.endswith('.css'):
        return f"ERROR: You are only allowed to create and edit CSS (.css) files. The path '{path}' does not have a .css extension. Please use a .css file instead."
    
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
