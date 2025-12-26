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


def create_code_revision_agent(
    work_path: str, agent_id: AgentIdentifier
) -> MultiAgentBase:
    """Create a code revision agent specialized in fixing review feedback"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = cast(Model, config_manager.get_model(agent_id))

    # Create agent with file system tools
    system_prompt = f"""You are a Code Revision Specialist working in a multi-agent web development system.

CONTEXT:
A code reviewer has analyzed the website code and provided feedback containing:
1. A REVIEW SUMMARY (inside <review_summary> XML tag) - brief overview of main issues
2. TASKS TO FIX organized by priority with specific issues to address

Your role is to address each issue raised in the review and improve the code quality.

YOUR TASK:
You will receive a review summary and a task list.
Your responsibilities are:
1. First, read the review summary inside <review_summary> to understand the overall assessment
2. Then, follow the task list to address each issue in order
3. First tasks are the most important - fix them first
4. Review the affected files to understand the current implementation
5. Make the necessary corrections to address each task
6. Ensure your fixes don't break other functionality
7. Re-test the changes by reading the modified files

WORKFLOW:
1. Read the review summary (inside <review_summary> tag) first for context
2. Follow the task list to fix issues in order (first tasks = highest priority)
3. For each task mentioned:
    a. Find and read the relevant files
    b. Understand what needs to be changed
    c. Make the necessary edits
    d. Verify the changes address the issue

GOAL:
Fix all issues in the task list to improve the code quality.

Available tools:
- list_files: List files and directories in a path (automatically called at startup)
- read_file: Read contents of one or more files
- edit_file: Rewrite or create a file with new content
- grep_files: Search for patterns in files
- glob_files: Find files using glob patterns
- fetch_url: Fetch content from a URL

The workspace exploration will be automatically provided to you at the start.
"""

    return WorkspaceExplorerNode(
        model=model,
        system_prompt=system_prompt,
        work_path=work_path,
        tools=[
            list_files,
            read_file,
            edit_file_code,
            grep_files,
            glob_files,
            fetch_url,
            search,
        ],
        agent_id=agent_id,
        hooks=[
            get_tool_tracker(agent_id),
            get_conversation_tracker(agent_id),
            get_tool_limit_hook(agent_id),
        ],
    )


@tool
def edit_file_code(path: str, content: str) -> str:
    """Edit or create a web file. Only .html, .js, .css, .svg, .json and .md files are allowed."""
    # Validate that the file has an allowed extension
    allowed_extensions = (".html", ".js", ".css", ".svg", ".json", ".md")
    if not path.endswith(allowed_extensions):
        return f"ERROR: You are only allowed to create and edit web files with extensions: .html, .js, .css, .svg, .json, .md. The path '{path}' does not have an allowed extension."

    return edit_file(path, content)


class WorkspaceExplorerNode(MultiAgentBase):
    """Custom node that automatically explores the workspace before processing tasks"""

    def __init__(
        self,
        model,
        system_prompt,
        work_path: str,
        tools,
        agent_id,
        hooks=None,
    ):
        super().__init__()
        self.model = model
        self.system_prompt = system_prompt
        self.work_path = work_path
        self.tools = tools
        self.agent_id = agent_id
        self.hooks = hooks or []

    def _create_agent(self) -> Agent:
        return Agent(
            model=self.model,
            tools=self.tools,
            system_prompt=self.system_prompt,
            name=self.agent_id,
            description=get_agent_description(self.agent_id),
            hooks=self.hooks,
        )

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Execute workspace exploration before main task"""
        try:
            agent = self._create_agent()

            # First, explore the workspace
            exploration_result = list_files(path=self.work_path, recursive=True)

            # Extract structured feedback from state (contains summary + tasks)
            structured_tasks = ""

            # Try to extract from review_agent (has review_output with get_feedback_for_revision)
            if "state" in kwargs:
                state = kwargs["state"]
                if hasattr(state, "results") and "review_agent" in state.results:
                    review_result_node = state.results["review_agent"]
                    if hasattr(review_result_node, "result") and hasattr(
                        review_result_node.result, "state"
                    ):
                        review_state = review_result_node.result.state
                        if isinstance(review_state, dict):
                            review_output = review_state.get("review_output")
                            if review_output and hasattr(
                                review_output, "get_feedback_for_revision"
                            ):
                                structured_tasks = (
                                    review_output.get_feedback_for_revision()
                                )

            # Build enhanced prompt with workspace context, natural review, and structured tasks
            workspace_context = f"""WORKSPACE EXPLORATION RESULTS:
{exploration_result}
"""

            if structured_tasks:
                workspace_context += f"""
=== REVIEW FEEDBACK ===
{structured_tasks}

"""

            workspace_context += f"Now proceed with fixing the issues:\n{task}"

            # Execute the main task with workspace context
            response = await agent.invoke_async(workspace_context)

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
