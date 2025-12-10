import xml.etree.ElementTree as ET
from strands import Agent
from strands.agent.agent_result import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.types.content import ContentBlock, Message
from strands.telemetry.metrics import EventLoopMetrics

class TaskFilteringNode(MultiAgentBase):
    """
    A Custom Node that extracts specific tasks from an XML distribution plan
    before invoking the underlying agent.
    """

    def __init__(self, agent: Agent, agent_xml_tag: str):
        super().__init__()
        self.agent = agent
        self.agent_xml_tag = agent_xml_tag  # ex: 'class_agent'

    def _extract_tasks(self, full_xml_content: str) -> str:
        """Parses XML and returns only the content for this specific agent."""
        try:
            # Clean up to ensure we just get the xml part
            start = full_xml_content.find("<task_distribution>")
            end = full_xml_content.rfind("</task_distribution>")
            if start != -1 and end != -1:
                full_xml_content = full_xml_content[start : end + len("</task_distribution>")]

            root = ET.fromstring(full_xml_content)
            
            # Find the section for this agent
            agent_section = root.find(self.agent_xml_tag)
            
            if agent_section is None:
                return "No tasks assigned."

            # Reconstruct the relevant part or just list tasks
            tasks = []
            for task in agent_section.findall("task"):
                if task.text:
                    tasks.append(f"- {task.text}")
            
            if not tasks:
                return "No specific tasks found in assignment."
                
            return f"Here are your assigned tasks:\n" + "\n".join(tasks)

        except ET.ParseError:
            # Fallback: return full content if parsing fails, or handle error
            return f"Error parsing tasks. Full context provided:\n{full_xml_content}"

    async def invoke_async(self, task, invocation_state=None, **kwargs):
        # task comes from the previous node (Orchestrator's XML output)
        full_xml_input = task if isinstance(task, str) else str(task)
        
        # 1. Filter the input
        filtered_instructions = self._extract_tasks(full_xml_input)
        
        # 2. Invoke the agent with ONLY the filtered instructions
        # We assume the agent returns a standard response
        response = await self.agent.invoke_async(filtered_instructions)
        
        # 3. Wrap result in MultiAgentResult as expected by the Graph
        # Note: We construct a NodeResult compatible with strands graph
        agent_result = AgentResult(
            stop_reason="end_turn", # or dynamic based on response
            state=Status.COMPLETED,
            metrics=EventLoopMetrics(),
            message=response.message if hasattr(response, 'message') else Message(
                role="assistant", content=[ContentBlock(text=str(response))]
            ),
        )

        return MultiAgentResult(
            status=Status.COMPLETED,
            results={
                self.agent.name: NodeResult(
                    result=agent_result, status=Status.COMPLETED
                )
            },
        )
