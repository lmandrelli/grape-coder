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

from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.agents.review.reviewer import ReviewOutput, SCORE_CATEGORIES
from grape_coder.agents.review.review_data import ReviewData, CategoryScore
from grape_coder.tools.tool_limit_tracker import reset_agent_count


class QualityChecker(MultiAgentBase):
    """Custom node that evaluates review results and decides if revision is needed.

    This node:
    1. Receives ReviewData with category scores, summary, and tasks
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

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        self.iteration += 1

        review_data = ReviewData()

        # Get data from invocation_state (shared between nodes)
        if invocation_state:
            # Get scores from score_evaluator
            score_data = invocation_state.get("score_review_data")
            if score_data and isinstance(score_data, ReviewData):
                review_data.category_scores = score_data.category_scores
                review_data.raw_output = score_data.raw_output

            # Get summary and tasks from task_generator
            task_data = invocation_state.get("task_review_data")
            if task_data and isinstance(task_data, ReviewData):
                review_data.summary = task_data.summary
                review_data.tasks = task_data.tasks
                if not review_data.raw_output:
                    review_data.raw_output = task_data.raw_output

        # Fallback if no data found
        if not review_data.category_scores and not review_data.summary:
            review_data = ReviewData()
            review_data.summary = (
                "Quality checker received no review data from parallel agents"
            )

        approved = self._is_approved(review_data)
        avg_score = review_data.average_score()

        # Auto-approve after MAX_ITERATIONS
        if not approved and self.iteration >= self.MAX_ITERATIONS:
            approved = True
            msg = f"""### 🔄 ITERATION {self.iteration}: AUTO-APPROVED (Max iterations reached)

Code review has reached the maximum of {self.MAX_ITERATIONS} iterations. The result will be accepted even if quality standards are not fully met.

**Final review summary:**
{review_data.summary}"""
            feedback_for_code_agent = review_data.review_feedback
        elif approved:
            category_rows = []
            for cat in SCORE_CATEGORIES:
                score = review_data.get_score(cat)
                status = "✅"
                category_rows.append(
                    f"| {cat.replace('_', ' ').title()} | {score}/20 | {status} |"
                )

            msg = f"""### ✅ ITERATION {self.iteration}: APPROVED

All quality criteria met! The code has passed the quality check.

**Review Summary:**
{review_data.summary}

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
            feedback = self._get_feedback_for_revision(review_data)

            category_rows = []
            for cat in SCORE_CATEGORIES:
                score = review_data.get_score(cat)
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

        print(msg)

        # Reset tool counts
        reset_agent_count(AgentIdentifier.CODE_REVISION.value)
        reset_agent_count(AgentIdentifier.REVIEW.value)

        # Update review_data with quality checker results
        review_data.approved = approved
        review_data.iteration = self.iteration
        review_data.review_feedback = feedback_for_code_agent or ""

        # Store in invocation_state for code_revision to access
        if invocation_state is None:
            invocation_state = {}
        invocation_state["review_data"] = review_data

        task_for_next_agent = (
            feedback_for_code_agent
            if feedback_for_code_agent
            else "No revision needed - code approved"
        )

        agent_result = AgentResult(
            stop_reason="end_turn",
            message=Message(
                role="assistant", content=[ContentBlock(text=task_for_next_agent)]
            ),
            metrics=EventLoopMetrics(),
            state={
                "approved": approved,
                "iteration": self.iteration,
                "feedback_for_code_agent": feedback_for_code_agent,
                "review_summary": review_data.summary,
                "review_data": review_data,
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

    def _is_approved(self, review_data: ReviewData) -> bool:
        """Check if the review meets all approval criteria."""
        if not review_data.category_scores:
            return False

        category_dict = {c.name: c.score for c in review_data.category_scores}
        avg_score = sum(category_dict.values()) / len(category_dict)

        # Check average score threshold
        if avg_score < 16:
            return False

        # Check critical categories
        if category_dict.get("code_validity", 0) < 17:
            return False
        if category_dict.get("integration", 0) < 17:
            return False

        # Check other categories
        for cat, score in category_dict.items():
            if cat not in ["code_validity", "integration"] and score < 15:
                return False

        return True

    def _get_feedback_for_revision(self, review_data: ReviewData) -> str:
        feedback_parts = []

        for cat_score in review_data.category_scores:
            threshold = 17 if cat_score.name in ["code_validity", "integration"] else 15
            if cat_score.score < threshold:
                feedback_parts.append(
                    f"- **{cat_score.name.replace('_', ' ').title()}**: Score {cat_score.score}/20 (minimum {threshold})"
                )

        if review_data.tasks:
            feedback_parts.append("\n**Specific Tasks:**")
            for task in review_data.tasks:
                files_str = ", ".join(task.files) if task.files else "Multiple files"
                feedback_parts.append(f"📋 {task.description}")
                feedback_parts.append(f"   Files: {files_str}")

        return (
            "\n".join(feedback_parts)
            if feedback_parts
            else "No specific issues identified, but score does not meet minimum requirements."
        )
