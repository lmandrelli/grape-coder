import xml.etree.ElementTree as ET

from strands.agent import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import ContentBlock, Message


class TaskFilteringNode(MultiAgentBase):
    """
    A Custom Node that extracts context and specific tasks from an XML distribution plan
    and returns both the global context and the list of tasks for the specified agent.
    """

    def __init__(self, agent_xml_tag: str):
        super().__init__()
        self.agent_xml_tag = agent_xml_tag  # ex: 'class_agent'

    def _extract_context(self, full_xml_content: str) -> str:
        """Extracts the global context from the XML content."""
        try:
            # Look for context section
            start = full_xml_content.find("<context>")
            end = full_xml_content.find("</context>")
            if start != -1 and end != -1:
                context_content = full_xml_content[start + len("<context>") : end]
                return context_content.strip()
        except Exception:
            pass
        return ""

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

        # Extract both context and tasks
        global_context = self._extract_context(full_xml_input)
        filtered_tasks = self._extract_tasks(full_xml_input)

        # Build the enhanced prompt with context and tasks
        if global_context:
            prompt = f"""GLOBAL CONTEXT:
{global_context}

YOUR ASSIGNED TASKS:
{chr(10).join(filtered_tasks) if filtered_tasks else "No tasks assigned."}

Please complete your assigned tasks while keeping the global context in mind to ensure consistency with the overall project."""
        else:
            # Fallback if no context found
            task_list_str = (
                "\n".join(filtered_tasks) if filtered_tasks else "No tasks assigned."
            )
            prompt = task_list_str

        agent_result = AgentResult(
            stop_reason="end_turn",
            state=Status.COMPLETED,
            metrics=EventLoopMetrics(),
            message=Message(role="assistant", content=[ContentBlock(text=prompt)]),
        )

        return MultiAgentResult(
            status=Status.COMPLETED,
            results={
                f"task_filter_{self.agent_xml_tag}": NodeResult(
                    result=agent_result, status=Status.COMPLETED
                )
            },
        )
