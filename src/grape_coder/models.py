from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_MAX_TOKENS = 32000


class MessageType(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    CALL_FUNCTION = "call_function"
    RESULT_FUNCTION = "result_function"

    def __str__(self):
        return self.value


class Message(BaseModel):
    type: MessageType
    content: str
    result: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ToolParameter(BaseModel):
    name: str
    type: Literal["string", "integer", "number", "boolean", "array", "object"]
    description: Optional[str] = None
    required: bool = True
    default: Optional[Any] = None


class Tool(BaseModel):
    name: str
    prompt: str
    function: Callable
    description: Optional[str] = None
    parameters: List[ToolParameter] = Field(default_factory=list)

    async def execute(self, **kwargs) -> Any:
        return NotImplementedError("Tool must implement execute method")

    def to_xml_schema(self) -> str | Exception:
        return NotImplementedError("Tool must implement to_xml_schema method")


class LLMModel(BaseModel):
    name: str
    max_tokens: int = DEFAULT_MAX_TOKENS
    description: Optional[str] = None


class Provider(BaseModel):
    model: LLMModel
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    async def generate(
        self, messages: List[Message], tools: Optional[List[Tool]] = None
    ) -> str:
        raise NotImplementedError("Provider must implement generate method")


class History(BaseModel):
    messages: List[Message] = Field(default_factory=list)
    max_tokens: int = DEFAULT_MAX_TOKENS
    # TODO: not max_tokens but provider

    def add_message(self, message: Message) -> None:
        self.messages.append(message)
        self.prune()

    def prune(self) -> None:
        """Prune messages based on count and token limits"""
        # TODO:
        #   remove unecessary messages
        #   cut
        #   summarize cut content

        # Always keep system messages
        system_messages = [m for m in self.messages if m.type == MessageType.SYSTEM]

        # Token-based pruning (rough estimation)
        total_tokens = self.estimate_tokens()
        if total_tokens > self.max_tokens:
            # Remove oldest non-system messages until under token limit
            non_system_messages = [
                m for m in self.messages if m.type != MessageType.SYSTEM
            ]
            while total_tokens > self.max_tokens * 0.8 and len(non_system_messages) > 1:
                removed = non_system_messages.pop(0)
                total_tokens -= self.estimate_message_tokens(removed)

            self.messages = system_messages + non_system_messages

    def estimate_tokens(self) -> int:
        """Rough token estimation (1 token ≈ 4 characters)"""
        return sum(self.estimate_message_tokens(msg) for msg in self.messages)

    def estimate_message_tokens(self, message: Message) -> int:
        """Estimate tokens for a single message"""
        return len(message.content) // 4 + 10  # Add some overhead

    def get_openai_messages(self) -> List[Dict[str, str]]:
        """Convert to OpenAI message format"""
        openai_messages = []
        for msg in self.messages:
            if msg.type == MessageType.CALL_FUNCTION:
                # Convert function calls to assistant messages with tool calls
                openai_messages.append({"role": "assistant", "content": msg.content})
            elif msg.type == MessageType.RESULT_FUNCTION:
                # Convert function results to tool messages
                openai_messages.append({"role": "tool", "content": msg.content})
            else:
                openai_messages.append({"role": msg.type.value, "content": msg.content})
        return openai_messages

    def clear(self) -> None:
        """Clear all messages except system messages"""
        system_messages = [m for m in self.messages if m.type == MessageType.SYSTEM]
        self.messages = system_messages

    def get_last_user_message(self) -> Optional[Message]:
        """Get the last user message"""
        for msg in reversed(self.messages):
            if msg.type == MessageType.USER:
                return msg
        return None

    def get_last_agent_message(self) -> Optional[Message]:
        """Get the last agent message"""
        for msg in reversed(self.messages):
            if msg.type == MessageType.AGENT:
                return msg
        return None


class Agent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    system_prompt: str
    provider: Provider
    tools: List[Tool] = Field(default_factory=list)
    sub_agents: Optional[List["Agent"]] = Field(default_factory=list)
    history: History = Field(default_factory=History)
    name: Optional[str] = None
    description: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        # Set max_tokens from provider model
        self.history.max_tokens = self.provider.model.max_tokens
        # Add system prompt to history
        system_message = Message(type=MessageType.SYSTEM, content=self.system_prompt)
        self.history.add_message(system_message)

    def add_tool(self, tool: Tool) -> None:
        """Add a tool to this agent"""
        self.tools.append(tool)

    def add_sub_agent(self, agent: "Agent") -> None:
        """Add a sub-agent to this agent"""
        if self.sub_agents is None:
            self.sub_agents = []
        self.sub_agents.append(agent)

    def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    async def process_user_input(self, user_input: str) -> str:
        """Process user input and return agent response"""
        # Add user message to history
        user_message = Message(type=MessageType.USER, content=user_input)
        self.history.add_message(user_message)

        # Main agent loop
        while True:
            # Generate response
            response = await self.provider.generate(self.history.messages, self.tools)
            agent_message = Message(type=MessageType.AGENT, content=response)
            self.history.add_message(agent_message)

            from .tools import XMLFunctionParser

            function_calls = XMLFunctionParser.parse_function_calls(response)

            if not function_calls:
                return response

            await self.handle_function_calls(function_calls)

    async def handle_function_calls(self, function_calls: List[Dict[str, Any]]) -> None:
        """Handle function calls from agent response"""

        for call in function_calls:
            tool_name = call["tool"]
            parameters = call["parameters"]

            from .tools import XMLFunctionParser

            # Find the tool
            tool = self.get_tool_by_name(tool_name)
            if not tool:
                error_msg = f"Tool '{tool_name}' not found"
                result_message = Message(
                    type=MessageType.RESULT_FUNCTION,
                    content=XMLFunctionParser.format_function_result(
                        tool_name, {"error": error_msg}
                    ),
                )
                self.history.add_message(result_message)
                continue

            try:
                # Execute the tool
                result = await tool.execute(**parameters)

                # Format and add result to history
                result_xml = XMLFunctionParser.format_function_result(tool_name, result)
                result_message = Message(
                    type=MessageType.RESULT_FUNCTION, content=result_xml, result=result
                )
                self.history.add_message(result_message)

            except Exception as e:
                # Handle tool execution errors
                error_result = {"error": str(e), "tool": tool_name}
                error_xml = XMLFunctionParser.format_function_result(
                    tool_name, error_result
                )
                error_message = Message(
                    type=MessageType.RESULT_FUNCTION,
                    content=error_xml,
                    result=error_result,
                )
                self.history.add_message(error_message)

    def get_tools_info(self) -> str:
        """Get formatted information about available tools"""
        if not self.tools:
            return "No tools available."

        tools_info = "Available tools:\n"
        for tool in self.tools:
            tools_info += f"- {tool.name}: {tool.description or tool.prompt}\n"

        return tools_info

    def clear_history(self) -> None:
        """Clear conversation history but keep system prompt"""
        self.history.clear()
        # Re-add system prompt
        system_message = Message(type=MessageType.SYSTEM, content=self.system_prompt)
        self.history.add_message(system_message)
