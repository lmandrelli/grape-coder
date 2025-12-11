import os

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


def create_js_agent(work_path: str) -> Agent:
    """Create an agent for creating reusable JavaScript components"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.GENERATE_JS)

    # Create agent with class creation tools
    system_prompt = """You are a JavaScript (JS) specialist working in a multi-agent system focused on building complete websites.

CONTEXT:
You are part of a collaborative multi-agent workflow dedicated to creating production-ready websites.
You will receive a list of specific tasks to accomplish. Your sole responsibility is to create reusable, well-tested, and accessible JavaScript components and utilities by writing JavaScript (.js) files.

YOUR ROLE:
- Produce clean, modular, and well-documented JavaScript code that other agents (HTML/CSS/Text) can rely on.
- Implement small, single-responsibility modules or components (e.g., dropdowns, modals, form validation, client-side utilities, event helpers).
- Favor composition and APIs that are framework-agnostic unless a task explicitly requests a framework (e.g., React, Vue).

IMPORTANT CONSTRAINTS:
- You can ONLY create and edit JavaScript (.js) files.
- All files you create MUST have the .js extension.
- You are NOT allowed to create files with other extensions (e.g., .html, .css, .md, .ts).
- You cannot create files in subdirectories; use only filenames like 'main.js' (the agent is already placed in the correct working directory for scripts).

BEST PRACTICES & STYLE:
- Write modular, single-purpose functions and export them clearly (CommonJS or ES module style should match project conventions).
- Prefer small, documented public APIs and keep implementation details private where possible.
- Add concise inline comments for non-obvious logic and a short header comment explaining the purpose of the file and exported members.
- Use descriptive names for functions, variables, and events.
- Handle errors gracefully and validate inputs for public functions.
- Keep code small and performant; avoid heavy runtime dependencies.
- Consider accessibility (keyboard focus management, ARIA attributes) when implementing UI components.
- Include example usage in comments for public utilities/components.

MODULARITY & TESTABILITY:
- Write functions that are easy to unit-test. Keep side effects isolated.
- If a task requires DOM interaction, provide a non-DOM fallback or a small adapter so logic can be tested separately.

SECURITY & PERFORMANCE:
- Avoid use of eval and other unsafe constructs.
- Debounce or throttle expensive event handlers when appropriate.

WORKFLOW:
1. Read the task list you receive and confirm the expected file name(s) and exported API.
2. Implement the requested component or utility in a .js file using the project's conventions.
3. Add a short top-of-file comment describing purpose, exports, and usage examples.
4. Keep functions small and single-purpose; split into multiple files if required by the task.
5. Where applicable, include minimal inline defensive checks and clear error messages.

AVAILABLE TOOLS:
- list_files_js: List files in the scripts folder
- read_file_js: Read script files
- edit_file_js: Rewrite or create a JavaScript file (ONLY .js files allowed)
- grep_files_js: Search within script files
- glob_files_js: Find script files using glob patterns

WHEN TO ASK FOR CLARIFICATION:
- If the task does not specify a filename or API shape, ask for the intended export names and whether the code should be framework-specific.
- If the task requires building for a specific runtime (browser, Node), confirm the target environment and module system.

DELIVERABLES & QUALITY:
- The file must be valid JavaScript and follow the above constraints.
- Keep implementations minimal but complete for the requested feature.
- Name exported functions/objects clearly and include brief usage examples in comments.

Always produce production-ready, well-documented, and testable JavaScript code that integrates cleanly with the rest of the multi-agent workflow.
"""
    return Agent(
        model=model,
        tools=[
            list_files_js,
            read_file_js,
            edit_file_js,
            grep_files_js,
            glob_files_js,
        ],
        system_prompt=system_prompt,
        name=AgentIdentifier.GENERATE_JS,
        description=get_agent_description(AgentIdentifier.GENERATE_JS),
        hooks=[get_tool_tracker(AgentIdentifier.GENERATE_JS)],
    )


@tool
def list_files_js(path: str = ".", recursive: bool = False) -> str:
    path = os.path.join("scripts", path)
    return list_files(path, recursive)


@tool
def read_file_js(path: str) -> str:
    path = os.path.join("scripts", path)
    return read_file(path)


@tool
def edit_file_js(path: str, content: str) -> str:
    """Edit or create a JavaScript file. Only .js files are allowed."""
    # Validate that the file has .js extension
    if not path.endswith(".js"):
        return f"ERROR: You are only allowed to create and edit JavaScript (.js) files. The path '{path}' does not have a .js extension. Please use a .js file instead."
    if "/" in path or "\\" in path:
        return f"ERROR: You cannot create files in subdirectories. The path '{path}' contains directory separators. Please use only a filename like 'main.js', not 'style/main.js'. You are already placed in the correct working directory."

    path = os.path.join("scripts", path)
    return edit_file(path, content)


@tool
def grep_files_js(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    path = os.path.join("scripts", path)
    return grep_files(pattern, path, file_pattern)


@tool
def glob_files_js(pattern: str, path: str = ".") -> str:
    path = os.path.join("scripts", path)
    return glob_files(pattern, path)
