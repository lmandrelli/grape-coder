from typing import Any

from strands import Agent
from strands.multiagent.base import MultiAgentBase
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from grape_coder.agents.common import (
    XMLValidatorNode,
    XMLValidationError,
    extract_review_tasks_from_xml,
)
from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_conversation_tracker, get_tool_tracker
from grape_coder.tools.tool_limit_hooks import get_tool_limit_hook

console = Console()


def display_tasks_markdown(xml_content: str) -> None:
    """Display tasks in a rich markdown formatted panel."""
    summary, tasks = extract_review_tasks_from_xml(xml_content)

    if not tasks:
        return

    priority_colors = {
        "CRITICAL": "red",
        "HIGH": "orange1",
        "MEDIUM": "yellow",
        "LOW": "green",
    }

    md_content = f"## Review Summary\n{summary}\n\n## Tasks ({len(tasks)})\n"

    for i, task in enumerate(tasks, 1):
        files = task.get("files", "N/A")
        description = task.get("description", "")
        priority = task.get("priority", "MEDIUM")
        color = priority_colors.get(priority.upper(), "white")
        md_content += (
            f"### {i}. [{priority.upper()}]({color}) {files}\n{description}\n\n"
        )

    md = Markdown(md_content)

    panel = Panel(
        md,
        title="[bold cyan]Code Revision Tasks[/bold cyan]",
        expand=False,
        border_style="green",
    )

    console.print(panel)


def create_task_generator_agent() -> MultiAgentBase:
    """Create a task generator agent that converts reviews to actionable tasks."""

    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.REVIEW_TASK_GENERATOR)

    system_prompt = """You are a Task Generation Specialist. You receive natural language code reviews and convert them into structured, actionable tasks for the code revision agent.

Your role is to parse the review and create specific, actionable tasks organized by priority. You must also provide a COMPLETE summary that gives the code revisor a comprehensive understanding of the work context.

SUMMARY REQUIREMENTS:
The summary must be thorough and include:
1. Overall project type and purpose (what kind of website/application is this?)
2. The overall state of the codebase - what's working, what's broken
3. Main weaknesses that need addressing
4. Any design decisions or technical approaches that were taken
5. Specific areas that need the most attention

TASK GENERATION RULES:
- List the most important fixes first (blocking issues, critical bugs)
- Specify which files need to be modified
- Provide a clear description of what to fix
- Be specific about CSS properties, HTML elements, and exact issues
- Make tasks actionable and specific
- Include priority levels (CRITICAL, HIGH, MEDIUM, LOW)
- Group related fixes together when possible

CRITICAL INSTRUCTION:
Extract specific, actionable tasks from the review. Be precise about file names and exact changes needed. Provide a comprehensive summary.

Output your tasks in the required XML format:
<review>
    <summary>
        A comprehensive summary of the review including:
        - Project type and purpose
        - Overall state of the codebase
        - Main weaknesses
        - Specific areas needing attention
    </summary>
    <tasks>
        <task>
            <priority>CRITICAL|HIGH|MEDIUM|LOW</priority>
            <files>file1.html, file2.css</files>
            <description>Fix the layout issue where elements overlap on mobile screens</description>
        </task>
        <task>
            <priority>HIGH</priority>
            <files>styles.css</files>
            <description>Add missing hover states for interactive elements</description>
        </task>
    </tasks>
</review>"""

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        name=AgentIdentifier.REVIEW_TASK_GENERATOR,
        description=get_agent_description(AgentIdentifier.REVIEW_TASK_GENERATOR),
        hooks=[
            get_tool_tracker(AgentIdentifier.REVIEW_TASK_GENERATOR),
            get_conversation_tracker(AgentIdentifier.REVIEW_TASK_GENERATOR),
            get_tool_limit_hook(AgentIdentifier.REVIEW_TASK_GENERATOR),
        ],
        callback_handler=None,
    )

    return XMLValidatorNode(
        agent=agent,
        validate_fn=validate_tasks,
        extract_fn=extract_tasks_xml,
        success_callback=display_tasks_markdown,
    )


def extract_tasks_xml(content: str) -> str:
    """Extract XML content from task generator response.

    Searches for <review> tags in the content.

    Args:
        content: Raw agent response content.

    Returns:
        Extracted XML string.
    """
    import re

    review_pattern = r"<review>.*?</review>"

    review_match = re.search(review_pattern, content, re.DOTALL)

    if review_match:
        return review_match.group(0)

    xml_pattern = r"<[^>]+>.*?</[^>]+>"
    xml_match = re.search(xml_pattern, content, re.DOTALL)

    if xml_match:
        return xml_match.group(0)

    return content


def validate_tasks(xml_content: str) -> str:
    """Validate XML tasks format from task generator agent.

    Validates that the XML contains required <review> section
    with summary and tasks.

    Args:
        xml_content: XML string containing review tasks.

    Returns:
        Validation success message.

    Raises:
        XMLValidationError: If XML structure is invalid.
    """
    import xml.etree.ElementTree as ET

    try:
        if "<review>" in xml_content:
            start = xml_content.find("<review>")
            end = xml_content.find("</review>") + len("</review>")

            review_section = xml_content[start:end]

            root = ET.fromstring(review_section)
            if root.tag != "review":
                raise XMLValidationError(
                    "Error: Review section must have 'review' as root element"
                )
        else:
            root = ET.fromstring(xml_content)
            if root.tag != "review":
                raise XMLValidationError("Error: Root element must be 'review'")

        summary_elem = root.find("summary")
        tasks_elem = root.find("tasks")
        tasks_elems = tasks_elem.findall("task") if tasks_elem is not None else []

        if summary_elem is None:
            raise XMLValidationError("Error: Missing 'summary' element in review")

        if not tasks_elems:
            raise XMLValidationError("Error: No 'task' elements found in review")

        task_count = len(tasks_elems)

        return f"Validation passed: review with summary and {task_count} tasks"

    except ET.ParseError as e:
        raise XMLValidationError(f"Error: Invalid XML format - {str(e)}")
