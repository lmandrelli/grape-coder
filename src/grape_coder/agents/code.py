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


def create_code_agent(work_path: str) -> MultiAgentBase:
    """Create a code agent with file system tools"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = cast(Model, config_manager.get_model(AgentIdentifier.CODE))

    # Create agent with file system tools
    system_prompt = """You are a code assistant with access to file system tools.
You can list files, read files, edit/create files, search for content, use glob patterns, and fetch web content.

Available tools:
- list_files: List files and directories in a path
- read_file: Read contents of one or more files
- edit_file: Edit or create a file with new content
- grep_files: Search for patterns in files
- glob_files: Find files using glob patterns
- fetch_url: Fetch content from a URL

Before doing anything list files to see what have been done.
Use tools to create all css files in . folder.
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
        name=AgentIdentifier.CODE,
        description=get_agent_description(AgentIdentifier.CODE),
    )

    return CodeNode(agent=agent)


class CodeNode(MultiAgentBase):
    def __init__(self, agent):
        super().__init__()
        self.agent = agent

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        # task comes from the previous node (Orchestrator's XML output)
        task = task if isinstance(task, str) else str(task)

        response = await self.agent.invoke_async(task)

        agent_result = AgentResult(
            stop_reason="end_turn",
            state=Status.COMPLETED,
            metrics=EventLoopMetrics(),
            message=Message(role="assistant", content=[ContentBlock(text=response)]),
        )

        return MultiAgentResult(
            status=Status.COMPLETED,
            results={"code": NodeResult(result=agent_result, status=Status.COMPLETED)},
        )
