from strands import Agent
from strands.agent.agent_result import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.config import get_config_manager


def create_orchestrator_agent() -> MultiAgentBase:
    """Create an orchestrator agent that distributes tasks to specialized agents"""

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.ORCHESTRATOR)

    # Create agent with task distribution tools
    system_prompt = """You are a task orchestrator for web page generation.
Your role is to analyze a project description and distribute tasks to specialized agents.

Available agents:
- class_agent: Creates reusable CSS classes
- text_agent: Generates text content for web pages
- coder_agent: Takes all generated content and produces final HTML code

You must analyze the requirements and create a task distribution plan in XML format.

Output format example:
<task_distribution>
    <class_agent>
        <task>Create a navigation component class</task>
        <task>Create a card component class</task>
        <task>Create color scheme with primary blue theme</task>
        <task>Create responsive layout styles</task>
    </class_agent>
    <text_agent>
        <task>Generate hero section headline and tagline</task>
        <task>Generate about us paragraph</task>
    </text_agent>
    <code_agent>
        <task>Combine all components into final HTML page</task>
    </code_agent>
</task_distribution>

Be thorough and break down the project into specific, actionable tasks for each agent."""

    agent = Agent(model=model, system_prompt=system_prompt)

    return XMLValidatorNode(agent=agent)


class XMLValidatorNode(MultiAgentBase):
    """Custom node type that validates XML with retry logic"""

    def __init__(self, agent: Agent, max_retries: int = 3):
        super().__init__()
        self.agent = agent
        self.max_retries = max_retries

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Execute XML validation with retry logic"""
        initial_prompt = task if isinstance(task, str) else str(task)
        current_prompt = initial_prompt
        last_error = None
        xml_content = None

        for attempt in range(self.max_retries + 1):
            try:
                # Ask model to build XML
                if attempt == 0:
                    # First attempt - just the initial prompt
                    prompt = str(current_prompt)
                else:
                    # Retry attempts - include previous attempt and error
                    prompt = f"""Your previous attempt:
<last_attempt>
{current_prompt}
</last_attempt>

Error encountered:
<error>
{last_error}
</error>

Please fix the XML and provide a corrected version. Ensure the XML is well-formed and follows the required structure."""

                # Get model response
                response = await self.agent.invoke_async(prompt)
                xml_content = str(response)

                # Try to extract XML from response
                xml_to_validate = self._extract_xml(xml_content)

                # Validate XML
                validate_distribution(xml_to_validate)

                # If we get here, XML is valid
                agent_result = AgentResult(
                    stop_reason="end_turn",
                    state=Status.COMPLETED,
                    metrics=EventLoopMetrics(),
                    message=Message(
                        role="assistant", content=[ContentBlock(text=xml_to_validate)]
                    ),
                )

                return MultiAgentResult(
                    status=Status.COMPLETED,
                    results={
                        "xml_validator": NodeResult(
                            result=agent_result, status=Status.COMPLETED
                        )
                    },
                )

            except XMLValidationError as e:
                last_error = str(e)
                current_prompt = ""
                if xml_content is not None:
                    current_prompt = xml_content

                if attempt == self.max_retries:
                    # Max retries reached, send initial prompt to next nodes
                    agent_result = AgentResult(
                        stop_reason="guardrail_intervened",
                        state=Status.COMPLETED,
                        metrics=EventLoopMetrics(),
                        message=Message(
                            role="assistant",
                            content=[ContentBlock(text=initial_prompt)],
                        ),
                    )

                    return MultiAgentResult(
                        status=Status.COMPLETED,
                        results={
                            "xml_validator": NodeResult(
                                result=agent_result, status=Status.COMPLETED
                            )
                        },
                    )

                # Continue to next retry
                continue

            except Exception as e:
                # Other unexpected errors
                agent_result = AgentResult(
                    stop_reason="guardrail_intervened",
                    state=Status.FAILED,
                    metrics=EventLoopMetrics(),
                    message=Message(
                        role="assistant",
                        content=[ContentBlock(text=f"Error: {str(e)}")],
                    ),
                )

                return MultiAgentResult(
                    status=Status.FAILED,
                    results={
                        "xml_validator": NodeResult(
                            result=agent_result, status=Status.FAILED
                        )
                    },
                )

    def _extract_xml(self, content):
        """Extract XML content from model response"""
        import re

        # Try to find XML content between <task_distribution> and </task_distribution>
        pattern = r"<task_distribution>.*?</task_distribution>"
        match = re.search(pattern, content, re.DOTALL)

        if match:
            return match.group(0)

        # If no specific tags found, try to find any XML-like content
        xml_pattern = r"<[^>]+>.*?</[^>]+>"
        xml_match = re.search(xml_pattern, content, re.DOTALL)

        if xml_match:
            return xml_match.group(0)

        # Return original content if no XML found
        return content


class XMLValidationError(Exception):
    """Custom exception for XML validation errors"""


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

        required_agents = ["class_agent", "text_agent", "coder_agent"]
        found_agents = [child.tag for child in root]

        missing = [agent for agent in required_agents if agent not in found_agents]
        if missing:
            raise XMLValidationError(
                f"Warning: Missing agent sections: {', '.join(missing)}"
            )

        task_count = 0
        for agent in root:
            tasks = agent.findall("task")
            task_count += len(tasks)

        return f"Validation passed: {task_count} tasks distributed across {len(found_agents)} agents"

    except ET.ParseError as e:
        raise XMLValidationError(f"Error: Invalid XML format - {str(e)}")
