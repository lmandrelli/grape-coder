# grape-coder

A Python CLI application built with Typer and managed with uv.

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

**Basic usage:**
```bash
grape-coder <arg>    # Greet with the provided argument
```

**Available options:**
```bash
grape-coder --version, -v    # Show version and exit
grape-coder --help           # Show help message
```

**Examples:**
```bash
grape-coder "Hello World"    # Output: Hello Hello World ! This is grape-coder.
grape-coder --version        # Shows ASCII art logo and version
```

## Key Configuration Details

- **Python Version**: 3.13+ (specified in `.python-version` and `pyproject.toml`)
- **Entry Point**: `grape-coder` command points to `grape_coder.main:app`
- **Main Dependency**: `typer>=0.20.0` for CLI functionality
- **Build System**: Uses `uv_build` backend