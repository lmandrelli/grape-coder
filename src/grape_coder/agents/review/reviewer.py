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
from grape_coder.globals import get_original_user_prompt
from grape_coder.tools.work_path import (
    glob_files,
    grep_files,
    list_files,
    read_file,
    set_work_path,
)
from grape_coder.tools.tool_limit_hooks import get_tool_limit_hook


@dataclass
class CategoryScore:
    name: str
    score: int


@dataclass
class Task:
    files: List[str]
    description: str


@dataclass
class ReviewOutput:
    category_scores: List[CategoryScore]
    summary: str
    tasks: List[Task] = field(default_factory=list)

    def is_approved(self) -> bool:
        MIN_APPROVAL_SCORE = 16

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
        feedback_parts = []

        feedback_parts.append(f"<review_summary>{self.summary}</review_summary>\n")
        feedback_parts.append("📝 TASKS TO FIX:")
        for i, task in enumerate(self.tasks, 1):
            files_str = ", ".join(task.files)
            feedback_parts.append(f"\n{i}. {task.description}")
            feedback_parts.append(f"   Files: {files_str}")

        return "\n".join(feedback_parts)


class ReviewValidationError(Exception):
    pass


def extract_score_xml(content: str) -> str:
    import re

    pattern = r"<review_scores>.*?</review_scores>"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(0)

    return content


def parse_score_xml(xml_content: str) -> List[CategoryScore]:
    SCORE_CATEGORIES = [
        "user_prompt_compliance",
        "code_validity",
        "integration",
        "responsiveness",
        "best_practices",
        "accessibility",
    ]

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
    import re

    pattern = r"<revision_tasks>.*?</revision_tasks>"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(0)

    return content


SCORE_CATEGORIES = [
    "user_prompt_compliance",
    "code_validity",
    "integration",
    "responsiveness",
    "best_practices",
    "accessibility",
]


def parse_tasks_xml(xml_content: str) -> tuple[str, List[Task]]:
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


class ReviewerAgent(MultiAgentBase):
    def __init__(self, agent: Agent, work_path: str, node_name: str = "reviewer_agent"):
        super().__init__()
        self.agent = agent
        self.work_path = work_path
        self.node_name = node_name

    async def invoke_async(
        self,
        task: str | list[ContentBlock],
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> MultiAgentResult:
        try:
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
            response_text = str(response)

            agent_result = AgentResult(
                stop_reason="end_turn",
                state={
                    "natural_review": response_text,
                    "original_user_prompt": original_user_prompt,
                },
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

    def _extract_original_user_prompt(
        self, task: str | list[ContentBlock], invocation_state: dict[str, Any] | None
    ) -> str | None:
        if invocation_state and "original_user_prompt" in invocation_state:
            return invocation_state["original_user_prompt"]

        return get_original_user_prompt()


def create_reviewer_agent(work_path: str) -> ReviewerAgent:
    set_work_path(work_path)

    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.REVIEW)

    system_prompt = """You are the Senior Design & Product Reviewer. You are a critical quality assurance agent in a collaborative multi-agent workflow.

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

    agent = Agent(
        model=model,
        tools=[list_files, read_file, grep_files, glob_files],
        system_prompt=system_prompt,
        name=AgentIdentifier.REVIEW,
        description=get_agent_description(AgentIdentifier.REVIEW),
        hooks=[
            get_tool_tracker(AgentIdentifier.REVIEW),
            get_conversation_tracker(AgentIdentifier.REVIEW),
            get_tool_limit_hook(AgentIdentifier.REVIEW),
        ],
    )

    return ReviewerAgent(agent, work_path, node_name="reviewer_agent")
