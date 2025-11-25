import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from .models import Tool


class BaseTool(Tool):
    """Base tool implementation with XML function calling support"""

    def to_xml_schema(self) -> str:
        """Generate XML schema for this tool"""
        # TODO: add parameters
        return f"""
        <tool name="{self.name}">
            <description>{self.description or self.prompt}</description>
            <prompt>{self.prompt}</prompt>
        </tool>
        """

    async def execute(self, **kwargs) -> Any:
        """Execute the tool function with given parameters"""
        try:
            if callable(self.function):
                result = self.function(**kwargs)
                if hasattr(result, "__await__"):
                    return await result
                else:
                    return result
            else:
                raise ValueError(f"Tool {self.name} function is not callable")
        except Exception as e:
            return {"error": str(e), "tool": self.name}


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
                        parameters[param.tag] = param.text or ""

                function_calls.append({"tool": tool_name, "parameters": parameters})

        except ET.ParseError as e:
            print(f"XML parsing error: {e}")

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
