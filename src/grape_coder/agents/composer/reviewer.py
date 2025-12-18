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
MIN_APPROVAL_SCORE = 16


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

    def _extract_original_user_prompt(self, task: str | list[ContentBlock], invocation_state: dict[str, Any] | None) -> str | None:
        """Extract the original user prompt from available sources.
        
        Tries multiple strategies:
        1. Look in invocation_state for 'original_user_prompt' key
        2. Parse the task content for 'ORIGINAL USER REQUEST:' section
        3. Return None if not found
        """
        import re
        
        # Strategy 1: Check invocation_state
        if invocation_state and 'original_user_prompt' in invocation_state:
            return invocation_state['original_user_prompt']
        
        # Strategy 2: Extract text from task and parse for patterns
        # Handle both string and list[ContentBlock] cases
        if isinstance(task, str):
            task_str = task
        elif isinstance(task, list):
            # Extract text from ContentBlock list
            texts = []
            for item in task:
                if hasattr(item, 'text') and item.text:
                    texts.append(item.text)
                elif isinstance(item, dict) and 'text' in item:
                    texts.append(item['text'])
            task_str = "\n".join(texts)
        else:
            task_str = str(task)
        
        # Look for ORIGINAL USER REQUEST pattern in the task content
        pattern = r'ORIGINAL USER REQUEST:\s*(.+?)(?=\n\s*Execute the following|$)'
        match = re.search(pattern, task_str, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Also check for USER TASK pattern (fallback format)
        pattern2 = r'USER TASK:\s*(.+?)(?=\n\s*\n|$)'
        match2 = re.search(pattern2, task_str, re.DOTALL | re.IGNORECASE)
        if match2:
            return match2.group(1).strip()
        
        return None

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
        
        # Extract the original user prompt from task content or invocation_state
        original_user_prompt = self._extract_original_user_prompt(task, invocation_state)
        print(original_user_prompt)
        for attempt in range(self.max_retries + 1):
            try:
                # Build prompt based on attempt
                if attempt == 0:
                    # Include original user prompt for context if available
                    if original_user_prompt:
                        prompt = f"""ORIGINAL USER REQUEST:
<user_prompt>
{original_user_prompt}
</user_prompt>

Please review the code files created for this request. Use the tools available to explore and read the files, then provide your review."""
                    else:
                        prompt = "Please review the code files in the workspace. Use the tools available to explore and read the files, then provide your review."
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
    system_prompt = """You are the Senior Design & Product Reviewer. You are a critical quality assurance agent in a collaborative multi-agent workflow. 

        YOUR MISSION:
        Ensure the website is not just "functional," but professional, modern, and high-converting. If a website "works" but looks unprofessional, dated, or boring, it is a FAILURE. You must push the code agent to implement high-end, modern web experiences.

        CRITICAL DESIGN PHILOSOPHY:
        We value "Premium Polish" over "Visual Noise." 
        - Animations must be SUBTLE and PURPOSEFUL (e.g., smooth opacity transitions, slight transform shifts).
        - NEVER allow distracting or amateurish animations like blinking, constant looping, or jarring movements.
        - Focus on Micro-interactions: how a button feels when hovered, how a menu slides in, how content fades in gracefully.

        REVIEW CATEGORIES (Scored 0-20):

        1. VISUAL_AESTHETICS (The "Look and Feel")
        - Does it look modern? (e.g., proper use of whitespace, consistent border-radii, modern font pairings).
        - Is the color palette harmonious? Is there visual "polish" (subtle shadows, glassmorphism, professional icons)?
        
        2. UX_AND_HIERARCHY (User Experience)
        - Is there a clear Call to Action (CTA)? Is the "Hero" section impactful?
        - Is the information architecture logical? Does the user know what to do next?

        3. PROMPT_COMPLIANCE (Business Goals)
        - Does it fulfill the original user request?
        - If the user asked for "Luxury," is it actually luxurious, or just a basic template?

        4. RESPONSIVENESS (Fluidity)
        - Does the layout adapt elegantly across mobile, tablet, and desktop?
        - Are touch targets (buttons) large enough? Are images responsive?

        5. TECHNICAL_INTEGRATION (File Linking & Structure)
        - Are all CSS and JS files correctly linked with valid paths?
        - Is the HTML semantic (<header>, <main>, <section>) rather than just <div> soup?

        6. MOTION_REFINEMENT & DETAIL (Modern Polish)
        - Does the code use modern CSS (Flexbox, Grid, CSS Variables)?
        - INTERACTIVE QUALITY: Use smooth `transition: all 0.3s ease;` for hovers. 
        - CONTENT REFINEMENT: Use subtle entrance animations (e.g., `fade-in-up`) for sections.
        - AVOID: No blinking, no marquee-style movement, no "shaking" elements unless contextually required.

        SCORING GUIDELINES:
        - 0-10: Critical failures or extremely amateur design.
        - 11-14: "Standard/Basic." Code works, but looks like a student project. NEEDS IMPROVEMENT.
        - 15-17: "Professional." Good enough for a real business.
        - 18-20: "Exceptional." Looks like a premium, custom-designed site.

        REQUIRED XML OUTPUT FORMAT:
        You MUST output your review in this exact XML format. Be specific about file names and CSS properties in your remarks.

        <code_review>
            <blocking_issues>
                <issue>The 'styles.css' file is not linked in index.html.</issue>
                <issue>The button animations are too aggressive (blinking); replace with a smooth background-color transition.</issue>
            </blocking_issues>

            <prompt_compliance>
                <score>15</score>
                <remarks>
                    <remark>Fulfills the request for a 3-page site, but the 'Services' section lacks the requested pricing table.</remark>
                </remarks>
            </prompt_compliance>

            <code_validity>
                <score>18</score>
                <remarks>
                    <remark>Clean HTML5 structure and valid CSS logic.</remark>
                </remarks>
            </code_validity>

            <integration>
                <score>20</score>
                <remarks>
                    <remark>All assets and scripts are correctly mapped.</remark>
                </remarks>
            </integration>

            <responsiveness>
                <score>12</score>
                <remarks>
                    <remark>The navigation menu breaks on screens smaller than 400px. Use a hamburger menu pattern.</remark>
                </remarks>
            </responsiveness>

            <completeness>
                <score>14</score>
                <remarks>
                    <remark>The contact form exists but lacks a 'success' state or validation styling.</remark>
                </remarks>
            </completeness>

            <best_practices>
                <score>10</score>
                <remarks>
                    <remark>Design is visually dated. Use CSS variables for colors and add more whitespace (padding: 4rem) to the hero section.</remark>
                    <remark>Instead of static links, use buttons with a subtle hover effect: 'transform: translateY(-2px); shadow: 0 4px 12px rgba(0,0,0,0.1);'.</remark>
                </remarks>
            </best_practices>

            <summary>
                Overall the site is functional but visually 'generic.' To reach a score of 18+, the agent must improve the visual hierarchy and replace the distracting blinking elements with sophisticated, smooth CSS transitions.
            </summary>
        </code_review>

        CRITICAL INSTRUCTION:
        You are a reviewer only. Do not modify code. Provide detailed, actionable directives. If the design is mediocre or the animations are "cheap," keep the score below 18 to force a revision cycle."""

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
