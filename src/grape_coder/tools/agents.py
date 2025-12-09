from strands import tool


@tool
def get_agent_tasks(xml_distribution: str, agent_name: str) -> str:
    """Extract tasks for a given agent from an XML task distribution.

    Args:
        xml_distribution: XML string containing task_distribution root and agent sections
        agent_name: Tag name of the agent section (e.g. 'class_agent')

    Returns:
        A newline-separated string of tasks for the agent, or an error message.
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(xml_distribution)

        if root.tag != "task_distribution":
            return "Error: Root element must be 'task_distribution'"

        # Find the agent element by tag
        agent_elem = root.find(agent_name)
        if agent_elem is None:
            return f"No tasks found for agent '{agent_name}'"

        tasks = [t.text.strip() for t in agent_elem.findall("task") if t.text]
        if not tasks:
            return f"No tasks found for agent '{agent_name}'"

        return "\n".join(tasks)

    except ET.ParseError as e:
        return f"Error: Invalid XML format - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"
