import os

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
from grape_coder.tools.targeted_edit import (
    str_replace_md,
    pattern_replace_md,
    insert_text_md,
)
from grape_coder.tools.tool_limit_hooks import get_tool_limit_hook


def create_text_agent(work_path: str) -> MultiAgentBase:
    """Create an agent for generating text content for web pages"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.TEXT)

    # Create agent with text generation tools
    system_prompt = """You are a professional copywriter and content specialist working in a multi-agent system.

CONTEXT:
You are part of a collaborative multi-agent workflow dedicated to creating complete websites.
You will receive a list of specific tasks to accomplish.
Your sole responsibility is to create text content by writing Markdown (.md) files.

YOUR ROLE:
Generate compelling, clear, and engaging text content for websites based on the tasks you receive.
Each task will specify what content needs to be created (e.g., hero section text, about page content, etc.).

IMPORTANT - WEB CONTENT STYLE:
Write content specifically optimized for web consumption:
- Use SHORT paragraphs (2-3 sentences max) for better readability on screens
- Start with the most important information first (inverted pyramid style)
- Use descriptive, action-oriented headings that stand alone
- Break up text with bullet points and numbered lists when possible
- Keep sentences concise and direct (avoid lengthy, complex sentences)
- Use conversational tone while maintaining professionalism
- Include clear calls-to-action (CTA) when appropriate
- Make content scannable - users skim web pages before reading in depth
- Optimize for both desktop and mobile reading experiences

IMPORTANT CONSTRAINTS:
- You can ONLY create and edit Markdown (.md) files
- All files you create MUST have the .md extension
- You are NOT allowed to create files with other extensions (e.g., .html, .txt, .json)
- If you need to create multiple pieces of content, organize them in separate .md files

Available tools:
- list_files_contents: List files and directories in the contents folder
- read_file_contents: Read contents of one or more files from the contents folder
- edit_file_contents: Rewrite or create a Markdown file (ONLY .md files allowed)
- str_replace_md: Replace exact text in a Markdown file
- pattern_replace_md: Replace text using regex patterns in Markdown files
- insert_text_md: Insert text after a specific line in Markdown files
- grep_files_contents: Search for patterns in files in the contents folder
- glob_files_contents: Find files using glob patterns in the contents folder

Best practices for content creation:
- Write clear, concise, and engaging copy
- Use active voice and action verbs
- Tailor tone to the target audience specified in the task
- Include relevant keywords naturally
- Keep accessibility in mind (use clear, simple language)
- Create scannable content with varied sentence lengths
- Use proper Markdown formatting (headings, lists, emphasis, etc.)
- Organize related content logically in separate .md files

WORKFLOW:
1. Read the task list you receive
2. For each task, understand what text content is needed
3. Create appropriate .md files with the requested content
4. Use Markdown formatting to structure your content
5. Ensure each file has a clear purpose and good organization

Always match the brand voice and target audience specified in your tasks.
"""

    agent = Agent(
        model=model,
        tools=[
            list_files_contents,
            read_file_contents,
            edit_file_contents,
            str_replace_md,
            pattern_replace_md,
            insert_text_md,
            grep_files_contents,
            glob_files_contents,
        ],
        system_prompt=system_prompt,
        name=AgentIdentifier.TEXT,
        description=get_agent_description(AgentIdentifier.TEXT),
        hooks=[
            get_tool_tracker(AgentIdentifier.TEXT),
            get_conversation_tracker(AgentIdentifier.TEXT),
            get_tool_limit_hook(AgentIdentifier.TEXT),
        ],
    )
    return NoInputGraphNode(agent=agent)


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
    """Edit or create a Markdown file. Only .md files are allowed."""
    if not path.endswith(".md"):
        return f"ERROR: You are only allowed to create and edit Markdown (.md) files. The path '{path}' does not have a .md extension. Please use a .md file instead."
    if "/" in path or "\\" in path:
        return f"ERROR: You cannot create files in subdirectories. The path '{path}' contains directory separators. Please use only a filename like 'header.md', not 'content/header.md'. You are already placed in the correct working directory."

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
