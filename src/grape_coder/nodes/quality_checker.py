"""Quality Checker Node for the review loop.

This node checks the review result and determines if the code needs revision
or if it can proceed to completion. It parses the structured XML review
and evaluates approval criteria.
"""

from strands.agent.agent_result import AgentResult
from strands.multiagent import MultiAgentBase, MultiAgentResult
from strands.multiagent.base import NodeResult, Status
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.tools.tool_limit_tracker import reset_agent_count


class QualityChecker(MultiAgentBase):
    """Custom node that evaluates review results and decides if revision is needed.

    This node:
    1. Extracts the ReviewResult from the reviewer's output
    2. Checks for blocking issues
    3. Verifies all category scores meet minimum threshold (18/20)
    4. If not approved, generates feedback for the code agent
    5. Resets tool counts for agents in the revision loop
    """

    def __init__(self):
        super().__init__()
        self.name = "quality_checker"
        self.iteration = 0

    def _extract_review_result(self, task, state):
        """Extract ReviewResult from the reviewer's output.
        
        The reviewer node stores the parsed ReviewResult in the agent result's state.
        """
        # Import here to avoid circular imports
        from grape_coder.agents.composer.reviewer import (
            ReviewResult,
            parse_review_xml,
            extract_review_xml,
        )
        from grape_coder.agents.identifiers import AgentIdentifier
        
        # If task is a list of ContentBlocks, extract text and try to parse XML
        if isinstance(task, list):
            # Try to find text content with valid XML
            for item in task:
                if isinstance(item, dict) and "text" in item:
                    text_content = item["text"]
                    try:
                        xml_content = extract_review_xml(text_content)
                        result = parse_review_xml(xml_content)
                        return result
                    except Exception:
                        # Continue trying other items in the list
                        continue
        
        # Try to get the pre-parsed ReviewResult from the graph state
        # The ReviewValidatorNode stores it in its node result's state with AgentIdentifier.REVIEW key
        if state and isinstance(state, dict) and "results" in state:
            review_result_node = state["results"].get(AgentIdentifier.REVIEW)
            if review_result_node and hasattr(review_result_node, "result"):
                agent_result = review_result_node.result
                if (
                    hasattr(agent_result, "state")
                    and "review_result" in agent_result.state
                ):
                    return agent_result.state["review_result"]
        elif state and hasattr(state, "results"):
            review_result_node = state.results.get(AgentIdentifier.REVIEW)
            if review_result_node and hasattr(review_result_node, "result"):
                agent_result = review_result_node.result
                if (
                    hasattr(agent_result, "state")
                    and "review_result" in agent_result.state
                ):
                    return agent_result.state["review_result"]

        # Fallback: If task is a string containing XML, try to parse it
        if isinstance(task, str):
            try:
                xml_content = extract_review_xml(task)
                return parse_review_xml(xml_content)
            except Exception:
                pass

        # If we couldn't parse, return a default failed review
        return ReviewResult(
            blocking_issues=["Could not parse review result"],
            summary="Quality checker failed to extract review data",
        )

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Evaluate the review result and decide next step.

        Args:
            task: The task/review feedback from the reviewer agent (XML content)
            invocation_state: State from previous invocations (GraphState)
            **kwargs: Additional arguments (may contain 'state')

        Returns:
            MultiAgentResult with approved state and feedback for conditional edges
        """
        self.iteration += 1

        # Try to get the graph state from kwargs
        graph_state = kwargs.get("state", invocation_state)

        # Extract and evaluate the review result
        review_result = self._extract_review_result(task, graph_state)
        approved = review_result.is_approved()

        if approved:
            # Build success message with scores
            score_summary = ", ".join(
                f"{cat.name}: {cat.score}/20" for cat in review_result.categories
            )
            msg = f"""✅ ITERATION {self.iteration}: APPROVED

All quality criteria met:
- No blocking issues
- All category scores >= 18/20

Scores: {score_summary}

{review_result.summary}"""
            feedback_for_code_agent = None
        else:
            # Build revision request with detailed feedback
            feedback = review_result.get_feedback_for_revision()
            msg = f"""⚠️ ITERATION {self.iteration}: NEEDS REVISION

{feedback}

The code agent will receive this feedback to implement fixes."""
            feedback_for_code_agent = feedback
            
        # Reset tool counts for agents that will be revisited in the loop
        reset_agent_count(AgentIdentifier.CODE_REVISION.value)
        reset_agent_count(AgentIdentifier.REVIEW.value)

        agent_result = AgentResult(
            stop_reason="end_turn",
            message=Message(role="assistant", content=[ContentBlock(text=msg)]),
            metrics=None,
            state={
                "approved": approved,
                "iteration": self.iteration,
                "feedback_for_code_agent": feedback_for_code_agent,
                "review_summary": review_result.summary,
            },
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
