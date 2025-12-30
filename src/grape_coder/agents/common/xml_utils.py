import xml.etree.ElementTree as ET
from typing import List, Optional


class XMLValidationError(Exception):
    pass


def extract_context_from_xml(full_xml_content: str) -> str:
    """Extracts the global context from the XML content."""
    try:
        start = full_xml_content.find("<context>")
        end = full_xml_content.find("</context>")
        if start != -1 and end != -1:
            context_content = full_xml_content[start + len("<context>") : end]
            return context_content.strip()
    except Exception:
        pass
    return ""


def extract_tasks_from_xml(full_xml_content: str, agent_xml_tag: str) -> List[str]:
    """Parses XML and returns a list of tasks for a specific agent tag."""
    try:
        start = full_xml_content.find("<task_distribution>")
        end = full_xml_content.rfind("</task_distribution>")
        if start != -1 and end != -1:
            full_xml_content = full_xml_content[
                start : end + len("</task_distribution>")
            ]

        root = ET.fromstring(full_xml_content)

        agent_section = root.find(agent_xml_tag)

        if agent_section is None:
            return []

        tasks = []
        for task in agent_section.findall("task"):
            if task.text and task.text.strip():
                tasks.append(task.text.strip())

        return tasks

    except ET.ParseError:
        return []


def extract_review_tasks_from_xml(full_xml_content: str) -> tuple[str, List[dict]]:
    """Extracts summary and tasks from review XML content."""
    try:
        start = full_xml_content.find("<review>")
        end = full_xml_content.rfind("</review>")
        if start != -1 and end != -1:
            full_xml_content = full_xml_content[start : end + len("</review>")]

        root = ET.fromstring(full_xml_content)

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
                priority_elem = task_elem.find("priority")

                files = (
                    files_elem.text.strip()
                    if files_elem is not None and files_elem.text
                    else ""
                )
                description = (
                    desc_elem.text.strip()
                    if desc_elem is not None and desc_elem.text
                    else ""
                )
                priority = (
                    priority_elem.text.strip()
                    if priority_elem is not None and priority_elem.text
                    else "MEDIUM"
                )

                if description:
                    tasks.append(
                        {
                            "files": files,
                            "description": description,
                            "priority": priority,
                        }
                    )

        return summary, tasks

    except ET.ParseError:
        return "", []


def extract_scores_from_xml(full_xml_content: str) -> dict:
    """Extracts scores from review_scores XML content."""
    try:
        start = full_xml_content.find("<review_scores>")
        end = full_xml_content.rfind("</review_scores>")
        if start != -1 and end != -1:
            full_xml_content = full_xml_content[start : end + len("</review_scores>")]

        root = ET.fromstring(full_xml_content)

        scores = {}
        for category in [
            "code_validity",
            "integration",
            "responsiveness",
            "best_practices",
            "accessibility",
        ]:
            category_elem = root.find(category)
            if category_elem is not None:
                score_elem = category_elem.find("score")
                if score_elem is not None and score_elem.text:
                    scores[category] = int(score_elem.text.strip())

        return scores

    except ET.ParseError:
        return {}


def needs_revision_from_scores(scores: dict) -> bool:
    """Determines if revision is needed based on scores."""
    critical_threshold = 17
    standard_threshold = 15

    code_validity = scores.get("code_validity", 0)
    integration = scores.get("integration", 0)
    responsiveness = scores.get("responsiveness", 0)
    best_practices = scores.get("best_practices", 0)
    accessibility = scores.get("accessibility", 0)

    if code_validity < critical_threshold or integration < critical_threshold:
        return True
    if (
        responsiveness < standard_threshold
        or best_practices < standard_threshold
        or accessibility < standard_threshold
    ):
        return True

    return False
