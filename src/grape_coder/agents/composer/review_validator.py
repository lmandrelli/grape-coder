"""Review Validator Node for validating reviewer XML output.

This module provides validation for the structured XML review format
and ensures the review can be properly parsed by the quality checker.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, List, Optional

from strands import Agent
from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message


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
