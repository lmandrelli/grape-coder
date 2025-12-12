# Contributing

We welcome contributions! Here's how you can get involved:

## Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Project Guidelines

- Use Python 3.13+ with type hints
- Follow the existing code style (PEP 8)
- Add docstrings for public methods and classes
- Run tests before committing (`pytest`)
- Write clear, descriptive commit messages, use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) style

## Testing

Before submitting a pull request, please ensure that:

1. The project installs without errors
2. You run the tests and fix any issues (`pytest`)
3. The code follows the project guidelines
4. New functionality includes appropriate tests

## Development Setup

### Prerequisites

- Python 3.13+
- uv (recommended) or pip
- Git

### Installation

Install dependencies:
    ```bash
    uv sync
    ```

### Development Workflow

1. Make changes to the source code in the `src/` directory.

2. Run tests to ensure everything is working:

    ```bash
    pytest
    ```

## Project Structure

```
grape-coder/
├── src/                      # Source code
│   └── grape_coder/          # Main package
│       ├── agents/           # Agent definitions
│       ├── composer/         # Composer graph logic
│       ├── config/           # Configuration management
│       ├── display/          # UI and display utilities
│       ├── nodes/            # Task filtering nodes
│       ├── planner/          # Planner swarm agents
│       └── tools/            # Utility tools
├── tests/                    # Test files
├── pyproject.toml            # Project configuration and dependencies
└── README.md                 # Project documentation
```

## Architecture

### Core Components

1. **Grape Coder CLI** (`src/grape_coder/main.py`): Main entry point that provides the CLI commands (`config`, `mono-agent`, `code`).

2. **Agents** (`src/grape_coder/agents/`): Contains the definitions for various agents like `mono_agent`, `todo`, and `code`.

3. **Composer** (`src/grape_coder/composer/`): Manages the orchestration of agents to generate code based on plans.

4. **Planner** (`src/grape_coder/planner/`): A swarm of agents (Architect, Designer, Researcher, Content Planner) that creates development plans.

5. **Configuration** (`src/grape_coder/config/`): Handles user configuration for providers and models.

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.