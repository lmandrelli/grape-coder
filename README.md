# 🍇 Grape Coder

Grape Coder is an AI-powered coding assistant built with the Strands Framework. It leverages a multi-agent system to plan, design, and generate code for web development projects using HTML/CSS/JS.

## Commands

Grape Coder provides several commands to interact with the AI agents:

- `grape-coder config`: Interactive configuration setup for providers and agents.
- `grape-coder mono-agent [PATH]`: Run a single coding agent with a prompt in the specified path (default: current directory).
- `grape-coder code [PATH]`: Start an interactive code session with file system tools in the specified path (default: current directory).
  - Options:
    - `--debug`: Enable debug mode with verbose output.
- `grape-coder --version`: Show the current version of Grape Coder.

## Installation

To install Grape Coder, ensure you have Python 3.13 or higher installed. You can install the package using `pip` or `uv`:

```bash
pip install grape-coder
```

Or with `uv`:

```bash
uv pip install grape-coder
```

## Config
Grape Coder uses a secure JSON configuration system supporting multiple AI providers through LiteLLM. Here is a simplified example of the configuration file:

```json
{
    "providers": {
        "Mistral": {
            "provider": "mistral",
            "api_key": "your-api-key",
            "api_base_url": null
        }
    },
    "agents": {
        "researcher": {
            "provider_ref": "Mistral",
            "model_name": "mistral-large-latest"
        },
        "code_agent": {
            "provider_ref": "Mistral",
            "model_name": "devstral-latest"
        }
    }
}
```
To update your configuration, run:

```bash
grape-coder config
```


## Development

### Project Structure

The project is structured as follows:

- `src/grape_coder/`: Main package source code.
  - `agents/`: Contains agent definitions (code, mono_agent, todo, etc.).
    - `composer/`: Logic for the composer graph (orchestrator, generators).
    - `planner/`: Planner swarm agents (architect, designer, researcher, content planner).
    - `review/`: Review graph agents for quality assurance (reviewer, quality evaluator, task generator, code revision).
  - `config/`: Configuration management (CLI, models, providers).
  - `display/`: UI and display utilities.
  - `nodes/`: Task filtering nodes.
  - `templates/`: File templates for code generation.
  - `tools/`: Utility tools (web, work_path).
- `tests/`: Unit and integration tests.

### Agent Description

Grape Coder employs a variety of specialized agents, each with a specific role in the development process:

#### Planner Swarm
- **Researcher**: Gathers context and requirements for the project.
- **Architect**: Defines the site structure and technical specifications.
- **Designer**: Establishes the visual identity, layout, and UI/UX guidelines.
- **Content Planner**: Structures the website's content and messaging.

#### Composer Graph
- **Todo Generator**: Breaks down the plan into actionable development tasks.
- **Orchestrator**: Coordinates the generation process, routing tasks to specialized agents.
- **Class Generator**: Generates CSS styles and classes.
- **JavaScript Agent**: Implements interactive functionality and logic.
- **SVG Agent**: Creates vector graphics and icons.
- **Text Generator**: Writes the textual content for the web pages.
- **Code Agent**: Assembles the final HTML structure and integrates all components.

#### Review Graph
- **Linter Node**: Runs deterministic linters on the work path directory using oxlint, markuplint, purgecss, and linkinator to identify code quality issues before the review process.
- **Reviewer Agent**: Provides detailed natural language feedback on code quality, visual aesthetics, UX, and best practices.
- **Score Evaluator Agent**: Assesses code quality and assigns numerical scores (0-20) across five categories: code validity, integration, responsiveness, best practices, and accessibility.
- **Review Task Generator Agent**: Converts natural language reviews into structured, actionable XML tasks organized by priority.
- **Code Revision Agent**: Implements fixes based on review feedback, addressing each task systematically to improve code quality.

### Graph
The graph below illustrates the multi-agent architecture of Grape Coder, highlighting three of its core components: the Planner Swarm for project planning, the Composer Graph for code generation, and the Review Graph for quality assurance with iterative revision.

```mermaid
graph TD
    %% --- COLOR PALETTE ---
    classDef planner fill:#e1f5fe,stroke:#0277bd,stroke-width:2px,color:#000;
    classDef filter fill:#fff9c4,stroke:#fbc02d,stroke-width:2px,stroke-dasharray: 5 5;
    classDef utility fill:#d1c4e9,stroke:#512da8,stroke-width:2px,stroke-dasharray: 3 3;
    classDef generator fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;
    classDef orchestrator fill:#263238,stroke:#000,stroke-width:4px,color:#fff;
    classDef userInput fill:#ffccbc,stroke:#d84315,stroke-width:2px;
    classDef reviewer fill:#ffe0b2,stroke:#f57c00,stroke-width:2px;
    classDef decision fill:#c8e6c9,stroke:#388e3c,stroke-width:2px;
    classDef endNode fill:#000,stroke:#000,color:#fff;
    classDef invisible fill:none,stroke:none,color:none;

    %% --- MAIN GRAPH ---
    User[User Input]:::userInput --> PlannerSwarm
    PlannerSwarm --> TodoGenerator[Todo Generator]:::orchestrator
    TodoGenerator --> Orchestrator

    subgraph PlannerSwarm["Planner Swarm"]
        direction TB
        Researcher[Researcher Agent]
        Architect[Architect Agent]
        Designer[Designer Agent]
        ContentPlanner[Content Planner Agent]
    end

    subgraph ComposerGraph["Composer Graph"]
        Orchestrator[Orchestrator Agent]:::orchestrator

        %% Filters
        ClassFilter[class_task_filter]
        JSFilter[js_task_filter]
        SVGFilter[svg_task_filter]
        TextFilter[text_task_filter]
        CodeFilter[code_task_filter]

        %% Agents
        ClassAgent[Class Generator Agent]
        JSAgent[JavaScript Agent]
        SVGAgent[SVG Agent]
        TextAgent[Text Generator Agent]
        CodeAgent[Code Agent]

        %% Links
        Orchestrator --> ClassFilter & JSFilter & SVGFilter & TextFilter & CodeFilter
        ClassFilter --> ClassAgent
        JSFilter --> JSAgent
        SVGFilter --> SVGAgent
        TextFilter --> TextAgent

        ClassAgent & JSAgent & CodeFilter & SVGAgent & TextAgent -.->|wait for all| CodeAgent
    end

    CodeAgent --> Linter

    subgraph ReviewGraph["Review Graph"]
        direction TB
        Linter[Linter Node]
        Reviewer[Reviewer Agent]
        ScoreEvaluator[Score Evaluator Agent]
        TaskGenerator[Review Task Generator Agent]
        CodeRevision[Code Revision Agent]
        ToolReset[Tool Limit Reset]

        Linter --> Reviewer
        Reviewer --> ScoreEvaluator
        Reviewer --> TaskGenerator
        ScoreEvaluator -.->|❌ needs revision| CodeRevision
        TaskGenerator -- tasks --> CodeRevision
        CodeRevision --> ToolReset
        ToolReset --> Linter
    end

    ScoreEvaluator -- "✅ Approved" ----> FinalOutput((Final Output))

    %% --- APPLY CLASSES ---
    class Researcher,Architect,Designer,ContentPlanner planner;
    class ClassFilter,JSFilter,SVGFilter,TextFilter,CodeFilter filter;
    class Linter,ToolReset utility;
    class ClassAgent,JSAgent,SVGAgent,TextAgent,CodeAgent generator;
    class Reviewer,ScoreEvaluator,TaskGenerator,CodeRevision reviewer;
    class QualityCheck decision;
    class FinalOutput endNode;

    %% --- CENTERED LEGEND ---
    %% Add invisible nodes to force centering
    InvisibleLeft[ ]:::invisible
    InvisibleRight[ ]:::invisible

    subgraph Legend["Legend"]
        direction LR
        L1[Planner]:::planner
        L2[Filter]:::filter
        L4[Utility]:::utility
        L3[Generator]:::generator
        L5[Orchestration]:::orchestrator
        L6[Review]:::reviewer

        L1 ~~~ L2
        L2 ~~~ L4
        L4 ~~~ L3
        L3 ~~~ L5
        L5 ~~~ L6
    end

    %% Invisible links to enforce centered layout
    FinalOutput ~~~ InvisibleLeft
    InvisibleLeft ~~~ Legend
    Legend ~~~ InvisibleRight
```
