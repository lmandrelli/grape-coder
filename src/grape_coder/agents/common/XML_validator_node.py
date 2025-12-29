from typing import Any, Callable

from strands import Agent
from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message


class XMLValidatorNode(MultiAgentBase):
    """Generic XML validation node that validates agent responses with retry logic.

    This node wraps an agent and validates its XML output using custom validation
    and extraction functions. It supports retry logic on validation failure.

    Args:
        agent: The Strands Agent to use for generating XML content.
        validate_fn: Callable that validates XML string and returns validation message
            or raises XMLValidationError on failure.
        extract_fn: Callable that extracts XML string from agent response content.
        max_retries: Maximum number of retry attempts on validation failure.
                      Defaults to 3.
        success_callback: Optional callable to execute after successful validation.
                         Receives the validated XML content as argument.
    """

    def __init__(
        self,
        agent: Agent,
        validate_fn: Callable[[str], str],
        extract_fn: Callable[[str], str],
        max_retries: int = 3,
        success_callback: Callable[[str], None] | None = None,
    ):
        super().__init__()
        self.agent = agent
        self.validate_fn = validate_fn
        self.extract_fn = extract_fn
        self.max_retries = max_retries
        self.success_callback = success_callback

    async def invoke_async(
        self,
        task: str | list[ContentBlock],
        invocation_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> MultiAgentResult:
        initial_prompt = task if isinstance(task, str) else str(task)
        current_prompt = initial_prompt
        last_error = None
        xml_content = None

        for attempt in range(self.max_retries + 1):
            try:
                if attempt == 0:
                    prompt = str(current_prompt)
                else:
                    prompt = f"""Your previous attempt:
<last_attempt>
{current_prompt}
</last_attempt>

Error encountered:
<error>
{last_error}
</error>

Please fix the XML and provide a corrected version. Ensure the XML is well-formed and follows the required structure."""

                response = await self.agent.invoke_async(prompt)
                xml_content = str(response)

                xml_to_validate = self.extract_fn(xml_content)

                self.validate_fn(xml_to_validate)

                if self.success_callback:
                    self.success_callback(xml_to_validate)

                agent_result = AgentResult(
                    stop_reason="end_turn",
                    state=Status.COMPLETED,
                    metrics=EventLoopMetrics(),
                    message=Message(
                        role="assistant", content=[ContentBlock(text=xml_to_validate)]
                    ),
                )

                return MultiAgentResult(
                    status=Status.COMPLETED,
                    results={
                        "xml_validator": NodeResult(
                            result=agent_result, status=Status.COMPLETED
                        )
                    },
                )

            except XMLValidationError as e:
                last_error = str(e)
                current_prompt = ""
                if xml_content is not None:
                    current_prompt = xml_content

                if attempt == self.max_retries:
                    agent_result = AgentResult(
                        stop_reason="guardrail_intervened",
                        state=Status.COMPLETED,
                        metrics=EventLoopMetrics(),
                        message=Message(
                            role="assistant",
                            content=[ContentBlock(text=initial_prompt)],
                        ),
                    )

                    return MultiAgentResult(
                        status=Status.COMPLETED,
                        results={
                            "xml_validator": NodeResult(
                                result=agent_result, status=Status.COMPLETED
                            )
                        },
                    )

                continue

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
                        "xml_validator": NodeResult(
                            result=agent_result, status=Status.FAILED
                        )
                    },
                )

        agent_result = AgentResult(
            stop_reason="guardrail_intervened",
            state=Status.FAILED,
            metrics=EventLoopMetrics(),
            message=Message(
                role="assistant",
                content=[ContentBlock(text=initial_prompt)],
            ),
        )
        return MultiAgentResult(
            status=Status.FAILED,
            results={
                "xml_validator": NodeResult(result=agent_result, status=Status.FAILED)
            },
        )


class XMLValidationError(Exception):
    pass
