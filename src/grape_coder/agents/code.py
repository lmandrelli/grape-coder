from typing import cast

from strands import Agent, tool
from strands.agent import AgentResult
from strands.models.model import Model
from strands.multiagent import MultiAgentResult
from strands.multiagent.base import MultiAgentBase, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_conversation_tracker, get_tool_tracker
from grape_coder.tools.web import fetch_url, search
from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)
from grape_coder.tools.tool_limit_hooks import get_tool_limit_hook


def create_code_agent(work_path: str, agent_id: AgentIdentifier) -> MultiAgentBase:
    """Create a code agent with file system tools"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = cast(Model, config_manager.get_model(agent_id))

    # Create agent with file system tools
    system_prompt = f"""You are a code assistant specialized in web development, working as part of a multi-agent system for generating websites.

    CONTEXT:
    You are working in a multi-agent pipeline designed to generate complete websites. Other specialized agents have already prepared the groundwork:
    - CSS/styling agents have created style files (.css) for components
    - Content agents have generated text files (.txt) with copy and content
    - Graphics agents have created SVG files (.svg) with icons, logos, and illustrations
    - Additional agents may have created other web resources (images, data files, etc.)

    WORKFLOW:
    You will receive a list of specific tasks to accomplish from an {AgentIdentifier.ORCHESTRATOR}.
    Your role is to:
    1. First, explore the working directory to understand what has been prepared by previous agents
    2. Read and understand the generated files (CSS, text content, SVG graphics, etc.)
    3. Use these prepared resources to complete the tasks you've been assigned
    4. Integrate all resources into cohesive, production-ready web code
    5. Create the final website deliverables (HTML, JavaScript, etc.) that properly reference and use the prepared assets including SVG graphics

    KEY POINT: The files created by other agents are YOUR RESOURCES to complete your assigned tasks.
    Read them, understand them, and incorporate them into your web development work to fulfill the task list.
    Maybe some files are incomplete, create new one or rewrite them to add missing logic. Especially style files may need additional classes to style the page correctly.
    Your goal is to produce a functional, well-structured website that integrates all the prepared components.

    Available tools:
    - list_files: List files and directories in a path (automatically called at startup)
    - read_file: Read contents of one or more files
    - edit_file: Rewrite or create a file with new content
    - grep_files: Search for patterns in files
    - glob_files: Find files using glob patterns
    - fetch_url: Fetch content from a URL

    The workspace exploration will be automatically provided to you at the start.
    """

    agent = Agent(
        model=model,
        tools=[
            list_files,
            read_file,
            edit_file_code,
            grep_files,
            glob_files,
            fetch_url,
            search,
        ],
        system_prompt=system_prompt,
        name=agent_id,
        description=get_agent_description(agent_id),
        hooks=[
            get_tool_tracker(agent_id),
            get_conversation_tracker(agent_id),
            get_tool_limit_hook(agent_id),
        ],
    )

    return WorkspaceExplorerNode(agent=agent, work_path=work_path)


@tool
def edit_file_code(path: str, content: str) -> str:
    """Edit or create a web file. Only .html, .js, .css, and .md files are allowed."""
    # Validate that the file has an allowed extension
    allowed_extensions = (".html", ".js", ".css", ".md")
    if not path.endswith(allowed_extensions):
        return f"ERROR: You are only allowed to create and edit web files with extensions: .html, .js, .css, .md. The path '{path}' does not have an allowed extension."

    return edit_file(path, content)


class WorkspaceExplorerNode(MultiAgentBase):
    """Custom node that automatically explores the workspace before processing tasks"""

    def __init__(self, agent: Agent, work_path: str):
        super().__init__()
        self.agent = agent
        self.work_path = work_path

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Execute workspace exploration before main task"""
        try:
            # First, explore the workspace
            exploration_result = list_files(path=self.work_path, recursive=True)

            # Build enhanced prompt with workspace context
            workspace_context = f"""WORKSPACE EXPLORATION RESULTS:
{exploration_result}

Now proceed with your task:
{task}"""

            # Execute the main task with workspace context
            response = await self.agent.invoke_async(workspace_context)

            # Return successful result
            agent_result = AgentResult(
                stop_reason="end_turn",
                state=Status.COMPLETED,
                metrics=EventLoopMetrics(),
                message=response.message
                if hasattr(response, "message")
                else Message(
                    role="assistant", content=[ContentBlock(text=str(response))]
                ),
            )

            return MultiAgentResult(
                status=Status.COMPLETED,
                results={
                    "workspace_explorer": NodeResult(
                        result=agent_result, status=Status.COMPLETED
                    )
                },
            )

        except Exception as e:
            agent_result = AgentResult(
                stop_reason="guardrail_intervened",
                state=Status.FAILED,
                metrics=EventLoopMetrics(),
                message=Message(
                    role="assistant",
                    content=[ContentBlock(text=f"Error: {str(e)}")],
                ),
            )

            return MultiAgentResult(
                status=Status.FAILED,
                results={
                    "workspace_explorer": NodeResult(
                        result=agent_result, status=Status.FAILED
                    )
                },
            )
