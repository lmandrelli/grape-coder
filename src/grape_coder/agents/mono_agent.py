from typing import cast

from strands import Agent
from strands.agent import AgentResult
from strands.models.model import Model
from strands.multiagent import MultiAgentResult
from strands.multiagent.base import MultiAgentBase, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.tools.web import fetch_url
from grape_coder.tools.work_path import (
    edit_file,
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)


def create_mono_agent(work_path: str) -> MultiAgentBase:
    """Create a mono-agent with file system tools"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = cast(Model, config_manager.get_model(AgentIdentifier.MONO_AGENT))

    # Create agent with file system tools
    system_prompt = """You are a code assistant specialized in web development and general programming tasks.

WORKFLOW:
Your role is to:
1. First, explore the working directory to understand the current project structure
2. Read and understand existing files to get context
3. Complete the task you've been assigned based on the user's prompt
4. Create, modify, or integrate code as needed to fulfill the request
5. Ensure your solution is functional, well-structured, and follows best practices

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
            edit_file,
            grep_files,
            glob_files,
            fetch_url,
        ],
        system_prompt=system_prompt,
        name=AgentIdentifier.MONO_AGENT,
        description=get_agent_description(AgentIdentifier.MONO_AGENT),
    )

    return MonoAgentNode(agent=agent, work_path=work_path)


class MonoAgentNode(MultiAgentBase):
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
