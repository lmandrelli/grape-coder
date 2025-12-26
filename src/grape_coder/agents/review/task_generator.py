from typing import Any

from strands import Agent
from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message

from grape_coder.agents.identifiers import AgentIdentifier
from grape_coder.config import get_config_manager
from grape_coder.display import get_conversation_tracker, get_tool_tracker

from .reviewer import ReviewValidationError, Task, extract_tasks_xml, parse_tasks_xml
from .review_data import ReviewData


class TaskGeneratorAgent(MultiAgentBase):
    def __init__(
        self,
        agent: Agent,
        max_retries: int = 3,
        node_name: str = "task_generator_agent",
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
                    summary, tasks = parse_tasks_xml(xml_content)

                    review_data = ReviewData(
                        summary=summary, tasks=tasks, raw_output=response_text
                    )

                    # Store in invocation_state for sharing with other nodes
                    if invocation_state is None:
                        invocation_state = {}
                    invocation_state["task_review_data"] = review_data

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
                        review_data = ReviewData(
                            summary="Task generation failed",
                            raw_output=f"Task generation failed after retries. Error: {str(e)}",
                        )

                        # Store in invocation_state
                        if invocation_state is None:
                            invocation_state = {}
                        invocation_state["task_review_data"] = review_data

                        agent_result = AgentResult(
                            stop_reason="end_turn",
                            state={"review_data": review_data},
                            metrics=EventLoopMetrics(),
                            message=Message(
                                role="assistant",
                                content=[
                                    ContentBlock(
                                        text=f"Task generation failed after retries. Error: {str(e)}"
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
                                        text=f"Task generation failed after retries. Error: {str(e)}"
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
                    content=[ContentBlock(text="Task generation failed")],
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


def create_task_generator_agent() -> TaskGeneratorAgent:
    config_manager = get_config_manager()
    model = config_manager.get_model(AgentIdentifier.REVIEW)

    system_prompt = """You are a Task Generation Specialist. You receive natural language code reviews and convert them into structured, actionable tasks for the code revision agent.

Your role is to parse the review and create specific, actionable tasks organized by priority.

TASK GENERATION RULES:
- List the most important fixes first (blocking issues, critical bugs)
- Specify which files need to be modified
- Provide a short, clear description of what to fix
- Be specific about CSS properties, HTML elements, and exact issues
- Make tasks actionable and specific

CRITICAL INSTRUCTION:
Extract specific, actionable tasks from the review. Be precise about file names and exact changes needed. The code revision agent will execute these tasks in order. Output your tasks in the required XML format."""

    agent = Agent(
        model=model,
        tools=[],
        system_prompt=system_prompt,
        name="task_generator",
        description="Generates structured tasks from natural language code reviews",
        hooks=[
            get_tool_tracker(AgentIdentifier.REVIEW),
            get_conversation_tracker(AgentIdentifier.REVIEW),
        ],
    )

    return TaskGeneratorAgent(agent, max_retries=3, node_name="task_generator_agent")
