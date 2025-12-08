# grape-coder

Grape Coder is an AI-powered code assistant. Built with Typer and managed with uv.

## Development with uv

### Project Structure
```
grape-coder/
├── src/grape_coder/          # Package source code
│   ├── __init__.py
│   └── main.py              # CLI application
├── pyproject.toml           # Project configuration
├── uv.lock                  # Locked dependencies
└── .python-version          # Python version 
```

### Setup & Installation

**Install dependencies:**
```bash
uv sync
```

**Activate virtual environment:**
```bash
source .venv/bin/activate  # Unix/macOS
# or
.venv\Scripts\activate     # Windows
```

### Development Workflow

**Run the CLI application:**
```bash
# With uv (no venv activation needed)
uv run grape-coder --help
uv run grape-coder "world"
uv run grape-coder --version
```

**Add new dependencies:**
```bash
uv add package_name
uv add --dev package_name  # Development dependency
```

**Update dependencies:**
```bash
uv lock --upgrade
```

### Testing

This project uses pytest for testing. Tests are located in the `tests/` directory.

**Run all tests:**
```bash
uv run pytest
```

**Run tests with verbose output:**
```bash
uv run pytest -v
```

**Run a specific test file:**
```bash
uv run pytest tests/test_basic.py
```

**Run tests with coverage:**
```bash
uv run pytest --cov=grape_coder
```

#### Adding New Tests

1. Create test files in the `tests/` directory with names starting with `test_`
2. Write test functions starting with `test_`
3. Use `assert` statements for assertions

**Example test file (`tests/test_example.py`):**
```python
def test_example_function():
    """Example test showing basic pytest usage."""
    result = 2 + 2
    assert result == 4

def test_another_example():
    """Another example test."""
    data = ["apple", "banana", "cherry"]
    assert "banana" in data
    assert len(data) == 3
```

**Test discovery:**
- Pytest automatically discovers test files matching `test_*.py` pattern
- Test functions must start with `test_`
- Test classes must start with `Test`

### Building & Publishing
```bash
uv build
uv publish  # Requires PyPI credentials
```

## CLI Commands

**Configuration setup:**
```bash
grape-coder config    # Interactive configuration setup for providers and agents
```

**Code agent:**
```bash
grape-coder code [path]    # Start an interactive code session (default: current directory)
```

**Available options:**
```bash
grape-coder --version, -v    # Show version and exit
grape-coder --help           # Show help message
```

**Examples:**
```bash
grape-coder config           # Set up providers and agents
grape-coder code ./my-project  # Start coding in a specific directory
grape-coder --version        # Shows ASCII art logo and version
```

## Configuration

Grape Coder uses a secure JSON configuration system supporting multiple AI providers through LiteLLM:

### Supported Providers and Models examples
- **OpenAI**: `gpt-5.1`, `gpt-5.1-codex-max`
- **Anthropic**: `claude-sonnet-4-5`, `claude-opus-4-5`
- **Gemini**: `gemini-3-pro-preview`, `gemini-2.5-flash`
- **Mistral**: `devstral-medium-2507`, `mistral-large-latest`, `ministral-8b-latest`
- **Ollama**: `ministral-3:14b`, `gpt-oss:20b`
- **Custom**: OpenAI-compatible APIs (model names automatically prefixed with `openai/`), with chutes.ai for exemple :`base_url : https://llm.chutes.ai/v1/`; `model_name : zai-org/GLM-4.6`

### Setup
Run `grape-coder config` to interactively configure providers and agents. The configuration is stored securely in your system's config directory with proper file permissions.

## Key Configuration Details

- **Python Version**: 3.13+ (specified in `.python-version` and `pyproject.toml`)
- **Entry Point**: `grape-coder` command points to `grape_coder.main:app`
- **Main Dependencies**: `typer>=0.20.0` for CLI, `strands-agents` for AI agents, `litellm` for model integration
- **Build System**: Uses `uv_build` backend
