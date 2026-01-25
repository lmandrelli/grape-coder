"""Review History Context for cross-iteration memory in the review loop.

This module implements Reflexion-style iterative memory, allowing agents
to maintain awareness of previous iterations, scores, and fixes.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IterationResult:
    """Stores results from a single review iteration."""

    iteration: int
    scores: dict[str, int]
    tasks_generated: list[str]
    fixes_applied: list[str]
    regression_detected: bool = False
    regression_details: Optional[str] = None


@dataclass
class ReviewHistoryContext:
    """Maintains review history across iterations for Reflexion-style memory.

    This context is passed through the review graph and NOT reset on revisit,
    allowing agents to build upon previous iterations rather than starting fresh.
    """

    max_iterations: int = 5
    current_iteration: int = 0
    iterations: list[IterationResult] = field(default_factory=list)

    def increment_iteration(self) -> int:
        """Increment and return the current iteration number."""
        self.current_iteration += 1
        return self.current_iteration

    def should_continue(self) -> bool:
        """Check if we haven't exceeded max iterations."""
        return self.current_iteration < self.max_iterations

    def add_iteration_result(
        self,
        scores: dict[str, int],
        tasks_generated: list[str],
        fixes_applied: Optional[list[str]] = None,
    ) -> None:
        """Record results from the current iteration."""
        result = IterationResult(
            iteration=self.current_iteration,
            scores=scores.copy(),
            tasks_generated=tasks_generated.copy(),
            fixes_applied=fixes_applied.copy() if fixes_applied else [],
        )

        # Check for regression
        if len(self.iterations) > 0:
            prev_scores = self.iterations[-1].scores
            regression = detect_regression(scores, prev_scores)
            if regression:
                result.regression_detected = True
                result.regression_details = regression

        self.iterations.append(result)

    def get_previous_scores(self) -> Optional[dict[str, int]]:
        """Get scores from the previous iteration, if any."""
        if len(self.iterations) > 0:
            return self.iterations[-1].scores.copy()
        return None

    def get_all_tasks_generated(self) -> list[str]:
        """Get a flat list of all tasks generated across all iterations."""
        all_tasks = []
        for iteration in self.iterations:
            all_tasks.extend(iteration.tasks_generated)
        return all_tasks

    def get_all_fixes_applied(self) -> list[str]:
        """Get a flat list of all fixes applied across all iterations."""
        all_fixes = []
        for iteration in self.iterations:
            all_fixes.extend(iteration.fixes_applied)
        return all_fixes

    def had_regression(self) -> bool:
        """Check if any iteration had a regression."""
        return any(it.regression_detected for it in self.iterations)

    def get_latest_regression_details(self) -> Optional[str]:
        """Get details of the most recent regression, if any."""
        for iteration in reversed(self.iterations):
            if iteration.regression_detected and iteration.regression_details:
                return iteration.regression_details
        return None

    def format_summary_for_reviewer(self) -> str:
        """Format a summary of previous iterations for the reviewer prompt.

        Returns a concise summary including:
        - Previous scores
        - Tasks that were completed
        - Key remaining issues
        - Regression warnings if applicable
        """
        if self.current_iteration == 0 or len(self.iterations) == 0:
            return ""

        lines = [
            f"=== PREVIOUS REVIEW CONTEXT (Iteration {self.current_iteration} of {self.max_iterations}) ===",
            "",
        ]

        # Previous scores
        prev_scores = self.get_previous_scores()
        if prev_scores:
            lines.append("PREVIOUS SCORES:")
            for category, score in prev_scores.items():
                status = (
                    "PASS" if _score_passes(category, score) else "NEEDS IMPROVEMENT"
                )
                lines.append(f"  - {category}: {score}/20 ({status})")
            lines.append("")

        # Tasks that were generated and presumably fixed
        prev_tasks = self.iterations[-1].tasks_generated if self.iterations else []
        if prev_tasks:
            lines.append("TASKS FROM PREVIOUS ITERATION (should have been addressed):")
            for i, task in enumerate(prev_tasks[:5], 1):  # Limit to 5 for brevity
                lines.append(f"  {i}. {task[:100]}...")
            if len(prev_tasks) > 5:
                lines.append(f"  ... and {len(prev_tasks) - 5} more tasks")
            lines.append("")

        # Fixes applied
        fixes = self.iterations[-1].fixes_applied if self.iterations else []
        if fixes:
            lines.append("FIXES APPLIED IN PREVIOUS ITERATION:")
            for fix in fixes[:5]:
                lines.append(f"  - {fix[:100]}...")
            if len(fixes) > 5:
                lines.append(f"  ... and {len(fixes) - 5} more fixes")
            lines.append("")

        # Regression warning
        if self.iterations and self.iterations[-1].regression_detected:
            lines.append("WARNING: REGRESSION DETECTED IN PREVIOUS ITERATION")
            lines.append(f"Details: {self.iterations[-1].regression_details}")
            lines.append("Please try a DIFFERENT approach to fix the issues.")
            lines.append("")

        lines.append("CRITICAL INSTRUCTIONS FOR THIS ITERATION:")
        lines.append("- Focus ONLY on issues that REMAIN after previous fixes")
        lines.append("- Do NOT re-report issues that were already addressed")
        lines.append(
            "- If a fix was attempted but didn't work, suggest a DIFFERENT approach"
        )
        lines.append("- Acknowledge improvements that were made")
        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def format_summary_for_task_generator(self) -> str:
        """Format a summary for the task generator to enable delta-focused task generation."""
        if self.current_iteration == 0 or len(self.iterations) == 0:
            return ""

        lines = [
            f"=== ITERATION CONTEXT ({self.current_iteration} of {self.max_iterations}) ===",
            "",
        ]

        # All previous tasks
        all_tasks = self.get_all_tasks_generated()
        if all_tasks:
            lines.append("PREVIOUSLY GENERATED TASKS (do not regenerate these):")
            for i, task in enumerate(all_tasks[:10], 1):
                lines.append(f"  {i}. {task[:80]}...")
            if len(all_tasks) > 10:
                lines.append(f"  ... and {len(all_tasks) - 10} more")
            lines.append("")

        lines.append("TASK GENERATION RULES FOR THIS ITERATION:")
        lines.append(
            "- Generate tasks ONLY for NEW issues or issues that REMAIN unfixed"
        )
        lines.append(
            "- Do NOT regenerate tasks that were already created in previous iterations"
        )
        lines.append("- If a previous fix didn't work, suggest a DIFFERENT approach")
        lines.append("- Focus on fewer, more impactful tasks")
        lines.append("")

        return "\n".join(lines)


def detect_regression(
    current_scores: dict[str, int], previous_scores: dict[str, int]
) -> Optional[str]:
    """Detect if current scores show regression compared to previous scores.

    Args:
        current_scores: Scores from the current iteration
        previous_scores: Scores from the previous iteration

    Returns:
        A string describing the regression, or None if no regression detected
    """
    regressions = []

    for category in current_scores:
        if category in previous_scores:
            current = current_scores[category]
            previous = previous_scores[category]
            if current < previous:
                diff = previous - current
                regressions.append(f"{category}: {previous} -> {current} (-{diff})")

    if regressions:
        return f"Score decreased in: {', '.join(regressions)}"
    return None


def calculate_average_score(scores: dict[str, int]) -> float:
    """Calculate the average score across all categories."""
    if not scores:
        return 0.0
    return sum(scores.values()) / len(scores)


def scores_improved(
    current_scores: dict[str, int], previous_scores: dict[str, int]
) -> bool:
    """Check if overall scores improved compared to previous iteration."""
    current_avg = calculate_average_score(current_scores)
    previous_avg = calculate_average_score(previous_scores)
    return current_avg > previous_avg


def _score_passes(category: str, score: int) -> bool:
    """Check if a score passes for its category."""
    critical_threshold = 17
    standard_threshold = 15

    if category in ["code_validity", "integration"]:
        return score >= critical_threshold
    return score >= standard_threshold
