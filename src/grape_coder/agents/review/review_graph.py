from typing import cast, Any

from strands.multiagent import GraphBuilder
from strands.multiagent.base import Status

from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.agents.review.code_revision import create_code_revision_agent
from grape_coder.agents.review.reviewer import create_reviewer_agent
from grape_coder.agents.review.score_evaluator import create_score_evaluator_agent
from grape_coder.agents.review.task_generator import create_task_generator_agent
from grape_coder.nodes.quality_checker import QualityChecker
from grape_coder.tools.tool_limit_tracker import reset_agent_count


def needs_revision(state) -> bool:
    """Check if code needs revision based on quality checker result."""
    checker_result = state.results.get("quality_checker")
    if not checker_result:
        return False

    result = checker_result.result
    if hasattr(result, "state") and isinstance(result.state, dict):
        return not result.state.get("approved", False)

    return True


def all_review_agents_complete(required_nodes: list[str]):
    def check_all_complete(state) -> bool:
        return all(
            node_id in state.results
            and state.results[node_id].status == Status.COMPLETED
            for node_id in required_nodes
        )

    return check_all_complete


def build_review_graph(work_path: str):
    reviewer_agent = create_reviewer_agent(work_path)
    score_evaluator_agent = create_score_evaluator_agent()
    task_generator_agent = create_task_generator_agent()
    code_revision_agent = create_code_revision_agent(
        work_path, AgentIdentifier.CODE_REVISION
    )
    quality_checker = QualityChecker()

    builder = GraphBuilder()

    builder.add_node(reviewer_agent, "reviewer_agent")
    builder.add_node(score_evaluator_agent, "score_evaluator_agent")
    builder.add_node(task_generator_agent, "task_generator_agent")
    builder.add_node(code_revision_agent, AgentIdentifier.CODE_REVISION)
    builder.add_node(quality_checker, "quality_checker")

    builder.add_edge("reviewer_agent", "score_evaluator_agent")
    builder.add_edge("reviewer_agent", "task_generator_agent")

    parallel_review_agents = ["score_evaluator_agent", "task_generator_agent"]
    condition = all_review_agents_complete(parallel_review_agents)

    builder.add_edge("score_evaluator_agent", "quality_checker", condition=condition)
    builder.add_edge("task_generator_agent", "quality_checker", condition=condition)

    builder.add_edge(
        "quality_checker", AgentIdentifier.CODE_REVISION, condition=needs_revision
    )
    builder.add_edge(AgentIdentifier.CODE_REVISION, "reviewer_agent")

    builder.set_entry_point("reviewer_agent")
    builder.set_execution_timeout(7200)

    return builder.build()
