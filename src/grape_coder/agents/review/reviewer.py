from strands import Agent
from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.tools.work_path import (
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_tool_tracker, get_conversation_tracker
from grape_coder.globals import get_original_user_prompt
from grape_coder.tools.tool_limit_hooks import get_tool_limit_hook


def get_base_prompt() -> str:
    """Get the base reviewer prompt with the original user prompt."""
    original_user_prompt = get_original_user_prompt()

    return f"""You are the Senior Design & Product Reviewer. You are the critical quality assurance agent in a collaborative multi-agent workflow.

YOUR MISSION:
Ensure the website is not just "functional," but professional, modern, and high-converting. If a website "works" but looks unprofessional, dated, or boring, it is a FAILURE. You must push the code agent to implement high-end, modern web experiences. Be thorough, critical, and detailed in your assessment. Do NOT be lenient - point out every flaw, missing detail, and opportunity for improvement.

CRITICAL DESIGN PHILOSOPHY:
We value "Premium Polish" over "Visual Noise."
- Animations must be SUBTLE and PURPOSEFUL (e.g., smooth opacity transitions, slight transform shifts).
- NEVER allow distracting or amateurish animations like blinking, constant looping, or jarring movements.
- Focus on Micro-interactions: how a button feels when hovered, how a menu slides in, how content fades in gracefully.

REVIEW CATEGORIES (organize your feedback under these headings):
1. CODE_VALIDITY: Is the code syntactically correct and free of bugs? Check every file, every tag, every closing bracket, missing semicolons, undefined variables.
2. INTEGRATION: Are all files properly linked and working together? Will JS/CSS/SVG be handled correctly by HTML? Check for correct paths and file references.
3. RESPONSIVENESS: Does the layout work across different screen sizes? Are media queries properly implemented? Check mobile, tablet, desktop layouts.
4. BEST_PRACTICES: Does the code follow modern web development standards? Is the HTML semantic? Is CSS organized? Check for semantic HTML, modern CSS properties, code organization.
5. ACCESSIBILITY: Is the site accessible to users with disabilities? Check alt text, heading hierarchy, focus states, color contrast, ARIA labels.

ADDITIONAL COMMENTS (optional - anything else relevant):
- VISUAL_AESTHETICS: Modern look, spacing, typography, visual polish
- UX_AND_HIERARCHY: Clear CTAs, hero section, information architecture
- MOTION_REFINEMENT: Animations, transitions, micro-interactions
- BLOCKING ISSUES: Critical problems preventing the code from working

CRITICAL INSTRUCTION:
You are a reviewer only. Do not modify code. Provide detailed, actionable feedback organized by the 5 review categories above. Be specific about file names, CSS properties, and exact issues. Other agents will convert your review into scores and a task list. Do NOT assign scores - the score evaluator will do that based on your feedback.

Be critical and honest. Most first iterations will have significant issues that need to be addressed.

ORIGINAL USER PROMPT:
<user_prompt>
{original_user_prompt}
</user_prompt>

Please review the code files created for this request. Use the tools available to explore and read the files, then provide your detailed natural language review organized by the 5 review categories.
Be specific about file names and issues."""


class ReviewerNode(MultiAgentBase):
    """Custom reviewer node that injects previous iteration context into the prompt."""

    def __init__(self, work_path: str):
        super().__init__()
        self.work_path = work_path

    def _create_agent(self, context_prompt: str) -> Agent:
        """Create the reviewer agent with context injected into the prompt."""
        set_work_path(self.work_path)

        config_manager = get_config_manager()
        model = config_manager.get_model(AgentIdentifier.REVIEW)

        # Combine base prompt with context
        base_prompt = get_base_prompt()
        if context_prompt:
            full_prompt = f"{context_prompt}\n\n{base_prompt}"
        else:
            full_prompt = base_prompt

        return Agent(
            model=model,
            system_prompt=full_prompt,
            tools=[list_files, read_file, grep_files, glob_files],
            name=AgentIdentifier.REVIEW,
            description=get_agent_description(AgentIdentifier.REVIEW),
            hooks=[
                get_tool_tracker(AgentIdentifier.REVIEW),
                get_conversation_tracker(AgentIdentifier.REVIEW),
                get_tool_limit_hook(AgentIdentifier.REVIEW),
            ],
        )

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        """Execute the reviewer with context from previous iterations."""
        try:
            # Import here to avoid circular imports
            from grape_coder.agents.review.review_graph import get_review_context

            context = get_review_context()
            context_prompt = context.format_summary_for_reviewer()

            # Create agent with context
            agent = self._create_agent(context_prompt)

            # Execute the review
            task_str = task if isinstance(task, str) else str(task)
            response = await agent.invoke_async(task_str)

            agent_result = AgentResult(
                stop_reason="end_turn",
                state=Status.COMPLETED,
                metrics=EventLoopMetrics(),
                message=response.message
                if hasattr(response, "message")
                else Message(
                    role="assistant", content=[ContentBlock(text=str(response))]
                ),
            )

            return MultiAgentResult(
                status=Status.COMPLETED,
                results={
                    AgentIdentifier.REVIEW: NodeResult(
                        result=agent_result, status=Status.COMPLETED
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
                    content=[ContentBlock(text=f"Error in review: {str(e)}")],
                ),
            )

            return MultiAgentResult(
                status=Status.FAILED,
                results={
                    AgentIdentifier.REVIEW: NodeResult(
                        result=agent_result, status=Status.FAILED
                    )
                },
            )


def create_reviewer_agent(work_path: str) -> MultiAgentBase:
    """Create a reviewer agent that gives a natural language review of the code.

    This now returns a ReviewerNode that injects previous iteration context
    into the reviewer prompt for Reflexion-style iterative improvement.
    """
    return ReviewerNode(work_path)
