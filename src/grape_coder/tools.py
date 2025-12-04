import json
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from .models import Tool


class WorkPathTool(Tool):
    """Base tool implementation with XML function calling support"""

    work_path: str = "."

    def __init__(self, work_path: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.work_path = work_path

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with given parameters"""

        path = kwargs.get("path")
        if path is None:
            raise ValueError("Missing required parameter: 'path'")
        if not isinstance(path, str):
            raise TypeError("Parameter 'path' must be a string")

        full_path = os.path.join(self.work_path, path)

        # Skip existence check for edit_file tool since it can create new files
        if self.name != "edit_file" and not os.path.exists(full_path):
            raise FileNotFoundError(f"Path does not exist: {full_path}")

        return await super().execute(**{**kwargs, "path": full_path})


class XMLFunctionParser:
    """Parser for XML function calls in agent responses"""

    @staticmethod
    def parse_function_calls(xml_content: str) -> List[Dict[str, Any]]:
        """Parse XML content to extract function calls"""
        function_calls = []

        try:
            # Look for function_calls root element
            if "<function_calls>" not in xml_content:
                return function_calls

            # Extract the function_calls block
            start = xml_content.find("<function_calls>")
            end = xml_content.find("</function_calls>") + len("</function_calls>")
            function_calls_xml = xml_content[start:end]

            # This prevents XML parsing issues with < and > characters in code
            def wrap_in_cdata(match):
                tag = match.group(1)
                content = match.group(2)
                return f"<{tag}><![CDATA[{content}]]></{tag}>"

            # Apply CDATA wrapping to individual parameter tags within <parameters>
            function_calls_xml = re.sub(
                r"<parameters>(.*?)</parameters>",
                lambda m: "<parameters>"
                + re.sub(
                    r"<([^/][^>]*)>(.*?)</\1>",
                    wrap_in_cdata,
                    m.group(1),
                    flags=re.DOTALL,
                )
                + "</parameters>",
                function_calls_xml,
                flags=re.DOTALL,
            )

            root = ET.fromstring(function_calls_xml)

            for call_elem in root.findall("invoke"):
                tool_name = call_elem.get("tool")
                if not tool_name:
                    continue

                # Parse parameters
                parameters = {}
                param_elem = call_elem.find("parameters")
                if param_elem is not None:
                    for param in param_elem:
                        # Use the text content directly, which properly handles XML escaping
                        # If the parameter has child elements, get the full XML content
                        if len(param) > 0:
                            # Parameter contains XML elements - get the full inner XML
                            param_value = "".join(
                                ET.tostring(child, encoding="unicode", method="xml")
                                for child in param
                            )
                        else:
                            # Parameter has simple text content
                            param_value = param.text or ""

                        parameters[param.tag] = param_value

                function_calls.append({"tool": tool_name, "parameters": parameters})

        except ET.ParseError as e:
            print(f"XML parsing error: {e}")
            print(xml_content)

        return function_calls

    @staticmethod
    def format_function_result(tool_name: str, result: Any) -> str:
        """Format function result as XML"""
        result_str = json.dumps(result) if not isinstance(result, str) else result

        return f"""
<function_results>
<result tool="{tool_name}">
{result_str}
</result>
</function_results>
        """.strip()
