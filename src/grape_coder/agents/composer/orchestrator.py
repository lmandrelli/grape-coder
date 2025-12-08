import os

from dotenv import load_dotenv
from strands import Agent
from strands.models.mistral import MistralModel
from strands.tools import tool

load_dotenv()


def create_orchestrator_agent() -> Agent:
    """Create an orchestrator agent that distributes tasks to specialized agents"""

    # Get configuration from environment variables
    api_key = os.getenv("MISTRAL_API_KEY")
    model_name = os.getenv("MISTRAL_MODEL_NAME", "mistral-large-latest")

    if not api_key:
        raise ValueError("MISTRAL_API_KEY environment variable is required.")

    # Create Mistral model
    model = MistralModel(
        api_key=api_key,
        model_id=model_name,
    )

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
    <class_agent>
        <task>Create a navigation component class</task>
        <task>Create a card component class</task>
    </class_agent>
    <css_agent>
        <task>Create color scheme with primary blue theme</task>
        <task>Create responsive layout styles</task>
    </css_agent>
    <text_agent>
        <task>Generate hero section headline and tagline</task>
        <task>Generate about us paragraph</task>
    </text_agent>
    <coder_agent>
        <task>Combine all components into final HTML page</task>
    </coder_agent>
</task_distribution>

Be thorough and break down the project into specific, actionable tasks for each agent."""

    agent = Agent(
        model=model,
        tools=[
            validate_distribution,
        ],
        system_prompt=system_prompt,
        name="Orchestrator Agent",
        description="AI assistant for distributing web generation tasks",
    )

    return agent


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
