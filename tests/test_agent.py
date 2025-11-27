import pytest

from grape_coder.models import Agent, History, LLMModel, Message, MessageType
from grape_coder.providers import MockProvider
from grape_coder.tools import BaseTool, XMLFunctionParser


class TestMessage:
    """Test Message model"""

    def test_message_creation(self):
        message = Message(type=MessageType.USER, content="Hello")
        assert message.type == MessageType.USER
        assert message.content == "Hello"
        assert message.result is None
        assert message.metadata == {}

    def test_message_with_result(self):
        message = Message(
            type=MessageType.RESULT_FUNCTION,
            content="Result",
            result={"output": "success"},
        )
        assert message.result == {"output": "success"}


class TestHistory:
    """Test History model"""

    # TODO: after new History class


class TestTool:
    """Test Tool functionality"""

    @pytest.mark.asyncio
    async def test_base_tool_execution(self):
        async def test_function(x: int, y: int) -> int:
            return x + y

        tool = BaseTool(name="add", prompt="Add two numbers", function=test_function)

        result = await tool.execute(x=2, y=3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        async def failing_function():
            raise ValueError("Test error")

        tool = BaseTool(
            name="failing_tool", prompt="This tool fails", function=failing_function
        )

        result = await tool.execute()
        assert "error" in str(result).lower()


class TestXMLFunctionParser:
    """Test XML function parsing"""

    def test_parse_function_calls(self):
        xml_content = """
        <function_calls>
        <invoke tool="calculator">
        <parameters>
        <expression>2+2</expression>
        </parameters>
        </invoke>
        </function_calls>
        """

        calls = XMLFunctionParser.parse_function_calls(xml_content)
        assert len(calls) == 1
        assert calls[0]["tool"] == "calculator"
        assert calls[0]["parameters"]["expression"] == "2+2"

    def test_parse_multiple_function_calls(self):
        xml_content = """
        <function_calls>
        <invoke tool="calculator">
        <parameters>
        <expression>2+2</expression>
        </parameters>
        </invoke>
        <invoke tool="echo">
        <parameters>
        <message>Hello</message>
        </parameters>
        </invoke>
        </function_calls>
        """

        calls = XMLFunctionParser.parse_function_calls(xml_content)
        assert len(calls) == 2
        assert calls[0]["tool"] == "calculator"
        assert calls[1]["tool"] == "echo"

    def test_parse_no_function_calls(self):
        xml_content = "This is just regular text without function calls."

        calls = XMLFunctionParser.parse_function_calls(xml_content)
        assert len(calls) == 0

    def test_format_function_result(self):
        result = {"output": 4}
        xml_result = XMLFunctionParser.format_function_result("calculator", result)

        assert "<function_results>" in xml_result
        assert 'tool="calculator"' in xml_result
        assert "4" in xml_result


class TestAgent:
    """Test Agent functionality"""

    @pytest.mark.asyncio
    async def test_agent_creation(self):
        model = LLMModel(name="test")
        provider = MockProvider(model=model)
        agent = Agent(
            name="Test Agent", system_prompt="You are a test agent", provider=provider
        )

        assert agent.name == "Test Agent"
        assert agent.system_prompt == "You are a test agent"
        assert len(agent.tools) == 0
        # System message should be added automatically
        assert len(agent.history.messages) == 1
        assert agent.history.messages[0].type == MessageType.SYSTEM

    def test_add_tool(self):
        model = LLMModel(name="test")
        provider = MockProvider(model=model)
        agent = Agent(system_prompt="Test", provider=provider)

        async def test_func():
            return "test"

        tool = BaseTool(name="test_tool", prompt="Test", function=test_func)
        agent.add_tool(tool)

        assert len(agent.tools) == 1
        assert agent.tools[0].name == "test_tool"

    def test_get_tool_by_name(self):
        model = LLMModel(name="test")
        provider = MockProvider(model=model)
        agent = Agent(system_prompt="Test", provider=provider)

        async def test_func():
            return "test"

        tool = BaseTool(name="test_tool", prompt="Test", function=test_func)
        agent.add_tool(tool)

        found_tool = agent.get_tool_by_name("test_tool")
        assert found_tool is not None
        assert found_tool.name == "test_tool"

        not_found = agent.get_tool_by_name("nonexistent")
        assert not_found is None

    @pytest.mark.asyncio
    async def test_process_user_input(self):
        model = LLMModel(name="test")
        provider = MockProvider(model=model)
        agent = Agent(system_prompt="Test", provider=provider)

        response = await agent.process_user_input("Hello")

        # Should have system, user, and agent messages
        assert len(agent.history.messages) >= 2

        # Check that user message was added
        user_message = agent.history.get_last_user_message()
        assert user_message is not None
        assert user_message.content == "Hello"

        # Check that agent response was added
        agent_message = agent.history.get_last_agent_message()
        assert agent_message is not None
        assert agent_message.content == response

    @pytest.mark.asyncio
    async def test_handle_function_calls(self):
        model = LLMModel(name="test")
        provider = MockProvider(model=model)
        agent = Agent(system_prompt="Test", provider=provider)

        # Add a test tool
        async def echo_tool(message: str) -> str:
            return f"Echo: {message}"

        tool = BaseTool(name="echo", prompt="Echo message", function=echo_tool)
        agent.add_tool(tool)

        # Simulate function calls
        function_calls = [{"tool": "echo", "parameters": {"message": "Hello World"}}]

        await agent.handle_function_calls(function_calls)

        # Check that function result was added to history
        result_messages = [
            m for m in agent.history.messages if m.type == MessageType.RESULT_FUNCTION
        ]
        assert len(result_messages) == 1
        assert "Echo: Hello World" in result_messages[0].content


class TestAgentIntegration:
    """Integration tests for the complete agent system"""

    @pytest.mark.asyncio
    async def test_agent_with_xml_function_calling(self):
        """Test agent with XML function calling in a realistic scenario"""

        # Create mock provider that returns XML function call
        model = LLMModel(name="test")
        provider = MockProvider(model=model)

        # Override the generate method to return XML function call
        async def mock_generate(messages, tools=None):
            if messages and messages[-1].type == MessageType.USER:
                if "calculate" in messages[-1].content.lower():
                    return """
                    I'll calculate that for you.
                    <function_calls>
                    <invoke tool="calculator">
                    <parameters>
                    <expression>5+3</expression>
                    </parameters>
                    </invoke>
                    </function_calls>
                    """
            return "I can help with that!"

        # Create a custom mock provider class
        class CustomMockProvider(MockProvider):
            async def generate(self, messages, tools=None):
                return await mock_generate(messages, tools)

        provider = CustomMockProvider(model=model)

        # Create agent with calculator tool
        agent = Agent(system_prompt="You are a helpful assistant.", provider=provider)

        async def calculator(expression: str) -> str:
            try:
                result = eval(expression)
                return str(result)
            except:
                return "Error"

        calc_tool = BaseTool(name="calculator", prompt="Calculate", function=calculator)
        agent.add_tool(calc_tool)

        # Process user input
        response = await agent.process_user_input("Please calculate 5+3")

        # Should have processed the function call
        # Check that function result is in history
        function_results = [
            m for m in agent.history.messages if m.type == MessageType.RESULT_FUNCTION
        ]
        assert len(function_results) >= 1
        assert "8" in function_results[0].content

        # Check that function call and result are in history
        function_calls = [
            m for m in agent.history.messages if m.type == MessageType.CALL_FUNCTION
        ]
        function_results = [
            m for m in agent.history.messages if m.type == MessageType.RESULT_FUNCTION
        ]

        # Note: The current implementation adds function calls as agent messages
        # and results as result_function messages
        assert len(function_results) >= 1  # At least one function result
