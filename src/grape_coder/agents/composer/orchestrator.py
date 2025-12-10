from typing import Any

from strands import Agent
from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_tool_tracker


def create_orchestrator_agent() -> MultiAgentBase:
    """Create an orchestrator agent that distributes tasks to specialized agents"""

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.ORCHESTRATOR)

    # Create agent with task distribution tools
    system_prompt = f"""You are the orchestrator and entry point of a multi-agent system for website creation.

    CONTEXT:
    You are the first agent in a collaborative multi-agent workflow designed to create complete, professional websites.
    You receive a TODO LIST containing tasks to accomplish for building a website, and your critical role is to analyze
    these tasks and intelligently distribute them to specialized agents that will work in parallel to build the website.

    YOUR ROLE:
    Analyze the incoming TODO LIST and distribute each task to the appropriate specialized agent based on the task's nature.
    Your job is to understand each task and route it to the agent best suited to accomplish it.
    You must ensure every task from the TODO LIST is assigned to an agent.

    AVAILABLE SPECIALIZED AGENTS:
    1. {AgentIdentifier.GENERATE_CLASS}: CSS Specialist
       - Creates reusable CSS classes and styles
       - Handles all styling, layouts, colors, typography, responsive design
       - Outputs: .css files only
       - Examples: button styles, navigation bars, card components, grid layouts, color schemes

    2. {AgentIdentifier.TEXT}: Content Writer
       - Generates all text content for the website
       - Creates web-optimized copy (short paragraphs, scannable, action-oriented)
       - Outputs: .md (Markdown) files only
       - Examples: hero headlines, about sections, product descriptions, CTAs, footer text

    3. {AgentIdentifier.CODE}: HTML Integrator
       - Takes CSS and content files and creates the final HTML structure
       - Integrates all components into a cohesive, functional website
       - Outputs: .html files
       - This agent works AFTER class_agent and {AgentIdentifier.TEXT} complete their work

    TASK DISTRIBUTION PROCESS:
    1. You receive a TODO LIST with tasks to accomplish
    2. Analyze each task in the list
    3. Determine which agent should handle each task:
       - If it's about styles, CSS, layouts, colors, design → assign to {AgentIdentifier.GENERATE_CLASS}
       - If it's about writing text, content, copy, headlines → assign to {AgentIdentifier.TEXT}
       - If it's about HTML structure, integration, combining elements → assign to {AgentIdentifier.CODE}
    4. You may also break down complex tasks into multiple sub-tasks if needed
    5. Ensure all tasks from the TODO LIST are distributed
    6. Group related tasks together under the same agent

    OUTPUT FORMAT (REQUIRED XML):
    You MUST output your task distribution in this exact XML format:

    <task_distribution>
    <{AgentIdentifier.GENERATE_CLASS}>
        <task>Specific CSS task description</task>
        <task>Another CSS task description</task>
        ...
    </{AgentIdentifier.GENERATE_CLASS}>
    <{AgentIdentifier.TEXT}>
        <task>Specific content writing task</task>
        <task>Another content writing task</task>
        ...
    </{AgentIdentifier.TEXT}>
    <{AgentIdentifier.CODE}>
        <task>HTML integration task (usually one main task to combine everything)</task>
    </{AgentIdentifier.CODE}>
    </task_distribution>

    EXAMPLE:
    If you receive this TODO LIST:
    - Create a modern portfolio website
    - Design a responsive navigation bar
    - Write an engaging hero section
    - Style the project cards
    - Create about me content
    - Integrate everything into HTML

    You would distribute:
    <task_distribution>
    <{AgentIdentifier.GENERATE_CLASS}>
        <task>Design a responsive navigation bar with modern styling</task>
        <task>Style the project cards with hover effects and proper spacing</task>
        <task>Create overall responsive layout and color scheme for portfolio</task>
    </{AgentIdentifier.GENERATE_CLASS}>
    <{AgentIdentifier.TEXT}>
        <task>Write an engaging hero section with headline and introduction</task>
        <task>Create about me content describing background and skills</task>
    </{AgentIdentifier.TEXT}>
    <{AgentIdentifier.CODE}>
        <task>Integrate navigation, hero section, project cards, and about section into a complete HTML portfolio page</task>
    </{AgentIdentifier.CODE}>
    </task_distribution>

    Be thorough, specific, and ensure every task from the TODO LIST is assigned to an agent."""

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        name=AgentIdentifier.ORCHESTRATOR,
        description=get_agent_description(AgentIdentifier.ORCHESTRATOR),
        hooks=[get_tool_tracker(AgentIdentifier.ORCHESTRATOR)],
        callback_handler=None,
    )

    return XMLValidatorNode(agent=agent)


class XMLValidatorNode(MultiAgentBase):
    """Custom node type that validates XML with retry logic"""

    def __init__(self, agent: Agent, max_retries: int = 3):
        super().__init__()
        self.agent = agent
        self.max_retries = max_retries

    async def invoke_async(
        self,
        task: str | list[ContentBlock],
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> MultiAgentResult:
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

        # Fallback return (should not be reached due to loop logic)
        agent_result = AgentResult(
            stop_reason="guardrail_intervened",
            state=Status.FAILED,
            metrics=EventLoopMetrics(),
            message=Message(
                role="assistant",
                content=[ContentBlock(text=initial_prompt)],
            ),
        )
        return MultiAgentResult(
            status=Status.FAILED,
            results={
                "xml_validator": NodeResult(result=agent_result, status=Status.FAILED)
            },
        )

    def _extract_xml(self, content: str) -> str:
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

        required_agents = [
            AgentIdentifier.GENERATE_CLASS,
            AgentIdentifier.TEXT,
            AgentIdentifier.CODE,
        ]
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
