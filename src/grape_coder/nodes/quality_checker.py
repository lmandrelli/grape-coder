"""Quality Checker Node for the review loop.

This node checks the review result and determines if the code needs revision
or if it can proceed to completion.
"""

from strands.agent.agent_result import AgentResult
from strands.multiagent import MultiAgentBase, MultiAgentResult
from strands.multiagent.base import NodeResult, Status
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.tools.tool_limit_tracker import reset_agent_count


class QualityChecker(MultiAgentBase):
    """Custom node that evaluates review results and decides if revision is needed.

    For now, this always returns needs_revision=True (not approved).
    The loop will exit via set_max_node_executions limit.
    
    In the future, this can be enhanced to:
    - Parse the reviewer's feedback
    - Check for specific approval keywords
    - Count iterations and approve after N cycles
    - Use an LLM to evaluate quality
    """

    def __init__(self):
        super().__init__()
        self.name = "quality_checker"
        self.iteration = 0

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Evaluate the review result and decide next step.
        
        Args:
            task: The task/review feedback from the reviewer agent
            invocation_state: State from previous invocations
            **kwargs: Additional arguments
            
        Returns:
            MultiAgentResult with approved state for conditional edges
        """
        self.iteration += 1
        
        # For now, always request revision (not approved)
        # The loop will exit via set_max_node_executions
        approved = False
        
        if approved:
            msg = f"✅ Iteration {self.iteration}: APPROVED - Code meets quality standards"
        else:
            msg = f"⚠️ Iteration {self.iteration}: NEEDS REVISION - Please apply the review feedback"
            # Reset tool counts for agents that will be revisited in the loop
            # This allows them to use their full tool quota again
            reset_agent_count(AgentIdentifier.CODE.value)
            reset_agent_count(AgentIdentifier.REVIEW.value)

        agent_result = AgentResult(
            stop_reason="end_turn",
            message=Message(role="assistant", content=[ContentBlock(text=msg)]),
            metrics=None,
            state={"approved": approved, "iteration": self.iteration},
        )

        return MultiAgentResult(
            status=Status.COMPLETED,
            results={
                self.name: NodeResult(
                    result=agent_result,
                    execution_time=10,
                    status=Status.COMPLETED,
                )
            },
            execution_count=1,
            execution_time=10,
        )
