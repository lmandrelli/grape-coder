import pytest
import os
from unittest.mock import patch, AsyncMock

from grape_coder.models import LLMModel, Message, MessageType, Tool, ToolParameter
from grape_coder.providers import LiteLLMProvider


class TestLiteLLMProvider:
    """Test LiteLLM provider functionality"""

    def test_provider_initialization_openai(self):
        """Test provider initialization with OpenAI model"""
        model = LLMModel(name="openai/gpt-4")
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            provider = LiteLLMProvider(model=model)
            assert provider.model == model
            assert provider.api_key == "test-key"

    def test_provider_initialization_anthropic(self):
        """Test provider initialization with Anthropic model"""
        model = LLMModel(name="anthropic/claude-3-sonnet")
        
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            provider = LiteLLMProvider(model=model)
            assert provider.model == model
            assert provider.api_key == "test-key"

    def test_provider_initialization_openrouter(self):
        """Test provider initialization with OpenRouter model"""
        model = LLMModel(name="openrouter/meta-llama/llama-3.1-8b-instruct")
        
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            provider = LiteLLMProvider(model=model)
            assert provider.model == model
            assert provider.api_key == "test-key"

    def test_provider_initialization_no_api_key(self):
        """Test provider initialization fails without API key"""
        model = LLMModel(name="openai/gpt-4")
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API key is required"):
                LiteLLMProvider(model=model)

    @pytest.mark.asyncio
    async def test_generate_simple_message(self):
        """Test generating a response for a simple message"""
        model = LLMModel(name="openai/gpt-4")
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            provider = LiteLLMProvider(model=model)
            
            messages = [
                Message(type=MessageType.USER, content="Hello, how are you?")
            ]
            
            # Mock the litellm.acompletion function
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message.content = "I'm doing well, thank you!"
            
            with patch('grape_coder.providers.litellm.acompletion', return_value=mock_response):
                response = await provider.generate(messages)
                assert response == "I'm doing well, thank you!"

    @pytest.mark.asyncio
    async def test_generate_with_tools(self):
        """Test generating a response with tools"""
        model = LLMModel(name="openai/gpt-4")
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            provider = LiteLLMProvider(model=model)
            
            messages = [
                Message(type=MessageType.USER, content="What's 2+2?")
            ]
            
            # Create a simple tool
            async def calculator(expression: str) -> str:
                try:
                    result = eval(expression)
                    return str(result)
                except:
                    return "Error"
            
            tool = Tool(
                name="calculator",
                prompt="Calculate mathematical expressions",
                function=calculator,
                parameters=[
                    ToolParameter(name="expression", type="string", description="Mathematical expression", required=True)
                ]
            )
            
            # Mock the litellm.acompletion function
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message.content = "The result is 4"
            
            with patch('grape_coder.providers.litellm.acompletion', return_value=mock_response):
                response = await provider.generate(messages, tools=[tool])
                assert response == "The result is 4"

    @pytest.mark.asyncio
    async def test_generate_with_system_message(self):
        """Test generating a response with system message"""
        model = LLMModel(name="anthropic/claude-3-sonnet")
        
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            provider = LiteLLMProvider(model=model)
            
            messages = [
                Message(type=MessageType.SYSTEM, content="You are a helpful assistant."),
                Message(type=MessageType.USER, content="Hello!")
            ]
            
            # Mock the litellm.acompletion function
            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message.content = "Hello! How can I help you today?"
            
            with patch('grape_coder.providers.litellm.acompletion', return_value=mock_response):
                response = await provider.generate(messages)
                assert response == "Hello! How can I help you today?"

    @pytest.mark.asyncio
    async def test_generate_api_error(self):
        """Test handling of API errors"""
        model = LLMModel(name="openai/gpt-4")
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            provider = LiteLLMProvider(model=model)
            
            messages = [
                Message(type=MessageType.USER, content="Hello")
            ]
            
            # Mock API error
            with patch('grape_coder.providers.litellm.acompletion', side_effect=Exception("API Error")):
                with pytest.raises(RuntimeError, match="LiteLLM API error"):
                    await provider.generate(messages)