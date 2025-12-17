import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, List

from strands import Agent
from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_tool_tracker, get_conversation_tracker
from grape_coder.tools.work_path import (
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)
from grape_coder.tools.tool_limit_hooks import get_tool_limit_hook


# Review categories that must be present in the XML
REVIEW_CATEGORIES = [
    "prompt_compliance",
    "code_validity",
    "integration",
    "responsiveness",
    "completeness",
    "best_practices",
]

# Minimum score required for approval (out of 20)
MIN_APPROVAL_SCORE = 18


@dataclass
class CategoryReview:
    """Represents a single category review with score and remarks."""
    name: str
    score: int
    remarks: List[str] = field(default_factory=list)


@dataclass
class ReviewResult:
    """Parsed review result from XML."""
    blocking_issues: List[str] = field(default_factory=list)
    categories: List[CategoryReview] = field(default_factory=list)
    summary: str = ""
    
    def is_approved(self) -> bool:
        """Check if the review passes approval criteria."""
        # Fail if there are blocking issues
        if self.blocking_issues:
            return False
        
        # Fail if any category score is below minimum
        for category in self.categories:
            if category.score < MIN_APPROVAL_SCORE:
                return False
        
        return True
    
    def get_feedback_for_revision(self) -> str:
        """Generate feedback message for the code agent when revision is needed."""
        feedback_parts = []
        
        # Add blocking issues first
        if self.blocking_issues:
            feedback_parts.append("🚫 BLOCKING ISSUES (must fix):")
            for issue in self.blocking_issues:
                feedback_parts.append(f"  - {issue}")
            feedback_parts.append("")
        
        # Add categories that need improvement
        feedback_parts.append("📋 REVIEW FEEDBACK BY CATEGORY:")
        for category in self.categories:
            status = "✅" if category.score >= MIN_APPROVAL_SCORE else "❌"
            feedback_parts.append(f"\n{status} {category.name.upper()} ({category.score}/20):")
            if category.remarks:
                for remark in category.remarks:
                    feedback_parts.append(f"  - {remark}")
            elif category.score < MIN_APPROVAL_SCORE:
                feedback_parts.append("  - Score below minimum, needs improvement")
        
        if self.summary:
            feedback_parts.append(f"\n📝 SUMMARY: {self.summary}")
        
        return "\n".join(feedback_parts)


class ReviewValidationError(Exception):
    """Custom exception for review XML validation errors."""
    pass


def parse_review_xml(xml_content: str) -> ReviewResult:
    """Parse and validate the review XML content.
    
    Args:
        xml_content: Raw XML string from the reviewer
        
    Returns:
        ReviewResult object with parsed data
        
    Raises:
        ReviewValidationError: If XML is malformed or missing required elements
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ReviewValidationError(f"Invalid XML format: {str(e)}")
    
    if root.tag != "code_review":
        raise ReviewValidationError(
            f"Root element must be 'code_review', got '{root.tag}'"
        )
    
    result = ReviewResult()
    
    # Parse blocking issues
    blocking_elem = root.find("blocking_issues")
    if blocking_elem is not None:
        for issue in blocking_elem.findall("issue"):
            if issue.text and issue.text.strip():
                result.blocking_issues.append(issue.text.strip())
    
    # Parse each category
    for category_name in REVIEW_CATEGORIES:
        category_elem = root.find(category_name)
        if category_elem is None:
            raise ReviewValidationError(f"Missing required category: {category_name}")
        
        # Get score
        score_elem = category_elem.find("score")
        if score_elem is None or not score_elem.text:
            raise ReviewValidationError(f"Missing score for category: {category_name}")
        
        try:
            score = int(score_elem.text.strip())
            if not 0 <= score <= 20:
                raise ReviewValidationError(
                    f"Score for {category_name} must be between 0 and 20, got {score}"
                )
        except ValueError:
            raise ReviewValidationError(
                f"Invalid score format for {category_name}: {score_elem.text}"
            )
        
        # Get remarks
        remarks = []
        remarks_elem = category_elem.find("remarks")
        if remarks_elem is not None:
            for remark in remarks_elem.findall("remark"):
                if remark.text and remark.text.strip():
                    remarks.append(remark.text.strip())
        
        result.categories.append(CategoryReview(
            name=category_name,
            score=score,
            remarks=remarks
        ))
    
    # Parse summary
    summary_elem = root.find("summary")
    if summary_elem is not None and summary_elem.text:
        result.summary = summary_elem.text.strip()
    
    return result


def extract_review_xml(content: str) -> str:
    """Extract XML content from model response.
    
    Args:
        content: Raw response from the model
        
    Returns:
        Extracted XML string
    """
    # Try to find XML content between <code_review> and </code_review>
    pattern = r"<code_review>.*?</code_review>"
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        return match.group(0)
    
    # Return original content if no XML found
    return content


class ReviewValidatorNode(MultiAgentBase):
    """Custom node that validates the reviewer's XML output with retry logic."""

    def __init__(self, agent: Agent, max_retries: int = 3, node_name: str = "review_agent"):
        """Initialize the review validator node.
        
        Args:
            agent: The reviewer agent
            max_retries: Maximum number of retry attempts for XML validation
            node_name: Name to use for this node in the results dict (default: "review_agent")
        """
        super().__init__()
        self.agent = agent
        self.max_retries = max_retries
        self.node_name = node_name

    async def invoke_async(
        self,
        task: str | list[ContentBlock],
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> MultiAgentResult:
        """Execute review with XML validation and retry logic."""
        initial_prompt = task if isinstance(task, str) else str(task)
        current_prompt = initial_prompt
        last_error = None
        xml_content = None

        for attempt in range(self.max_retries + 1):
            try:
                # Build prompt based on attempt
                if attempt == 0:
                    prompt = str(current_prompt)
                else:
                    prompt = f"""Your previous review attempt had formatting issues:

<last_attempt>
{current_prompt}
</last_attempt>

Error encountered:
<error>
{last_error}
</error>

Please provide your review again using the correct XML format. Ensure:
1. Root element is <code_review>
2. All 6 categories are present: prompt_compliance, code_validity, integration, responsiveness, completeness, best_practices
3. Each category has a <score> (0-20) and <remarks> section
4. Include <blocking_issues> section (can be empty)
5. Include <summary> section"""

                # Get model response
                response = await self.agent.invoke_async(prompt)
                response_text = str(response)
                
                # Extract and validate XML
                xml_content = extract_review_xml(response_text)
                review_result = parse_review_xml(xml_content)
                
                # If we get here, XML is valid
                # Store the parsed result in the message for the quality checker
                agent_result = AgentResult(
                    stop_reason="end_turn",
                    state={
                        "review_result": review_result,
                        "xml_content": xml_content,
                    },
                    metrics=EventLoopMetrics(),
                    message=Message(
                        role="assistant", 
                        content=[ContentBlock(text=xml_content)]
                    ),
                )

                return MultiAgentResult(
                    status=Status.COMPLETED,
                    results={
                        self.node_name: NodeResult(
                            result=agent_result, 
                            status=Status.COMPLETED
                        )
                    },
                )

            except ReviewValidationError as e:
                last_error = str(e)
                if xml_content:
                    current_prompt = xml_content
                
                if attempt == self.max_retries:
                    # Max retries reached - return error but allow pipeline to continue
                    # with a default "not approved" state
                    error_msg = f"Review XML validation failed after {self.max_retries + 1} attempts: {last_error}"
                    
                    # Create a default failed review result
                    default_review = ReviewResult(
                        blocking_issues=["Review format validation failed - manual review required"],
                        summary=error_msg
                    )
                    
                    agent_result = AgentResult(
                        stop_reason="guardrail_intervened",
                        state={
                            "review_result": default_review,
                            "validation_failed": True,
                        },
                        metrics=EventLoopMetrics(),
                        message=Message(
                            role="assistant",
                            content=[ContentBlock(text=error_msg)],
                        ),
                    )

                    return MultiAgentResult(
                        status=Status.COMPLETED,
                        results={
                            self.node_name: NodeResult(
                                result=agent_result, 
                                status=Status.COMPLETED
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
                        content=[ContentBlock(text=f"Error during review: {str(e)}")],
                    ),
                )

                return MultiAgentResult(
                    status=Status.FAILED,
                    results={
                        self.node_name: NodeResult(
                            result=agent_result, 
                            status=Status.FAILED
                        )
                    },
                )

        # Fallback return (should not be reached)
        agent_result = AgentResult(
            stop_reason="guardrail_intervened",
            state=Status.FAILED,
            metrics=EventLoopMetrics(),
            message=Message(
                role="assistant",
                content=[ContentBlock(text="Review validation failed unexpectedly")],
            ),
        )
        return MultiAgentResult(
            status=Status.FAILED,
            results={
                self.node_name: NodeResult(
                    result=agent_result, 
                    status=Status.FAILED
                )
            },
        )


def create_review_agent(work_path: str) -> ReviewValidatorNode:
    """Create an agent for reviewing website files with XML validation"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.REVIEW)

    # Create agent with review tools
    system_prompt = """You are the code reviewer agent in a multi-agent system for website creation.

    CONTEXT:
    You are a critical quality assurance agent in a collaborative multi-agent workflow designed to create complete, professional websites.
    You receive code files (HTML, CSS, JavaScript) from other agents and your role is to thoroughly review them for quality, correctness, and completeness.
    You are the final checkpoint before code is considered complete.

    YOUR ROLE:
    Review and analyze code files to ensure they meet professional standards. You cannot modify code directly - you can only suggest improvements and identify issues.
    Your responsibility is to validate the technical correctness, completeness, and quality of all code before it's finalized.

    REVIEW CATEGORIES (each scored 0-20):

    1. PROMPT_COMPLIANCE (User Requirements)
       - Does the website fulfill the original user request?
       - Are all requested features and pages implemented?
       - Does the design match the user's expectations?

    2. CODE_VALIDITY (Syntax & Correctness)
       - Verify HTML syntax and structure
       - Check CSS syntax and selector validity
       - Validate JavaScript logic and syntax
       - Ensure no broken or incomplete code

    3. INTEGRATION (Imports & File Linking)
       - Verify CSS files are properly linked in HTML (<link> tags)
       - Confirm JavaScript files are correctly imported (<script> tags)
       - Check that all external dependencies are properly referenced
       - Ensure file paths are correct and accessible

    4. RESPONSIVENESS (Mobile & Cross-browser)
       - Verify responsive design implementation (media queries, flexible layouts)
       - Check mobile-first approach and breakpoints
       - Ensure cross-browser compatibility considerations
       - Validate viewport meta tag and responsive units

    5. COMPLETENESS (Feature Implementation)
       - Verify all functionality is fully implemented
       - Check for missing features or incomplete implementations
       - Ensure no placeholder code or TODO comments remain
       - Validate that all user interactions work as expected

    6. BEST_PRACTICES (Code Quality)
       - Review code organization and structure
       - Check for semantic HTML usage
       - Verify CSS efficiency and maintainability
       - Ensure JavaScript follows best practices

    REVIEW PROCESS:
    1. Examine all provided files (HTML, CSS, JavaScript)
    2. Check imports and file linking
    3. Evaluate responsiveness across different screen sizes
    4. Verify complete implementation of all features
    5. Score each category from 0-20
    6. Identify critical blocking issues (if any)
    7. Provide specific, actionable feedback per category

    OUTPUT FORMAT (REQUIRED XML):
    You MUST output your review in this exact XML format:

    <code_review>
        <blocking_issues>
            <!-- List any critical issues that MUST be fixed before approval -->
            <!-- Leave empty if no blocking issues -->
            <issue>Description of critical blocking issue</issue>
        </blocking_issues>

        <prompt_compliance>
            <score>14</score>
            <remarks>
                <remark>Specific feedback about user requirements compliance</remark>
                <remark>Another specific point to improve</remark>
            </remarks>
        </prompt_compliance>

        <code_validity>
            <score>11</score>
            <remarks>
                <remark>Specific feedback about code syntax/validity</remark>
            </remarks>
        </code_validity>

        <integration>
            <score>13</score>
            <remarks>
                <remark>All imports correctly configured</remark>
            </remarks>
        </integration>

        <responsiveness>
            <score>16</score>
            <remarks>
                <remark>Missing media query for tablet breakpoint (768px)</remark>
                <remark>Footer not responsive on mobile</remark>
            </remarks>
        </responsiveness>

        <completeness>
            <score>8</score>
            <remarks>
                <remark>Contact form missing validation</remark>
            </remarks>
        </completeness>

        <best_practices>
            <score>19</score>
            <remarks>
                <remark>Good semantic HTML usage</remark>
            </remarks>
        </best_practices>

        <summary>
            Brief overall assessment of the code quality and main areas for improvement.
        </summary>
    </code_review>

    SCORING GUIDELINES:
    - 0-5: Critical failures, major issues
    - 6-10: Significant problems, needs substantial work
    - 11-14: Acceptable but needs improvement
    - 15-17: Good quality, minor improvements needed
    - 18-20: Excellent, meets or exceeds standards

    APPROVAL CRITERIA:
    - No blocking issues in <blocking_issues>
    - All category scores >= 18/20
    - If these criteria are not met, the code will be sent back for revision

    IMPORTANT: 
    - You are a reviewer only. Do not modify code.
    - Provide detailed, actionable feedback for each category.
    - Be specific about file names and line locations when possible.
    - The code agent will receive your feedback to implement fixes."""

    agent = Agent(
        model=model,
        tools=[
            list_files,
            read_file,
            grep_files,
            glob_files,
        ],
        system_prompt=system_prompt,
        name=AgentIdentifier.REVIEW,
        description=get_agent_description(AgentIdentifier.REVIEW),
        hooks=[
            get_tool_tracker(AgentIdentifier.REVIEW),
            get_conversation_tracker(AgentIdentifier.REVIEW),
            get_tool_limit_hook(AgentIdentifier.REVIEW),
        ],
    )

    return ReviewValidatorNode(agent=agent)
