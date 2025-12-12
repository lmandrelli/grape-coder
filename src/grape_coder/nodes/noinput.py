from typing import Any

from strands import Agent
from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message


class NoInputGraphNode(MultiAgentBase):
    """
    A Custom Node that removes the input propagation in graph.
    """

    def __init__(self, agent: Agent):
        super().__init__()
        self.agent = agent

    async def invoke_async(
        self,
        task: str | list[ContentBlock],
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> MultiAgentResult:
        """Execute task dequeuing and agent invocation"""

        # Remove input propagation
        task = task[1:]

        # Convert task to string if it's a ContentBlock list
        task_str = task if isinstance(task, str) else str(task)

        # If no tasks remain, return completed result
        if len(task) == 0:
            agent_result = AgentResult(
                stop_reason="end_turn",
                state=Status.COMPLETED,
                metrics=EventLoopMetrics(),
                message=Message(
                    role="assistant",
                    content=[ContentBlock(text="No tasks remaining to process.")],
                ),
            )

            return MultiAgentResult(
                status=Status.COMPLETED,
                results={
                    "task_dequeuer": NodeResult(
                        result=agent_result, status=Status.COMPLETED
                    )
                },
            )

        # Invoke the agent with remaining tasks
        try:
            agent_response = await self.agent.invoke_async(task_str)

            return MultiAgentResult(
                status=Status.COMPLETED,
                results={
                    "task_dequeuer": NodeResult(
                        result=agent_response, status=Status.COMPLETED
                    )
                },
            )

        except Exception as e:
            # Handle agent invocation errors
            agent_result = AgentResult(
                stop_reason="guardrail_intervened",
                state=Status.FAILED,
                metrics=EventLoopMetrics(),
                message=Message(
                    role="assistant",
                    content=[ContentBlock(text=f"Error invoking agent: {str(e)}")],
                ),
            )

            return MultiAgentResult(
                status=Status.FAILED,
                results={
                    "task_dequeuer": NodeResult(
                        result=agent_result, status=Status.FAILED
                    )
                },
            )
