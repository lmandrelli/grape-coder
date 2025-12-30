from strands import Agent
from strands.multiagent.base import MultiAgentBase

from grape_coder.nodes.XML_validator_node import XMLValidatorNode, XMLValidationError
from grape_coder.agents.review.review_xml_utils import extract_xml_by_tags
from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_conversation_tracker, get_tool_tracker
from grape_coder.tools.tool_limit_hooks import get_tool_limit_hook


def create_orchestrator_agent() -> MultiAgentBase:
    """Create an orchestrator agent that distributes tasks to specialized agents"""

    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.ORCHESTRATOR)

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

    return XMLValidatorNode(
        agent=agent,
        validate_fn=validate_distribution,
        extract_fn=orchestrator_xml_extractor,
    )


def orchestrator_xml_extractor(content: str) -> str:
    return extract_xml_by_tags(content, ["context", "task_distribution"])


def validate_distribution(xml_distribution: str) -> str:
    """Validate XML task distribution format from orchestrator agent.

    Validates that the XML contains required <context> and <task_distribution>
    sections with valid structure and all required agent tags.

    Args:
        xml_distribution: XML string containing context and task distribution.

    Returns:
        Validation success message with task count.

    Raises:
        XMLValidationError: If XML structure is invalid or required sections are missing.
    """
    import xml.etree.ElementTree as ET

    try:
        if (
            "<context>" in xml_distribution
            and "<task_distribution>" in xml_distribution
        ):
            context_match = xml_distribution.find("<context>")
            context_end = xml_distribution.find("</context>") + len("</context>")
            task_start = xml_distribution.find("<task_distribution>")

            context_section = xml_distribution[context_match:context_end]
            task_section = xml_distribution[task_start:]

            context_root = ET.fromstring(context_section)
            if context_root.tag != "context":
                raise XMLValidationError(
                    "Error: Context section must have 'context' as root element"
                )

            task_root = ET.fromstring(task_section)
            if task_root.tag != "task_distribution":
                raise XMLValidationError(
                    "Error: Task distribution section must have 'task_distribution' as root element"
                )

            root = task_root
        else:
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
