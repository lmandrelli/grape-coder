"""Quality Checker Node for the review loop.

This node checks the review result and determines if the code needs revision
or if it can proceed to completion. It evaluates the category scores from the review
and generates feedback for the code revision agent.
"""

from strands.agent.agent_result import AgentResult
from strands.multiagent import MultiAgentBase, MultiAgentResult
from strands.multiagent.base import NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.composer.reviewer import SCORE_CATEGORIES
from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.tools.tool_limit_tracker import reset_agent_count


class QualityChecker(MultiAgentBase):
    """Custom node that evaluates review results and decides if revision is needed.

    This node:
    1. Extracts the ReviewOutput from the reviewer's output
    2. Checks if category scores meet minimum thresholds
       - Overall average >= 16
       - Code validity >= 17 (CRITICAL)
       - Integration >= 17 (CRITICAL)
       - Other categories >= 15
    3. If not approved, generates feedback for the code agent
    4. Resets tool counts for agents in the revision loop
    """

    MAX_ITERATIONS = 20

    def __init__(self):
        super().__init__()
        self.name = "quality_checker"
        self.iteration = 0

    def _extract_review_output(self, task, state):
        """Extract ReviewOutput from the reviewer's output.

        The reviewer node stores the ReviewOutput in the agent result's state.
        """
        # Import here to avoid circular imports
        from grape_coder.agents.composer.reviewer import ReviewOutput

        # Try to get the pre-parsed ReviewOutput from the graph state
        # The ReviewValidatorNode stores it in its node result's state
        review_result_node = None
        if state:
            if isinstance(state, dict) and "results" in state:
                state_results = state["results"]
                if state_results and "review_agent" in state_results:
                    review_result_node = state_results["review_agent"]
            elif hasattr(state, "results"):
                state_results = state.results
                if state_results and "review_agent" in state_results:
                    review_result_node = state_results["review_agent"]

        if review_result_node and hasattr(review_result_node, "result"):
            agent_result = review_result_node.result
            if (
                hasattr(agent_result, "state")
                and isinstance(agent_result.state, dict)
                and "review_output" in agent_result.state
            ):
                return agent_result.state["review_output"]

        # If we couldn't parse, return a default failed review with low scores
        from grape_coder.agents.composer.reviewer import CategoryScore

        return ReviewOutput(
            category_scores=[
                CategoryScore(name="user_prompt_compliance", score=10),
                CategoryScore(name="code_validity", score=10),
                CategoryScore(name="integration", score=10),
                CategoryScore(name="responsiveness", score=10),
                CategoryScore(name="best_practices", score=10),
                CategoryScore(name="accessibility", score=10),
            ],
            summary="Quality checker failed to extract review data",
            tasks=[],
        )

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Evaluate the review result and decide next step.

        Args:
            task: The task/review feedback from the reviewer agent
            invocation_state: State from previous invocations (GraphState)
            **kwargs: Additional arguments (may contain 'state')

        Returns:
            MultiAgentResult with approved state and feedback for conditional edges
        """
        self.iteration += 1

        # Try to get the graph state from kwargs
        graph_state = kwargs.get("state", invocation_state)

        # Extract and evaluate the review output
        review_output = self._extract_review_output(task, graph_state)
        approved = review_output.is_approved()

        # Calculate average score
        category_dict = {c.name: c.score for c in review_output.category_scores}
        avg_score = (
            sum(category_dict.values()) / len(category_dict) if category_dict else 0
        )

        # Auto-approve after MAX_ITERATIONS (10) review loops
        if not approved and self.iteration >= self.MAX_ITERATIONS:
            approved = True
            msg = f"""### 🔄 ITERATION {self.iteration}: AUTO-APPROVED (Max iterations reached)

Code review has reached the maximum of {self.MAX_ITERATIONS} iterations. The result will be accepted even if quality standards are not fully met.

**Final review summary:**
{review_output.summary}"""
            feedback_for_code_agent = review_output.get_feedback_for_revision()
        elif approved:
            # Format category rows for markdown table
            category_rows = []
            for cat in SCORE_CATEGORIES:
                score = category_dict.get(cat, 0)
                status = "✅"
                category_rows.append(
                    f"| {cat.replace('_', ' ').title()} | {score}/20 | {status} |"
                )

            msg = f"""### ✅ ITERATION {self.iteration}: APPROVED

All quality criteria met! The code has passed the quality check.

**Review Summary:**
{review_output.summary}

**Category Scores:**

| Category | Score | Status |
|----------|-------|--------|
{chr(10).join(category_rows)}

**Overall Score: `{avg_score:.1f}/20`**

---
**Approval Requirements:**
- ✅ Average score >= 16/20
- ✅ Code validity >= 17/20 (CRITICAL)
- ✅ Integration >= 17/20 (CRITICAL)
- ✅ All other categories >= 15/20
"""
            feedback_for_code_agent = None
        else:
            feedback = review_output.get_feedback_for_revision()

            # Format category rows for markdown table with failures highlighted
            category_rows = []
            for cat in SCORE_CATEGORIES:
                score = category_dict.get(cat, 0)
                threshold = 17 if cat in ["code_validity", "integration"] else 15
                status = "❌" if score < threshold else "✅"
                category_rows.append(
                    f"| {cat.replace('_', ' ').title()} | {score}/20 | {status} (min {threshold}) |"
                )

            msg = f"""### ⚠️ ITERATION {self.iteration}: NEEDS REVISION

Quality check failed. The following categories did not meet requirements:

**Category Scores:**

| Category | Score | Status |
|----------|-------|--------|
{chr(10).join(category_rows)}

**Overall Score: `{avg_score:.1f}/20`**

**Issues to Fix:**
{feedback}

The code revision agent will receive this feedback to implement fixes.
"""
            feedback_for_code_agent = feedback

        # Reset tool counts for agents that will be revisited in the loop
        reset_agent_count(AgentIdentifier.CODE_REVISION.value)
        reset_agent_count(AgentIdentifier.REVIEW.value)

        agent_result = AgentResult(
            stop_reason="end_turn",
            message=Message(role="assistant", content=[ContentBlock(text=msg)]),
            metrics=EventLoopMetrics(),
            state={
                "approved": approved,
                "iteration": self.iteration,
                "feedback_for_code_agent": feedback_for_code_agent,
                "review_summary": review_output.summary,
                "review_scores": category_dict,
                "avg_score": avg_score,
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
