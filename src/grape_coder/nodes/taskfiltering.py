import xml.etree.ElementTree as ET

from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message


class TaskFilteringNode(MultiAgentBase):
    """
    A Custom Node that extracts specific tasks from an XML distribution plan
    and returns the list of tasks for the specified agent.
    """

    def __init__(self, agent_xml_tag: str):
        super().__init__()
        self.agent_xml_tag = agent_xml_tag  # ex: 'class_agent'

    def _extract_tasks(self, full_xml_content: str) -> list[str]:
        """Parses XML and returns a list of tasks for this specific agent."""
        try:
            # Clean up to ensure we just get the xml part
            start = full_xml_content.find("<task_distribution>")
            end = full_xml_content.rfind("</task_distribution>")
            if start != -1 and end != -1:
                full_xml_content = full_xml_content[
                    start : end + len("</task_distribution>")
                ]

            root = ET.fromstring(full_xml_content)

            # Find the section for this agent
            agent_section = root.find(self.agent_xml_tag)

            if agent_section is None:
                return []

            # Extract tasks
            tasks = []
            for task in agent_section.findall("task"):
                if task.text and task.text.strip():
                    tasks.append(task.text.strip())

            return tasks

        except ET.ParseError:
            # Return empty list if parsing fails
            return []

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        # task comes from the previous node (Orchestrator's XML output)
        full_xml_input = task if isinstance(task, str) else str(task)

        # Filter the input and return the list of tasks
        filtered_tasks = self._extract_tasks(full_xml_input)

        # Return the task list as a simple string
        task_list_str = (
            "\n".join(filtered_tasks) if filtered_tasks else "No tasks assigned."
        )

        agent_result = AgentResult(
            stop_reason="end_turn",
            state=Status.COMPLETED,
            metrics=EventLoopMetrics(),
            message=Message(
                role="assistant", content=[ContentBlock(text=task_list_str)]
            ),
        )

        return MultiAgentResult(
            status=Status.COMPLETED,
            results={
                f"task_filter_{self.agent_xml_tag}": NodeResult(
                    result=agent_result, status=Status.COMPLETED
                )
            },
        )
