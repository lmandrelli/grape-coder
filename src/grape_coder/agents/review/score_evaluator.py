from typing import Any

from strands import Agent
from strands.multiagent.base import MultiAgentBase
from rich.console import Console
from rich.table import Table

from grape_coder.nodes.XML_validator_node import XMLValidatorNode, XMLValidationError
from grape_coder.agents.common import extract_scores_from_xml
from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_conversation_tracker, get_tool_tracker
from grape_coder.tools.tool_limit_hooks import get_tool_limit_hook

console = Console()


def display_scores_table(scores: dict) -> None:
    """Display scores in a rich formatted table."""
    table = Table(title="Code Review Scores")

    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Score", style="magenta")
    table.add_column("Status", style="green")

    critical_threshold = 17
    standard_threshold = 15

    category_names = {
        "code_validity": "Code Validity",
        "integration": "Integration",
        "responsiveness": "Responsiveness",
        "best_practices": "Best Practices",
        "accessibility": "Accessibility",
    }

    for category, name in category_names.items():
        score = scores.get(category, 0)
        score_str = f"{score}/20"

        if category in ["code_validity", "integration"]:
            if score >= critical_threshold:
                status = "✓ PASS (Critical)"
                style = "green"
            else:
                status = "✗ FAIL (Critical)"
                style = "red"
        else:
            if score >= standard_threshold:
                status = "✓ PASS"
                style = "green"
            else:
                status = "✗ FAIL"
                style = "yellow"

        table.add_row(name, score_str, f"[{style}]{status}[/]")

    console.print(table)


def create_score_evaluator_agent() -> MultiAgentBase:
    """Create a score evaluator agent that assesses code quality."""

    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.SCORE_EVALUATOR)

    system_prompt = """You are a Score Evaluator. You receive natural language code reviews and evaluate the quality of the code in different categories.

Your role is to assess the review and assign scores from 0 to 20 for each category. You must be CRITICAL and HONEST - do not be lenient.

CRITICAL EVALUATION GUIDELINES:
- Be skeptical of high scores. If the review mentions ANY issues, the score should reflect that.
- A score of 20 means PERFECT - no issues, no improvements possible. This is extremely rare.
- A score of 17-19 means EXCELLENT - minor issues only.
- A score of 14-16 means GOOD - several issues that should be fixed.
- A score of 11-13 means ACCEPTABLE - many issues need attention.
- A score of 8-10 means BELOW AVERAGE - significant problems.
- A score of 5-7 means POOR - major issues.
- A score of 1-4 means VERY POOR - barely functional.
- A score of 0 means CRITICAL FAILURE - does not work.

CATEGORIES:
1. CODE_VALIDITY: Is the code syntactically correct and free of bugs?
   - Check for syntax errors, missing elements, broken references
   - Are HTML tags properly closed?
   - Are CSS and JavaScript syntax correct?
   - Look for missing semicolons, unclosed tags, undefined variables
   - This is a CRITICAL category - must be 17+ for approval

2. INTEGRATION: Are all files properly linked and working together?
   - Are CSS files linked in HTML?
   - Are JavaScript files properly included?
   - Are SVG files correctly referenced?
   - Will the browser handle all resources correctly?
   - Check for correct paths and file references
   - This is a CRITICAL category - must be 17+ for approval

3. RESPONSIVENESS: Does the layout work across different screen sizes?
   - Mobile, tablet, desktop layouts
   - Media queries, flexible grids
   - Touch-friendly elements on mobile
   - Are there actual media queries, or just theoretical ones?
   - Must be 15+ for approval

4. BEST_PRACTICES: Does the code follow modern web development standards?
   - Semantic HTML (use <header>, <main>, <nav>, <section>, etc.)
   - Modern CSS (Flexbox, Grid, CSS Variables)
   - Proper use of classes and IDs
   - Code organization and readability
   - Avoid inline styles, avoid deprecated properties
   - Must be 15+ for approval

5. ACCESSIBILITY: Is the site accessible to users with disabilities?
   - Alt text for images
   - Proper heading hierarchy (h1 -> h2 -> h3)
   - Focus states for keyboard navigation
   - Color contrast
   - ARIA labels where needed
   - Must be 15+ for approval

VALIDATION INSTRUCTIONS:
- Your score should reflect the actual quality, not what you wish it was
- A single blocking issue in code_validity or integration should result in FAIL

CRITICAL INSTRUCTION:
Output your evaluation in the required XML format:
<review_scores>
    <code_validity>
        <score>0-20</score>
    </code_validity>
    <integration>
        <score>0-20</score>
    </integration>
    <responsiveness>
        <score>0-20</score>
    </responsiveness>
    <best_practices>
        <score>0-20</score>
    </best_practices>
    <accessibility>
        <score>0-20</score>
    </accessibility>
</review_scores>"""

    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        name=AgentIdentifier.SCORE_EVALUATOR,
        description=get_agent_description(AgentIdentifier.SCORE_EVALUATOR),
        hooks=[
            get_tool_tracker(AgentIdentifier.SCORE_EVALUATOR),
            get_conversation_tracker(AgentIdentifier.SCORE_EVALUATOR),
            get_tool_limit_hook(AgentIdentifier.SCORE_EVALUATOR),
        ],
        callback_handler=None,
    )

    return XMLValidatorNode(
        agent=agent,
        validate_fn=validate_scores,
        extract_fn=extract_scores_xml,
        success_callback=display_scores_callback,
    )


def display_scores_callback(xml_content: str) -> None:
    """Callback to display scores table after successful validation."""
    scores = extract_scores_from_xml(xml_content)
    if scores:
        display_scores_table(scores)


def extract_scores_xml(content: str) -> str:
    """Extract XML content from score evaluator response.

    Searches for <review_scores> tags in the content.

    Args:
        content: Raw agent response content.

    Returns:
        Extracted XML string.
    """
    import re

    scores_pattern = r"<review_scores>.*?</review_scores>"

    scores_match = re.search(scores_pattern, content, re.DOTALL)

    if scores_match:
        return scores_match.group(0)

    xml_pattern = r"<[^>]+>.*?</[^>]+>"
    xml_match = re.search(xml_pattern, content, re.DOTALL)

    if xml_match:
        return xml_match.group(0)

    return content


def validate_scores(xml_content: str) -> str:
    """Validate XML scores format from score evaluator agent.

    Validates that the XML contains required <review_scores> section
    with all required score categories.

    Args:
        xml_content: XML string containing review scores.

    Returns:
        Validation success message.

    Raises:
        XMLValidationError: If XML structure is invalid.
    """
    import xml.etree.ElementTree as ET

    try:
        if "<review_scores>" in xml_content:
            start = xml_content.find("<review_scores>")
            end = xml_content.find("</review_scores>") + len("</review_scores>")

            scores_section = xml_content[start:end]

            root = ET.fromstring(scores_section)
            if root.tag != "review_scores":
                raise XMLValidationError(
                    "Error: Scores section must have 'review_scores' as root element"
                )
        else:
            root = ET.fromstring(xml_content)
            if root.tag != "review_scores":
                raise XMLValidationError("Error: Root element must be 'review_scores'")

        required_categories = [
            "code_validity",
            "integration",
            "responsiveness",
            "best_practices",
            "accessibility",
        ]
        found_categories = [child.tag for child in root]

        missing = [cat for cat in required_categories if cat not in found_categories]
        if missing:
            raise XMLValidationError(
                f"Warning: Missing score categories: {', '.join(missing)}"
            )

        return f"Validation passed: scores for {len(found_categories)} categories"

    except ET.ParseError as e:
        raise XMLValidationError(f"Error: Invalid XML format - {str(e)}")
