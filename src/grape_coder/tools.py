import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from .models import Tool


class BaseTool(Tool):
    """Base tool implementation with XML function calling support"""

    def to_xml_schema(self) -> str:
        """Generate XML schema for this tool"""
        parameters_xml = ""
        if self.parameters:
            parameters_xml = "<parameters>"
            for param in self.parameters:
                required_attr = "required='true'" if param.required else ""
                default_attr = (
                    f"default='{param.default}'" if param.default is not None else ""
                )
                parameters_xml += f"""
                <parameter name="{param.name}" type="{param.type}" {required_attr} {default_attr}>
                    <description>{param.description or ""}</description>
                </parameter>
                """
            parameters_xml += "</parameters>"

        return f"""
        <tool name="{self.name}">
            <description>{self.description or self.prompt}</description>
            <prompt>{self.prompt}</prompt>
            {parameters_xml}
        </tool>
        """.strip()

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
                        param_value = param.text or ""
                        # Try to parse as JSON for complex types
                        try:
                            if param_value.startswith(("[", "{")):
                                param_value = json.loads(param_value)
                            elif param_value.lower() in ("true", "false"):
                                param_value = param_value.lower() == "true"
                            elif param_value.isdigit():
                                param_value = int(param_value)
                            elif (
                                "." in param_value
                                and param_value.replace(".", "").isdigit()
                            ):
                                param_value = float(param_value)
                        except (ValueError, json.JSONDecodeError):
                            pass  # Keep as string
                        parameters[param.tag] = param_value

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
