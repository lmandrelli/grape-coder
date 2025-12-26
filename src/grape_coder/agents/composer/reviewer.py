import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, List, cast

from strands import Agent
from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier, get_agent_description
from grape_coder.config import get_config_manager
from grape_coder.display import get_tool_tracker, get_conversation_tracker
from grape_coder.globals import get_original_user_prompt
from grape_coder.tools.work_path import (
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)
from grape_coder.tools.tool_limit_hooks import get_tool_limit_hook


# Score categories and their minimum requirements
SCORE_CATEGORIES = [
    "user_prompt_compliance",
    "code_validity",
    "integration",
    "responsiveness",
    "best_practices",
    "accessibility",
]

# Overall minimum score required for approval (out of 20)
MIN_APPROVAL_SCORE = 16


@dataclass
class CategoryScore:
    """Represents a single category score."""

    name: str
    score: int


@dataclass
class Task:
    """Represents a single task for revision."""

    files: List[str]
    description: str


@dataclass
class ReviewOutput:
    """Combined output from the review process."""

    category_scores: List[CategoryScore]
    summary: str
    tasks: List[Task] = field(default_factory=list)

    def is_approved(self) -> bool:
        """Check if the review passes approval criteria.

        Returns True if:
        - Overall average score >= MIN_APPROVAL_SCORE (16)
        - Code validity score >= 17
        - Integration score >= 17
        - User prompt compliance score >= 15
        - Responsiveness score >= 15
        - Best practices score >= 15
        - Accessibility score >= 15
        """
        if self.category_scores:
            avg_score = sum(c.score for c in self.category_scores) / len(
                self.category_scores
            )
            if avg_score < MIN_APPROVAL_SCORE:
                return False

        category_dict = {c.name: c.score for c in self.category_scores}

        if category_dict.get("code_validity", 0) < 17:
            return False
        if category_dict.get("integration", 0) < 17:
            return False
        if category_dict.get("user_prompt_compliance", 0) < 15:
            return False
        if category_dict.get("responsiveness", 0) < 15:
            return False
        if category_dict.get("best_practices", 0) < 15:
            return False
        if category_dict.get("accessibility", 0) < 15:
            return False

        return True

    def get_feedback_for_revision(self) -> str:
        """Generate feedback message for the code revision agent."""
        feedback_parts = []

        feedback_parts.append(f"<review_summary>{self.summary}</review_summary>\n")
        feedback_parts.append("📝 TASKS TO FIX:")
        for i, task in enumerate(self.tasks, 1):
            files_str = ", ".join(task.files)
            feedback_parts.append(f"\n{i}. {task.description}")
            feedback_parts.append(f"   Files: {files_str}")

        return "\n".join(feedback_parts)


class ReviewValidationError(Exception):
    """Custom exception for review XML validation errors."""

    pass


def extract_score_xml(content: str) -> str:
    """Extract score XML content from model response.

    Args:
        content: Raw response from the model

    Returns:
        Extracted XML string
    """
    pattern = r"<review_scores>.*?</review_scores>"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(0)

    return content


def parse_score_xml(xml_content: str) -> List[CategoryScore]:
    """Parse and validate the score XML content.

    Args:
        xml_content: Raw XML string from the score evaluator

    Returns:
        List of CategoryScore objects

    Raises:
        ReviewValidationError: If XML is malformed or missing required elements
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ReviewValidationError(f"Invalid XML format: {str(e)}")

    if root.tag != "review_scores":
        raise ReviewValidationError(
            f"Root element must be 'review_scores', got '{root.tag}'"
        )

    category_scores = []

    for category_name in SCORE_CATEGORIES:
        category_elem = root.find(category_name)
        if category_elem is None:
            raise ReviewValidationError(f"Missing required category: {category_name}")

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

        category_scores.append(CategoryScore(name=category_name, score=score))

    return category_scores


def extract_tasks_xml(content: str) -> str:
    """Extract tasks XML content from model response.

    Args:
        content: Raw response from the model

    Returns:
        Extracted XML string
    """
    pattern = r"<revision_tasks>.*?</revision_tasks>"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(0)

    return content


def parse_tasks_xml(xml_content: str) -> tuple[str, List[Task]]:
    """Parse and validate the tasks XML content.

    Args:
        xml_content: Raw XML string from the task generator

    Returns:
        Tuple of (summary, list of Task objects)

    Raises:
        ReviewValidationError: If XML is malformed or missing required elements
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ReviewValidationError(f"Invalid XML format: {str(e)}")

    if root.tag != "revision_tasks":
        raise ReviewValidationError(
            f"Root element must be 'revision_tasks', got '{root.tag}'"
        )

    summary_elem = root.find("summary")
    summary = (
        summary_elem.text.strip()
        if summary_elem is not None and summary_elem.text
        else ""
    )

    tasks = []
    tasks_elem = root.find("tasks")
    if tasks_elem is not None:
        for task_elem in tasks_elem.findall("task"):
            files_elem = task_elem.find("files")
            desc_elem = task_elem.find("description")

            files = []
            if files_elem is not None and files_elem.text:
                files = [f.strip() for f in files_elem.text.split(",") if f.strip()]

            description = ""
            if desc_elem is not None and desc_elem.text:
                description = desc_elem.text.strip()

            if description:
                tasks.append(Task(files=files, description=description))

    return summary, tasks


class ReviewerAgent:
    """First agent that performs the natural language review."""

    def __init__(self, agent: Agent):
        self.agent = agent

    async def invoke_async(
        self,
        task: str | list[ContentBlock],
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate natural language review of the code."""
        original_user_prompt = self._extract_original_user_prompt(
            task, invocation_state
        )

        if original_user_prompt:
            prompt = f"""ORIGINAL USER REQUEST:
<user_prompt>
{original_user_prompt}
</user_prompt>

Please review the code files created for this request. Use the tools available to explore and read the files, then provide your natural language review.

Provide a thorough assessment discussing:
- Overall impressions
- Strengths and weaknesses
- Specific areas that need improvement
- Visual aesthetics
- User experience
- Technical quality

Be specific about file names and issues. This review will be used by other agents to generate scores and a task list."""
        else:
            prompt = """Please review the code files in the workspace. Use the tools available to explore and read the files, then provide your natural language review.

Provide a thorough assessment discussing:
- Overall impressions
- Strengths and weaknesses
- Specific areas that need improvement
- Visual aesthetics
- User experience
- Technical quality

Be specific about file names and issues."""

        response = await self.agent.invoke_async(prompt)
        return str(response)

    def _extract_original_user_prompt(
        self, task: str | list[ContentBlock], invocation_state: dict[str, Any] | None
    ) -> str | None:
        """Extract the original user prompt from available sources."""
        if invocation_state and "original_user_prompt" in invocation_state:
            return invocation_state["original_user_prompt"]

        return get_original_user_prompt()


class ScoreEvaluatorAgent:
    """Second agent that evaluates scores based on the review."""

    def __init__(self, agent: Agent, max_retries: int = 3):
        self.agent = agent
        self.max_retries = max_retries

    async def invoke_async(self, review_text: str) -> List[CategoryScore]:
        """Generate category scores based on the natural language review."""
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
                return parse_score_xml(xml_content)

            except ReviewValidationError as e:
                last_error = str(e)
                if attempt == self.max_retries:
                    return [
                        CategoryScore(name=cat, score=10) for cat in SCORE_CATEGORIES
                    ]
                continue

        return [CategoryScore(name=cat, score=10) for cat in SCORE_CATEGORIES]


class TaskGeneratorAgent:
    """Third agent that transforms the review into structured tasks."""

    def __init__(self, agent: Agent, max_retries: int = 3):
        self.agent = agent
        self.max_retries = max_retries

    async def invoke_async(self, review_text: str) -> tuple[str, List[Task]]:
        """Generate structured tasks from the natural language review."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                if attempt == 0:
                    prompt = f"""REVIEW TO PROCESS:
<review>
{review_text}
</review>

Convert the review into the following XML format:

<revision_tasks>
    <summary>
        A brief summary of the overall review and main issues found
    </summary>
    <tasks>
        <task>
            <files>file1.html, file2.css</files>
            <description>Fix the layout issue where elements overlap on mobile screens</description>
        </task>
        <task>
            <files>styles.css</files>
            <description>Add missing hover states for interactive elements</description>
        </task>
    </tasks>
</revision_tasks>"""
                else:
                    prompt = f"""Your previous task generation attempt had formatting issues:

<last_attempt>
{last_error}
</last_attempt>

Please generate the task list again using the correct XML format. Ensure:
1. Root element is <revision_tasks>
2. Contains a <summary> section
3. Contains a <tasks> section with at least one <task>
4. Each task has <files> (comma-separated) and <description>

Original review:
<review>
{review_text}
</review>"""

                response = await self.agent.invoke_async(prompt)
                response_text = str(response)

                xml_content = extract_tasks_xml(response_text)
                return parse_tasks_xml(xml_content)

            except ReviewValidationError as e:
                last_error = str(e)
                if attempt == self.max_retries:
                    return "Task generation failed", []
                continue

        return "Task generation failed", []


class ReviewValidatorNode(MultiAgentBase):
    """Custom node that orchestrates three agents: reviewer, score evaluator, and task generator."""

    def __init__(
        self,
        reviewer_model,
        score_evaluator_model,
        task_generator_model,
        reviewer_prompt,
        score_evaluator_prompt,
        task_generator_prompt,
        reviewer_tools,
        max_retries: int = 3,
        node_name: str = "review_agent",
        reviewer_hooks=None,
        score_evaluator_hooks=None,
        task_generator_hooks=None,
    ):
        super().__init__()
        self.reviewer_model = reviewer_model
        self.score_evaluator_model = score_evaluator_model
        self.task_generator_model = task_generator_model
        self.reviewer_prompt = reviewer_prompt
        self.score_evaluator_prompt = score_evaluator_prompt
        self.task_generator_prompt = task_generator_prompt
        self.reviewer_tools = reviewer_tools
        self.max_retries = max_retries
        self.node_name = node_name
        self.reviewer_hooks = reviewer_hooks or []
        self.score_evaluator_hooks = score_evaluator_hooks or []
        self.task_generator_hooks = task_generator_hooks or []

    def _create_reviewer_agent(self) -> ReviewerAgent:
        agent = Agent(
            model=cast(AgentIdentifier, self.reviewer_model),
            tools=self.reviewer_tools,
            system_prompt=self.reviewer_prompt,
            name=AgentIdentifier.REVIEW,
            description=get_agent_description(AgentIdentifier.REVIEW),
            hooks=self.reviewer_hooks,
        )
        return ReviewerAgent(agent)

    def _create_score_evaluator_agent(self) -> ScoreEvaluatorAgent:
        agent = Agent(
            model=cast(AgentIdentifier, self.score_evaluator_model),
            tools=[],
            system_prompt=self.score_evaluator_prompt,
            name="score_evaluator",
            description="Evaluates code quality scores from natural language reviews",
            hooks=self.score_evaluator_hooks,
        )
        return ScoreEvaluatorAgent(agent, self.max_retries)

    def _create_task_generator_agent(self) -> TaskGeneratorAgent:
        agent = Agent(
            model=cast(AgentIdentifier, self.task_generator_model),
            tools=[],
            system_prompt=self.task_generator_prompt,
            name="task_generator",
            description="Generates structured tasks from natural language code reviews",
            hooks=self.task_generator_hooks,
        )
        return TaskGeneratorAgent(agent, self.max_retries)

    async def invoke_async(
        self,
        task: str | list[ContentBlock],
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> MultiAgentResult:
        """Execute three-agent review process."""
        try:
            reviewer = self._create_reviewer_agent()
            score_evaluator = self._create_score_evaluator_agent()
            task_generator = self._create_task_generator_agent()

            # Step 1: Generate natural language review
            natural_review = await reviewer.invoke_async(task, invocation_state)

            # Step 2: Generate score and tasks in parallel
            import asyncio

            category_scores, (summary, tasks) = await asyncio.gather(
                score_evaluator.invoke_async(natural_review),
                task_generator.invoke_async(natural_review),
            )

            # Create combined output
            review_output = ReviewOutput(
                category_scores=category_scores,
                summary=summary,
                tasks=tasks,
            )

            # Store both outputs
            agent_result = AgentResult(
                stop_reason="end_turn",
                state={
                    "review_output": review_output,
                    "natural_review": natural_review,
                },
                metrics=EventLoopMetrics(),
                message=Message(
                    role="assistant",
                    content=[ContentBlock(text=natural_review)],
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

        except Exception as e:
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
                        result=agent_result, status=Status.FAILED
                    )
                },
            )


def create_review_agent(work_path: str) -> ReviewValidatorNode:
    """Create three agents for reviewing website files: reviewer, score evaluator, and task generator"""

    # Set work_path for tools
    set_work_path(work_path)

    # Get model using the config manager
    config_manager = get_config_manager()
    reviewer_model = config_manager.get_model(AgentIdentifier.REVIEW)
    score_evaluator_model = config_manager.get_model(AgentIdentifier.REVIEW)
    task_generator_model = config_manager.get_model(AgentIdentifier.REVIEW)

    # Reviewer agent system prompt (natural language review)
    reviewer_prompt = """You are the Senior Design & Product Reviewer. You are a critical quality assurance agent in a collaborative multi-agent workflow.

    YOUR MISSION:
    Ensure the website is not just "functional," but professional, modern, and high-converting. If a website "works" but looks unprofessional, dated, or boring, it is a FAILURE. You must push the code agent to implement high-end, modern web experiences.

    CRITICAL DESIGN PHILOSOPHY:
    We value "Premium Polish" over "Visual Noise."
    - Animations must be SUBTLE and PURPOSEFUL (e.g., smooth opacity transitions, slight transform shifts).
    - NEVER allow distracting or amateurish animations like blinking, constant looping, or jarring movements.
    - Focus on Micro-interactions: how a button feels when hovered, how a menu slides in, how content fades in gracefully.

    ASSESSMENT AREAS:
    - VISUAL_AESTHETICS: Does it look modern? Proper whitespace, consistent border-radii, modern font pairings, harmonious color palette, visual polish (subtle shadows, glassmorphism, professional icons)?
    - UX_AND_HIERARCHY: Is there a clear Call to Action (CTA)? Is the "Hero" section impactful? Is the information architecture logical?
    - MOTION_REFINEMENT & DETAIL: Modern CSS (Flexbox, Grid, CSS Variables)? Smooth transitions (0.3s ease)? Subtle entrance animations?
    - BLOCKING ISSUES: Any critical problems that prevent the code from working properly?

    SCORING CATEGORIES TO KEEP IN MIND:
    1. USER_PROMPT_COMPLIANCE: Does it fulfill the original user request? Don't be too harsh if the prompt is vague.
    2. CODE_VALIDITY: Is the code syntactically correct and free of bugs? (CRITICAL - needs 17+)
    3. INTEGRATION: Are all files properly linked and working together? Will JS/CSS/SVG be handled correctly by HTML? (CRITICAL - needs 17+)
    4. RESPONSIVENESS: Does the layout work across different screen sizes? (needs 15+)
    5. BEST_PRACTICES: Does the code follow modern web development standards? (needs 15+)
    6. ACCESSIBILITY: Is the site accessible to users with disabilities? (needs 15+)

    SCORING GUIDELINES (keep in mind for assessment):
    - 0-10: Critical failures or extremely amateur design.
    - 11-14: "Standard/Basic." Code works, but looks like a student project. NEEDS IMPROVEMENT.
    - 15-17: "Professional." Good enough for a real business.
    - 18-20: "Exceptional." Looks like a premium, custom-designed site.

    CRITICAL INSTRUCTION:
    You are a reviewer only. Do not modify code. Provide detailed, actionable feedback in natural language. Be specific about file names, CSS properties, and exact issues. Other agents will convert your review into scores and a task list."""

    # Score evaluator agent system prompt (evaluates scores from review)
    score_evaluator_prompt = """You are a Score Evaluator. You receive natural language code reviews and evaluate the quality of the code in different categories.

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

    # Task generator agent system prompt (converts review to structured tasks)
    task_generator_prompt = """You are a Task Generation Specialist. You receive natural language code reviews and convert them into structured, actionable tasks for the code revision agent.

    Your role is to parse the review and create specific, actionable tasks organized by priority.

    TASK GENERATION RULES:
    - List the most important fixes first (blocking issues, critical bugs)
    - Specify which files need to be modified
    - Provide a short, clear description of what to fix
    - Be specific about CSS properties, HTML elements, and exact issues
    - Make tasks actionable and specific

    CRITICAL INSTRUCTION:
    Extract specific, actionable tasks from the review. Be precise about file names and exact changes needed. The code revision agent will execute these tasks in order. Output your tasks in the required XML format."""

    return ReviewValidatorNode(
        reviewer_model=reviewer_model,
        score_evaluator_model=score_evaluator_model,
        task_generator_model=task_generator_model,
        reviewer_prompt=reviewer_prompt,
        score_evaluator_prompt=score_evaluator_prompt,
        task_generator_prompt=task_generator_prompt,
        reviewer_tools=[
            list_files,
            read_file,
            grep_files,
            glob_files,
        ],
        max_retries=3,
        node_name="review_agent",
        reviewer_hooks=[
            get_tool_tracker(AgentIdentifier.REVIEW),
            get_conversation_tracker(AgentIdentifier.REVIEW),
            get_tool_limit_hook(AgentIdentifier.REVIEW),
        ],
        score_evaluator_hooks=[
            get_tool_tracker(AgentIdentifier.REVIEW),
            get_conversation_tracker(AgentIdentifier.REVIEW),
        ],
        task_generator_hooks=[
            get_tool_tracker(AgentIdentifier.REVIEW),
            get_conversation_tracker(AgentIdentifier.REVIEW),
        ],
    )
