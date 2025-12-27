"""
TODO(Luca):
    redo with logic like `orchestrator`
"""

from typing import Any

from strands import Agent
from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.config import get_config_manager
from grape_coder.display import get_conversation_tracker, get_tool_tracker

from .review_data import ReviewData
from .reviewer import (
    SCORE_CATEGORIES,
    CategoryScore,
    ReviewValidationError,
    extract_score_xml,
    parse_score_xml,
)


class ScoreEvaluatorAgent(MultiAgentBase):
    def __init__(
        self,
        agent: Agent,
        max_retries: int = 3,
        node_name: str = "score_evaluator_agent",
    ):
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
        try:
            review_text = str(task)
            last_error = None

            for attempt in range(self.max_retries + 1):
                try:
                    if attempt == 0:
                        prompt = f"""REVIEW TO EVALUATE:
<review>
{review_text}
</review>

Provide your evaluation in the following XML format:

<review_scores>
    <user_prompt_compliance>
        <score>0-20</score>
    </user_prompt_compliance>
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
                    else:
                        prompt = f"""Your previous score evaluation attempt had formatting issues:

<last_attempt>
{last_error}
</last_attempt>

Please generate the score evaluation again using the correct XML format. Ensure:
1. Root element is <review_scores>
2. All 6 categories are present: user_prompt_compliance, code_validity, integration, responsiveness, best_practices, accessibility
3. Each category has a <score> element with an integer between 0 and 20

Original review:
<review>
{review_text}
</review>"""

                    response = await self.agent.invoke_async(prompt)
                    response_text = str(response)

                    xml_content = extract_score_xml(response_text)
                    category_scores = parse_score_xml(xml_content)

                    # Create ReviewData with scores
                    review_data = ReviewData(
                        category_scores=category_scores, raw_output=response_text
                    )

                    # Store in invocation_state for sharing with other nodes
                    if invocation_state is None:
                        invocation_state = {}
                    invocation_state["score_review_data"] = review_data

                    agent_result = AgentResult(
                        stop_reason="end_turn",
                        state={"review_data": review_data},
                        metrics=EventLoopMetrics(),
                        message=Message(
                            role="assistant", content=[ContentBlock(text=response_text)]
                        ),
                    )

                    agent_result = AgentResult(
                        stop_reason="end_turn",
                        state={"review_data": review_data},
                        metrics=EventLoopMetrics(),
                        message=Message(
                            role="assistant", content=[ContentBlock(text=response_text)]
                        ),
                    )

                    return MultiAgentResult(
                        status=Status.COMPLETED,
                        results={
                            self.node_name: NodeResult(
                                result=agent_result, status=Status.COMPLETED
                            )
                        },
                    )

                except ReviewValidationError as e:
                    last_error = str(e)
                    if attempt == self.max_retries:
                        default_scores = [
                            CategoryScore(name=cat, score=10)
                            for cat in SCORE_CATEGORIES
                        ]
                        review_data = ReviewData(
                            category_scores=default_scores,
                            raw_output=f"Score evaluation failed after retries. Error: {str(e)}",
                        )

                        # Store in invocation_state
                        if invocation_state is None:
                            invocation_state = {}
                        invocation_state["score_review_data"] = review_data

                        agent_result = AgentResult(
                            stop_reason="end_turn",
                            state={"review_data": review_data},
                            metrics=EventLoopMetrics(),
                            message=Message(
                                role="assistant",
                                content=[
                                    ContentBlock(
                                        text=f"Score evaluation failed after retries. Using default scores. Error: {str(e)}"
                                    )
                                ],
                            ),
                        )

                        agent_result = AgentResult(
                            stop_reason="end_turn",
                            state={"review_data": review_data},
                            metrics=EventLoopMetrics(),
                            message=Message(
                                role="assistant",
                                content=[
                                    ContentBlock(
                                        text=f"Score evaluation failed after retries. Using default scores. Error: {str(e)}"
                                    )
                                ],
                            ),
                        )
                        return MultiAgentResult(
                            status=Status.COMPLETED,
                            results={
                                self.node_name: NodeResult(
                                    result=agent_result, status=Status.COMPLETED
                                )
                            },
                        )
                    continue

            agent_result = AgentResult(
                stop_reason="guardrail_intervened",
                state=Status.FAILED,
                metrics=EventLoopMetrics(),
                message=Message(
                    role="assistant",
                    content=[ContentBlock(text="Score evaluation failed")],
                ),
            )
            return MultiAgentResult(
                status=Status.FAILED,
                results={
                    self.node_name: NodeResult(
                        result=agent_result, status=Status.FAILED
                    )
                },
            )

        except Exception as e:
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
                    self.node_name: NodeResult(
                        result=agent_result, status=Status.FAILED
                    )
                },
            )


def create_score_evaluator_agent() -> ScoreEvaluatorAgent:
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.REVIEW)

    system_prompt = """You are a Score Evaluator. You receive natural language code reviews and evaluate the quality of the code in different categories.

Your role is to assess the review and assign scores from 0 to 20 for each category.

CATEGORIES:
1. USER_PROMPT_COMPLIANCE: Does the code fulfill the original user requirements?
   - Don't be too harsh if the prompt was vague or ambiguous
   - Focus on whether the core intent was addressed
   - 15+ is acceptable for this category

2. CODE_VALIDITY: Is the code syntactically correct and free of bugs?
   - Check for syntax errors, missing elements, broken references
   - Are HTML tags properly closed?
   - Are CSS and JavaScript syntax correct?
   - This is a CRITICAL category - must be 17+ for approval

3. INTEGRATION: Are all files properly linked and working together?
   - Are CSS files linked in HTML?
   - Are JavaScript files properly included?
   - Are SVG files correctly referenced?
   - Will the browser handle all resources correctly?
   - This is a CRITICAL category - must be 17+ for approval

4. RESPONSIVENESS: Does the layout work across different screen sizes?
   - Mobile, tablet, desktop layouts
   - Media queries, flexible grids
   - Touch-friendly elements on mobile
   - Must be 15+ for approval

5. BEST_PRACTICES: Does the code follow modern web development standards?
   - Semantic HTML
   - Modern CSS (Flexbox, Grid, CSS Variables)
   - Proper use of classes and IDs
   - Code organization and readability
   - Must be 15+ for approval

6. ACCESSIBILITY: Is the site accessible to users with disabilities?
   - Alt text for images
   - Proper heading hierarchy
   - Focus states for keyboard navigation
   - Color contrast
   - Must be 15+ for approval

APPROVAL THRESHOLDS:
- Overall average score must be >= 16
- Code validity must be >= 17 (CRITICAL)
- Integration must be >= 17 (CRITICAL)
- All other categories must be >= 15

CRITICAL INSTRUCTION:
Evaluate the review objectively and assign appropriate scores based on the quality criteria and approval thresholds. Output your evaluation in the required XML format."""

    agent = Agent(
        model=model,
        tools=[],
        system_prompt=system_prompt,
        name="score_evaluator",
        description="Evaluates code quality scores from natural language reviews",
        hooks=[
            get_tool_tracker(AgentIdentifier.REVIEW),
            get_conversation_tracker(AgentIdentifier.REVIEW),
        ],
    )

    return ScoreEvaluatorAgent(agent, max_retries=3, node_name="score_evaluator_agent")
