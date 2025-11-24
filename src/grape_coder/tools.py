import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from .models import Tool


class BaseTool(Tool):
    """Base tool implementation with XML function calling support"""

    def to_xml_schema(self) -> str:
        """Generate XML schema for this tool"""
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


class MCPClient:
    """Model Context Protocol client for tool management"""

    def __init__(self):
        self.servers: Dict[str, Dict[str, Any]] = {}

    def register_server(self, server_name: str, server_info: Dict[str, Any]):
        """Register an MCP server"""
        self.servers[server_name] = server_info

    async def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """List available tools from an MCP server"""
        if server_name not in self.servers:
            raise ValueError(f"MCP server {server_name} not found")

        # Mock implementation - in real scenario, this would connect to actual MCP server
        server_info = self.servers[server_name]
        return server_info.get("tools", [])

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any]
    ) -> Any:
        """Call a tool on an MCP server"""
        if server_name not in self.servers:
            raise ValueError(f"MCP server {server_name} not found")

        # Mock implementation
        server_info = self.servers[server_name]
        tools = server_info.get("tools", [])

        for tool in tools:
            if tool.get("name") == tool_name:
                # Mock tool execution
                return f"Executed {tool_name} with arguments: {arguments}"

        raise ValueError(f"Tool {tool_name} not found on server {server_name}")


class MCPToolWrapper(BaseTool):
    """Wrapper for MCP tools to integrate with the tool system"""

    def __init__(
        self, server_name: str, tool_info: Dict[str, Any], mcp_client: MCPClient
    ):
        self.server_name = server_name
        self.tool_info = tool_info
        self.mcp_client = mcp_client

        super().__init__(
            name=tool_info["name"],
            prompt=tool_info.get("description", ""),
            function=self._execute_mcp_tool,
            description=tool_info.get("description", ""),
        )

    async def _execute_mcp_tool(self, **kwargs) -> Any:
        """Execute the MCP tool"""
        return await self.mcp_client.call_tool(self.server_name, self.name, kwargs)


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
