from strands.multiagent import Swarm

from .architect import create_architect_agent
from .content_planner import create_content_planner_agent
from .designer import create_designer_agent
from .researcher import create_researcher_agent


def build_planner(work_path: str):
    # Create specialized agents
    researcher = create_researcher_agent(str(work_path))
    architect = create_architect_agent(str(work_path))
    designer = create_designer_agent(str(work_path))
    content_planner = create_content_planner_agent(str(work_path))

    # Create swarm with website development agents
    return Swarm(
        [researcher, architect, designer, content_planner],
        entry_point=researcher,  # Start with researcher
        max_handoffs=10,
        max_iterations=10,
        execution_timeout=1200,  # 20 minutes
        node_timeout=300,  # 5 minutes per agent
        repetitive_handoff_detection_window=3,
        repetitive_handoff_min_unique_agents=2,
    )
