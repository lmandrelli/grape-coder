from typing import cast, Any, Optional

from rich.console import Console
from strands import Agent
from strands.agent import AgentResult
from strands.multiagent import GraphBuilder
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.review.review_xml_utils import (
    extract_scores_from_xml,
    extract_review_tasks_from_xml,
    needs_revision_from_scores,
)
from grape_coder.agents.review.review_context import (
    ReviewHistoryContext,
    detect_regression,
)
from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.agents.review.code_revision import create_code_revision_agent
from grape_coder.agents.review.linter_node import LinterNode
from grape_coder.agents.review.reviewer import create_reviewer_agent
from grape_coder.agents.review.score_evaluator import create_score_evaluator_agent
from grape_coder.agents.review.review_task_generator import create_task_generator_agent
from grape_coder.tools.tool_limit_tracker import reset_all_counts

console = Console()

# Global review context - shared across the graph
_review_context: Optional[ReviewHistoryContext] = None


def get_review_context() -> ReviewHistoryContext:
    """Get or create the global review context."""
    global _review_context
    if _review_context is None:
        _review_context = ReviewHistoryContext(max_iterations=5)
    return _review_context


def reset_review_context(max_iterations: int = 5) -> ReviewHistoryContext:
    """Reset the global review context for a new review session."""
    global _review_context
    _review_context = ReviewHistoryContext(max_iterations=max_iterations)
    return _review_context


def needs_revision(state) -> bool:
    """Check if revision is needed based on score evaluator results and iteration limit."""
    context = get_review_context()

    # Check iteration limit first
    if not context.should_continue():
        console.print(
            f"[yellow]Max iterations ({context.max_iterations}) reached. Stopping review loop.[/yellow]"
        )
        return False

    score_result = state.results.get(AgentIdentifier.SCORE_EVALUATOR)
    if score_result is None:
        return False

    result_text = str(score_result.result)
    scores = extract_scores_from_xml(result_text)

    if not scores:
        return False

    # Extract tasks for context tracking
    task_result = state.results.get(AgentIdentifier.REVIEW_TASK_GENERATOR)
    tasks = []
    if task_result:
        task_text = str(task_result.result)
        _, task_list = extract_review_tasks_from_xml(task_text)
        tasks = [t.get("description", "") for t in task_list]

    # Record this iteration's results
    context.add_iteration_result(scores=scores, tasks_generated=tasks)

    # Check for regression and log it
    if context.iterations and context.iterations[-1].regression_detected:
        regression_details = context.iterations[-1].regression_details
        console.print(
            f"[yellow]Warning: Score regression detected in iteration {context.current_iteration}[/yellow]"
        )
        console.print(f"[yellow]{regression_details}[/yellow]")
        console.print(
            "[yellow]Continuing with context to try a different approach...[/yellow]"
        )

    needs_rev = needs_revision_from_scores(scores)

    if needs_rev:
        console.print(
            f"[cyan]Iteration {context.current_iteration}/{context.max_iterations}: "
            f"Revision needed. Continuing loop...[/cyan]"
        )
    else:
        console.print(
            f"[green]Iteration {context.current_iteration}: All scores pass thresholds. "
            f"Review complete![/green]"
        )

    return needs_rev


def all_review_agents_complete(required_nodes: list[str]):
    def check_all_complete(state) -> bool:
        return all(
            node_id in state.results
            and state.results[node_id].status == Status.COMPLETED
            for node_id in required_nodes
        )

    return check_all_complete


class IterationTrackerNode(MultiAgentBase):
    """A node that tracks iteration count and resets tool counters when looping."""

    def __init__(self):
        super().__init__()

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        # Reset tool counters
        reset_all_counts()

        # Increment iteration counter
        context = get_review_context()
        iteration = context.increment_iteration()

        console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
        console.print(
            f"[bold cyan]Starting Review Iteration {iteration} of {context.max_iterations}[/bold cyan]"
        )
        console.print(f"[bold cyan]{'=' * 60}[/bold cyan]\n")

        agent_result = AgentResult(
            stop_reason="end_turn",
            state=Status.COMPLETED,
            metrics=EventLoopMetrics(),
            message=Message(
                role="assistant",
                content=[
                    ContentBlock(
                        text=f"Iteration {iteration}/{context.max_iterations} started. Tool counters reset."
                    )
                ],
            ),
        )

        return MultiAgentResult(
            status=Status.COMPLETED,
            results={
                "iteration_tracker": NodeResult(
                    result=agent_result, status=Status.COMPLETED
                )
            },
        )


class ToolResetNode(MultiAgentBase):
    """A node that resets all tool counters when looping back in the review graph."""

    def __init__(self):
        super().__init__()

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        reset_all_counts()

        # Increment iteration for the next loop
        context = get_review_context()
        iteration = context.increment_iteration()

        console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
        console.print(
            f"[bold cyan]Starting Review Iteration {iteration} of {context.max_iterations}[/bold cyan]"
        )
        console.print(f"[bold cyan]{'=' * 60}[/bold cyan]\n")

        agent_result = AgentResult(
            stop_reason="end_turn",
            state=Status.COMPLETED,
            metrics=EventLoopMetrics(),
            message=Message(
                role="assistant",
                content=[
                    ContentBlock(
                        text=f"Starting iteration {iteration}. Tool counters reset."
                    )
                ],
            ),
        )

        return MultiAgentResult(
            status=Status.COMPLETED,
            results={
                "tool_reset": NodeResult(result=agent_result, status=Status.COMPLETED)
            },
        )


def build_review_graph(work_path: str, max_iterations: int = 5):
    """Build the review graph with iteration tracking and limits.

    Args:
        work_path: Path to the workspace being reviewed
        max_iterations: Maximum number of review iterations (default: 5)

    Returns:
        The built graph ready for execution
    """
    # Reset the review context for this new review session
    reset_review_context(max_iterations=max_iterations)

    # Initialize first iteration
    context = get_review_context()
    context.increment_iteration()

    reviewer_agent = create_reviewer_agent(work_path)
    score_evaluator_agent = create_score_evaluator_agent()
    task_generator_agent = create_task_generator_agent()
    code_revision_agent = create_code_revision_agent(
        work_path, AgentIdentifier.CODE_REVISION
    )
    tool_reset_node = ToolResetNode()
    linter_node = LinterNode(work_path)

    builder = GraphBuilder()

    builder.add_node(tool_reset_node, "tool_reset")
    builder.add_node(reviewer_agent, AgentIdentifier.REVIEW)
    builder.add_node(score_evaluator_agent, AgentIdentifier.SCORE_EVALUATOR)
    builder.add_node(task_generator_agent, AgentIdentifier.REVIEW_TASK_GENERATOR)
    builder.add_node(code_revision_agent, AgentIdentifier.CODE_REVISION)
    builder.add_node(linter_node, "linter")

    # Linter runs first to provide technical issues to the reviewer
    builder.add_edge("linter", AgentIdentifier.REVIEW)

    # Both evaluators run in parallel after review is complete
    builder.add_edge(AgentIdentifier.REVIEW, AgentIdentifier.SCORE_EVALUATOR)
    builder.add_edge(AgentIdentifier.REVIEW, AgentIdentifier.REVIEW_TASK_GENERATOR)

    parallel_review_agents = [
        AgentIdentifier.SCORE_EVALUATOR,
        AgentIdentifier.REVIEW_TASK_GENERATOR,
    ]
    evaluation_done = all_review_agents_complete(parallel_review_agents)

    builder.add_edge(
        AgentIdentifier.REVIEW_TASK_GENERATOR,
        AgentIdentifier.CODE_REVISION,
        condition=evaluation_done and needs_revision,
    )

    builder.add_edge(
        AgentIdentifier.CODE_REVISION,
        "tool_reset",
        condition=needs_revision,
    )

    builder.add_edge(
        "tool_reset",
        "linter",
        condition=needs_revision,
    )

    # Linter is the entry point for the first iteration
    builder.set_entry_point("linter")
    builder.set_execution_timeout(5400)  # 1h30 max
    builder.reset_on_revisit(True)

    console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
    console.print(
        f"[bold cyan]Starting Review Loop (max {max_iterations} iterations)[/bold cyan]"
    )
    console.print(f"[bold cyan]{'=' * 60}[/bold cyan]\n")

    return builder.build()
