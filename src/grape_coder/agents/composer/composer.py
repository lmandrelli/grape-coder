from strands.multiagent import GraphBuilder
from strands.multiagent.base import Status
from strands.multiagent.graph import GraphState

from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.nodes.taskfiltering import TaskFilteringNode

from .generate_class import create_class_agent
from .generate_js import create_js_agent
from .orchestrator import create_orchestrator_agent
from .reviewer import create_review_agent
from .svg import create_svg_agent
from .text import create_text_agent

code_agent_after_review_id = AgentIdentifier.CODE_AFTER_REVIEW


def all_parallel_agents_complete(required_nodes: list[str]):
    """Factory function to create AND condition for multiple dependencies.

    This ensures the code_agent waits for ALL parallel agents to complete
    before starting assembly.
    """

    def check_all_complete(state: GraphState) -> bool:
        return all(
            node_id in state.results
            and state.results[node_id].status == Status.COMPLETED
            for node_id in required_nodes
        )

    return check_all_complete


def build_composer(work_path: str):
    """
    Build a multi-agent graph for web page generation.

    Graph structure:
        orchestrator
            ├── filter_class_task -> class_agent   ─┬──> code_agent ──> review_agent ──> code_agent_after_review
            ├── filter_text_task  -> text_agent    ─┤
            ├── filter_js_task    -> js_agent      ─┤
            └── filter_svg_task   -> svg_agent     ─┘

    Orchestrator analyzes the task and creates a distribution plan.
    Task filtering nodes extract specific tasks for each agent.
    Parallel agents (class, text, svg) work simultaneously.
    Code agent assembles everything into the final HTML output.
    """
    # Import code agent here to avoid circular imports
    from ..code import create_code_agent

    # Create all agents
    orchestrator = create_orchestrator_agent()
    class_agent = create_class_agent(work_path)
    js_agent = create_js_agent(work_path)
    text_agent = create_text_agent(work_path)
    svg_agent = create_svg_agent(work_path)
    code_agent = create_code_agent(work_path)
    review_agent = create_review_agent(work_path)
    code_agent_after_review = create_code_agent(work_path)

    # Create task filtering nodes
    class_filter = TaskFilteringNode(agent_xml_tag=AgentIdentifier.GENERATE_CLASS)
    js_filter = TaskFilteringNode(agent_xml_tag=AgentIdentifier.GENERATE_JS)
    text_filter = TaskFilteringNode(agent_xml_tag=AgentIdentifier.TEXT)
    svg_filter = TaskFilteringNode(agent_xml_tag=AgentIdentifier.SVG)
    code_filter = TaskFilteringNode(agent_xml_tag=AgentIdentifier.CODE)

    # Build the graph
    builder = GraphBuilder()

    # Add nodes
    builder.add_node(orchestrator, AgentIdentifier.ORCHESTRATOR)
    builder.add_node(class_filter, "filter_class_task")
    builder.add_node(js_filter, "filter_js_task")
    builder.add_node(text_filter, "filter_text_task")
    builder.add_node(svg_filter, "filter_svg_task")
    builder.add_node(class_agent, AgentIdentifier.GENERATE_CLASS)
    builder.add_node(js_agent, AgentIdentifier.GENERATE_JS)
    builder.add_node(text_agent, AgentIdentifier.TEXT)
    builder.add_node(svg_agent, AgentIdentifier.SVG)
    builder.add_node(code_filter, "filter_code_task")
    builder.add_node(code_agent, AgentIdentifier.CODE)
    builder.add_node(review_agent, AgentIdentifier.REVIEW)
    builder.add_node(code_agent_after_review, code_agent_after_review_id)

    # Add edges: orchestrator -> task filters
    builder.add_edge(AgentIdentifier.ORCHESTRATOR, "filter_class_task")
    builder.add_edge(AgentIdentifier.ORCHESTRATOR, "filter_js_task")
    builder.add_edge(AgentIdentifier.ORCHESTRATOR, "filter_text_task")
    builder.add_edge(AgentIdentifier.ORCHESTRATOR, "filter_svg_task")
    builder.add_edge(AgentIdentifier.ORCHESTRATOR, "filter_code_task")

    # Add edges: task filters -> agents
    builder.add_edge("filter_class_task", AgentIdentifier.GENERATE_CLASS)
    builder.add_edge("filter_js_task", AgentIdentifier.GENERATE_JS)
    builder.add_edge("filter_text_task", AgentIdentifier.TEXT)
    builder.add_edge("filter_svg_task", AgentIdentifier.SVG)

    # Add edges: parallel agents -> code_agent (wait for ALL to complete)
    parallel_agents: list[str] = [
        AgentIdentifier.GENERATE_CLASS,
        AgentIdentifier.GENERATE_JS,
        AgentIdentifier.TEXT,
        AgentIdentifier.SVG,
        "filter_code_task",
    ]
    condition = all_parallel_agents_complete(parallel_agents)

    builder.add_edge(
        AgentIdentifier.GENERATE_CLASS, AgentIdentifier.CODE, condition=condition
    )
    builder.add_edge(
        AgentIdentifier.GENERATE_JS, AgentIdentifier.CODE, condition=condition
    )
    builder.add_edge(AgentIdentifier.TEXT, AgentIdentifier.CODE, condition=condition)
    builder.add_edge(AgentIdentifier.SVG, AgentIdentifier.CODE, condition=condition)
    builder.add_edge("filter_code_task", AgentIdentifier.CODE, condition=condition)

    builder.add_edge(AgentIdentifier.CODE, AgentIdentifier.REVIEW)
    builder.add_edge(AgentIdentifier.REVIEW, code_agent_after_review_id)

    # Set entry point
    builder.set_entry_point(AgentIdentifier.ORCHESTRATOR)

    # Configure execution limits
    builder.set_execution_timeout(1200)  # 20 minutes max

    # Build and return the graph
    return builder.build()
