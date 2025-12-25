from typing import Any

from strands import Agent
from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_conversation_tracker, get_tool_tracker
from grape_coder.tools.tool_limit_hooks import get_tool_limit_hook


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
    Analyze the incoming TODO LIST and extract the global context, then distribute each task to the appropriate specialized agent based on the task's nature.
    Your job is to understand each task and route it to the agent best suited to accomplish it.
    You must ensure every task from the TODO LIST is assigned to an agent.

    GLOBAL CONTEXT EXTRACTION:
    Before distributing tasks, you MUST extract and summarize the global context of the entire website project.
    This context should include:
    - Overall website purpose and goals
    - Target audience and design style
    - Key features and functionality requirements
    - Technical requirements or constraints
    - Content themes and messaging
    - Any important design decisions or patterns
    
    This global context will be shared with ALL specialized agents to ensure consistency across the entire project.

    AVAILABLE SPECIALIZED AGENTS:
    1. {AgentIdentifier.GENERATE_CLASS}: CSS Specialist
       - Creates reusable CSS classes and styles
       - Handles all styling, layouts, colors, typography, responsive design
       - Outputs: .css files only
       - Examples: button styles, navigation bars, card components, grid layouts, color schemes

    2. {AgentIdentifier.GENERATE_JS}: JavaScript Specialist
       - Creates reusable JavaScript components and utilities
       - Handles all client-side scripting, interactivity, and DOM manipulation
       - Outputs: .js files only
       - Examples: dropdowns, modals, form validation, client-side utilities

    3. {AgentIdentifier.TEXT}: Content Writer
       - Generates all text content for the website
       - Creates web-optimized copy (short paragraphs, scannable, action-oriented)
       - Outputs: .md (Markdown) files only
       - Examples: hero headlines, about sections, product descriptions, CTAs, footer text

    4. {AgentIdentifier.SVG}: Graphics Designer
        - Creates SVG graphics, icons, logos, and illustrations
        - Generates optimized, accessible, and scalable vector graphics
        - Outputs: .svg files only
        - Examples: logos, icons, illustrations, decorative elements, charts

    5. {AgentIdentifier.CODE}: HTML Integrator
       - Takes CSS and content files and creates the final HTML structure
       - Integrates all components into a cohesive, functional website
       - Outputs: .html files
       - This agent works AFTER {AgentIdentifier.GENERATE_CLASS}, {AgentIdentifier.GENERATE_JS}, {AgentIdentifier.SVG} and {AgentIdentifier.TEXT} complete their work

    TASK DISTRIBUTION PROCESS:
    1. You receive a TODO LIST with tasks to accomplish
    2. Analyze each task in the list
    3. Determine which agent should handle each task:
       - If it's about styles, CSS, layouts, colors, design → assign to {AgentIdentifier.GENERATE_CLASS}
       - If it's about JavaScript functionality, interactivity, DOM manipulation → assign to {AgentIdentifier.GENERATE_JS}
       - If it's about writing text, content, copy, headlines → assign to {AgentIdentifier.TEXT}
       - If it's about graphics, icons, logos, illustrations, SVG → assign to {AgentIdentifier.SVG}
       - If it's about HTML structure, integration, combining elements → assign to {AgentIdentifier.CODE}
    4. You may also break down complex tasks into multiple sub-tasks if needed
    5. Ensure all tasks from the TODO LIST are distributed
    6. Group related tasks together under the same agent

    OUTPUT FORMAT (REQUIRED XML):
    You MUST output your response in this exact XML format with BOTH context and task distribution:

    <context>
    [Detailed global context summary that will be shared with all agents. Include website purpose, target audience, design style, key features, technical requirements, content themes, and important design decisions. This context ensures all agents work consistently towards the same goals.]
    </context>
    
    <task_distribution>
    <{AgentIdentifier.GENERATE_CLASS}>
        <task>Specific CSS task description</task>
        <task>Another CSS task description</task>
        ...
    </{AgentIdentifier.GENERATE_CLASS}>
    <{AgentIdentifier.GENERATE_JS}>
        <task>Specific JavaScript task description</task>
        <task>Another JavaScript task description</task>
        ...
    </{AgentIdentifier.GENERATE_JS}>
    <{AgentIdentifier.TEXT}>
        <task>Specific content writing task</task>
        <task>Another content writing task</task>
        ...
    </{AgentIdentifier.TEXT}>
    <{AgentIdentifier.SVG}>
        <task>Specific graphics/illustration task</task>
        <task>Another graphics task</task>
        ...
    </{AgentIdentifier.SVG}>
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

    You would output:
    <context>
    This is a modern portfolio website for a creative professional showcasing their work. The target audience is potential clients and employers. The design should be clean, professional, and modern with a minimalist aesthetic. Key features include responsive navigation, project showcase with filtering, smooth animations, and contact section. The color scheme should be monochromatic with accent colors. Technical requirements include mobile-first responsive design and fast loading times.
    </context>
    
    <task_distribution>
    <{AgentIdentifier.GENERATE_CLASS}>
        <task>Design a responsive navigation bar with modern styling</task>
        <task>Style the project cards with hover effects and proper spacing</task>
        <task>Create overall responsive layout and color scheme for portfolio</task>
    </{AgentIdentifier.GENERATE_CLASS}>
    <{AgentIdentifier.GENERATE_JS}>
        <task>Create JavaScript for responsive navigation bar (toggle menu on mobile)</task>
        <task>Add interactivity to project cards (e.g., modals, filters)</task>
    </{AgentIdentifier.GENERATE_JS}>
    <{AgentIdentifier.TEXT}>
        <task>Write an engaging hero section with headline and introduction</task>
        <task>Create about me content describing background and skills</task>
    </{AgentIdentifier.TEXT}>
    <{AgentIdentifier.SVG}>
        <task>Create portfolio logo and social media icons</task>
        <task>Design decorative illustrations for hero section</task>
    </{AgentIdentifier.SVG}>
    <{AgentIdentifier.CODE}>
        <task>Integrate navigation, hero section, project cards, about section, and SVG graphics into a complete HTML portfolio page</task>
    </{AgentIdentifier.CODE}>
    </task_distribution>

    IMPORTANT: Always include both <context> and <task_distribution> sections. The context provides essential global information to all agents, while the task distribution assigns specific work. Be thorough, specific, and ensure every task from the TODO LIST is assigned to an agent."""

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        name=AgentIdentifier.ORCHESTRATOR,
        description=get_agent_description(AgentIdentifier.ORCHESTRATOR),
        hooks=[
            get_tool_tracker(AgentIdentifier.ORCHESTRATOR),
            get_conversation_tracker(AgentIdentifier.ORCHESTRATOR),
            get_tool_limit_hook(AgentIdentifier.ORCHESTRATOR),
        ],
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

        # Try to find the complete XML structure with both context and task_distribution
        # Look for <context> followed by <task_distribution>
        context_pattern = r"<context>.*?</context>"
        task_pattern = r"<task_distribution>.*?</task_distribution>"

        context_match = re.search(context_pattern, content, re.DOTALL)
        task_match = re.search(task_pattern, content, re.DOTALL)

        if context_match and task_match:
            # Return both sections together
            return context_match.group(0) + "\n" + task_match.group(0)
        elif task_match:
            # Fallback to just task_distribution if context is missing
            return task_match.group(0)

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
    """Validate the XML distribution format with context and task distribution

    Args:
        xml_distribution: XML string containing context and task distribution
    """
    import xml.etree.ElementTree as ET

    try:
        # Handle the case where we have both context and task_distribution
        # Check if the content contains both sections
        if (
            "<context>" in xml_distribution
            and "<task_distribution>" in xml_distribution
        ):
            # Extract and validate both sections
            context_match = xml_distribution.find("<context>")
            context_end = xml_distribution.find("</context>") + len("</context>")
            task_start = xml_distribution.find("<task_distribution>")

            context_section = xml_distribution[context_match:context_end]
            task_section = xml_distribution[task_start:]

            # Validate context section
            context_root = ET.fromstring(context_section)
            if context_root.tag != "context":
                raise XMLValidationError(
                    "Error: Context section must have 'context' as root element"
                )

            # Validate task distribution section
            task_root = ET.fromstring(task_section)
            if task_root.tag != "task_distribution":
                raise XMLValidationError(
                    "Error: Task distribution section must have 'task_distribution' as root element"
                )

            root = task_root
        else:
            # Fallback to old format with just task_distribution
            root = ET.fromstring(xml_distribution)
            if root.tag != "task_distribution":
                return "Error: Root element must be 'task_distribution'"

        required_agents = [
            AgentIdentifier.GENERATE_CLASS,
            AgentIdentifier.GENERATE_JS,
            AgentIdentifier.TEXT,
            AgentIdentifier.SVG,
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

        context_info = " with context" if "<context>" in xml_distribution else ""
        return f"Validation passed{context_info}: {task_count} tasks distributed across {len(found_agents)} agents"

    except ET.ParseError as e:
        raise XMLValidationError(f"Error: Invalid XML format - {str(e)}")
