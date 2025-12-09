from strands import Agent
from strands.tools import tool

from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.config import get_config_manager


def create_orchestrator_agent() -> Agent:
    """Create an orchestrator agent that distributes tasks to specialized agents"""

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.ORCHESTRATOR)

    # Create agent with task distribution tools
    system_prompt = """You are a task orchestrator for web page generation.
Your role is to analyze a project description and distribute tasks to specialized agents.

Available agents:
- class_agent: Creates reusable CSS classes and component structures
- css_agent: Creates CSS styling and visual design
- text_agent: Generates text content related to the subject
- coder_agent: Takes all generated content and produces final HTML code

You must analyze the requirements and create a task distribution plan in XML format.

Output format example:
<task_distribution>
    <class_generator>
        <task>Create a navigation component class</task>
        <task>Create a card component class</task>
        <task>Create color scheme with primary blue theme</task>
        <task>Create responsive layout styles</task>
    </class_generator>
    <text_generator>
        <task>Generate hero section headline and tagline</task>
        <task>Generate about us paragraph</task>
    </text_generator>
    <code>
        <task>Combine all components into final HTML page</task>
    </code>
</task_distribution>

Be thorough and break down the project into specific, actionable tasks for each agent."""

    return Agent(
        model=model,
        tools=[
            validate_distribution,
        ],
        system_prompt=system_prompt,
        name="orchestrator",
        description="AI assistant for distributing web generation tasks",
    )


@tool
def validate_distribution(xml_distribution: str) -> str:
    """Validate the XML task distribution format

    Args:
        xml_distribution: XML string containing task distribution
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_distribution)

        if root.tag != "task_distribution":
            return "Error: Root element must be 'task_distribution'"

        required_agents = ["class_agent", "css_agent", "text_agent", "coder_agent"]
        found_agents = [child.tag for child in root]

        missing = [agent for agent in required_agents if agent not in found_agents]
        if missing:
            return f"Warning: Missing agent sections: {', '.join(missing)}"

        task_count = 0
        for agent in root:
            tasks = agent.findall("task")
            task_count += len(tasks)

        return f"Validation passed: {task_count} tasks distributed across {len(found_agents)} agents"

    except ET.ParseError as e:
        return f"Error: Invalid XML format - {str(e)}"
