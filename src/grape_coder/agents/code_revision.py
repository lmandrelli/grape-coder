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
A code reviewer has analyzed the website code and provided structured feedback on issues that need to be fixed.
Your role is to address each issue raised in the review and improve the code quality.

YOUR TASK:
You will receive REVIEW FEEDBACK with categories and specific issues to fix.
Your responsibilities are:
1. Carefully read each category and its remarks
2. Focus on BLOCKING ISSUES first (critical problems that must be fixed)
3. Review the affected files to understand the current implementation
4. Make the necessary corrections to address each remark
5. Ensure your fixes don't break other functionality
6. Re-test the changes by reading the modified files

REVIEW CATEGORIES:
- PROMPT_COMPLIANCE: Does the code fulfill the original user requirements?
- CODE_VALIDITY: Is the code syntactically correct and free of bugs?
- INTEGRATION: Are all files properly linked and working together?
- RESPONSIVENESS: Does the layout work across different screen sizes?
- COMPLETENESS: Are all features implemented and functional?
- BEST_PRACTICES: Does the code follow modern web development standards?

WORKFLOW:
1. Read the review feedback carefully (it will be provided to you)
2. For each issue mentioned:
   a. Find and read the relevant files
   b. Understand what needs to be changed
   c. Make the necessary edits
   d. Verify the changes address the issue
3. Ensure blocking issues are resolved first
4. Focus on categories with scores below 18/20

GOAL:
Improve the code until all categories would score >= 18/20 and no blocking issues remain.

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
    """Edit or create a web file. Only .html, .js, .css, .svg, .json and .md files are allowed."""
    # Validate that the file has an allowed extension
    allowed_extensions = (".html", ".js", ".css", ".svg", ".json", ".md")
    if not path.endswith(allowed_extensions):
        return f"ERROR: You are only allowed to create and edit web files with extensions: .html, .js, .css, .svg, .json, .md. The path '{path}' does not have an allowed extension."

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

            # Extract feedback from invocation_state if available
            feedback = ""
            if invocation_state and isinstance(invocation_state, dict):
                feedback = invocation_state.get("feedback_for_code_agent", "")
                # Also try to extract from kwargs['state'] (GraphState)
                if not feedback and "state" in kwargs:
                    state = kwargs["state"]
                    if hasattr(state, "results") and "quality_checker" in state.results:
                        checker_result = state.results["quality_checker"]
                        if hasattr(checker_result, "result") and hasattr(
                            checker_result.result, "state"
                        ):
                            feedback = checker_result.result.state.get(
                                "feedback_for_code_agent", ""
                            )

            # Build enhanced prompt with workspace context and feedback
            workspace_context = f"""WORKSPACE EXPLORATION RESULTS:
{exploration_result}
"""

            if feedback:
                workspace_context += f"""
REVIEW FEEDBACK TO ADDRESS:
{feedback}

"""

            workspace_context += f"Now proceed with fixing the issues:\n{task}"

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
