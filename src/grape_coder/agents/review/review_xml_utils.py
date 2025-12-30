import re
import xml.etree.ElementTree as ET
from typing import List, Optional, Union


class XMLValidationError(Exception):
    pass

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


def extract_xml_by_tags(
    content: str, tags: Union[str, List[str]], join_with: str = "\n"
) -> str:
    """Extract XML content from raw LLM response by searching for specific tags.

    Searches for specific XML tags in the content and returns the extracted sections.
    Falls back to a generic XML pattern if specific tags are not found.

    Args:
        content: Raw agent response content.
        tags: Single tag name (str) or list of tag names to search for.
        join_with: String to join multiple extracted sections. Defaults to newline.

    Returns:
        Extracted XML string(s), joined if multiple tags specified.
        Returns original content if no XML found.
    """
    if isinstance(tags, str):
        tags = [tags]

    matches = []
    for tag in tags:
        pattern = rf"<{tag}>.*?</{tag}>"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            matches.append(match.group(0))

    if matches:
        return join_with.join(matches)

    xml_pattern = r"<[^>]+>.*?</[^>]+>"
    xml_match = re.search(xml_pattern, content, re.DOTALL)

    if xml_match:
        return xml_match.group(0)

    return content


def extract_xml_section(content: str, tag_name: str) -> tuple[str, str]:
    """Extract and validate an XML section with the specified root tag.

    Extracts a section from content bounded by the specified tag, validates
    that the extracted XML has the correct root tag, and returns both the
    section and the root tag for further processing.

    Args:
        content: Content containing the XML section.
        tag_name: Name of the tag to extract.

    Returns:
        Tuple of (extracted_xml_section, root_tag_name).

    Raises:
        ET.ParseError: If XML parsing fails.
    """
    start = content.find(f"<{tag_name}>")
    end = content.find(f"</{tag_name}>") + len(f"</{tag_name}>")

    if start != -1 and end > start:
        section = content[start:end]
        root = ET.fromstring(section)
        if root.tag != tag_name:
            raise ET.ParseError(
                f"Root element must be '{tag_name}', found '{root.tag}'"
            )
        return section, tag_name

    root = ET.fromstring(content)
    if root.tag != tag_name:
        raise ET.ParseError(f"Root element must be '{tag_name}', found '{root.tag}'")
    return content, tag_name
