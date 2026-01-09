from typing import cast, Any

from strands import Agent
from strands.agent import AgentResult
from strands.multiagent import GraphBuilder
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.review.review_xml_utils import (
    extract_scores_from_xml,
    needs_revision_from_scores,
)
from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.agents.review.code_revision import create_code_revision_agent
from grape_coder.agents.review.linter_node import LinterNode
from grape_coder.agents.review.reviewer import create_reviewer_agent
from grape_coder.agents.review.score_evaluator import create_score_evaluator_agent
from grape_coder.agents.review.review_task_generator import create_task_generator_agent
from grape_coder.tools.tool_limit_tracker import reset_all_counts


def needs_revision(state) -> bool:
    """Check if revision is needed based on score evaluator results."""
    score_result = state.results.get(AgentIdentifier.SCORE_EVALUATOR)
    if score_result is None:
        return False

    result_text = str(score_result.result)
    scores = extract_scores_from_xml(result_text)

    if not scores:
        return False

    return needs_revision_from_scores(scores)


def all_review_agents_complete(required_nodes: list[str]):
    def check_all_complete(state) -> bool:
        return all(
            node_id in state.results
            and state.results[node_id].status == Status.COMPLETED
            for node_id in required_nodes
        )

    return check_all_complete


class ToolResetNode(MultiAgentBase):
    """A node that resets all tool counters when looping back in the review graph."""

    def __init__(self):
        super().__init__()

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        reset_all_counts()

        agent_result = AgentResult(
            stop_reason="end_turn",
            state=Status.COMPLETED,
            metrics=EventLoopMetrics(),
            message=Message(
                role="assistant",
                content=[
                    ContentBlock(text="All tool counters reset for reviewer loop")
                ],
            ),
        )

        return MultiAgentResult(
            status=Status.COMPLETED,
            results={
                "tool_reset": NodeResult(result=agent_result, status=Status.COMPLETED)
            },
        )


def build_review_graph(work_path: str):
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

    builder.add_edge(AgentIdentifier.REVIEW, "linter")
    builder.add_edge("linter", AgentIdentifier.SCORE_EVALUATOR)
    builder.add_edge("linter", AgentIdentifier.REVIEW_TASK_GENERATOR)

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
        AgentIdentifier.REVIEW,
        condition=needs_revision,
    )

    builder.set_entry_point(AgentIdentifier.REVIEW)
    builder.set_execution_timeout(5400)  # 1h30 max
    builder.reset_on_revisit(True)

    return builder.build()
