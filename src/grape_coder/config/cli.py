"""CLI configuration interface for Grape Coder."""

from rich.console import Console
from prompt_toolkit import prompt
from prompt_toolkit.validation import Validator

from .models import ProviderConfig, AgentConfig, GrapeCoderConfig, ProviderType
from .manager import get_config_manager
from .litellm_integration import ProviderFactory

console = Console()


def run_config_setup() -> None:
    """Run interactive configuration setup for providers and agents."""
    console.print("[bold blue]Grape Coder Configuration Setup[/bold blue]")
    console.print(
        "This will help you configure providers and agents for Grape Coder.\n"
    )

    config_manager = get_config_manager()

    # Check if config already exists
    if config_manager.config_exists():
        import typer

        if not typer.confirm("Configuration already exists. Overwrite?"):
            console.print("Configuration setup cancelled.")
            return

    # Start interactive setup
    config = interactive_setup()

    try:
        config_manager.save_config(config)
        console.print(
            f"[bold green]Configuration saved to: {config_manager.get_config_path()}[/bold green]"
        )
        console.print("[bold green]Setup complete![/bold green]")
    except Exception as e:
        console.print(f"[red]Error saving configuration: {e}[/red]")
        import typer

        raise typer.Exit(1)


def interactive_setup() -> GrapeCoderConfig:
    """Run interactive configuration setup."""
    config = GrapeCoderConfig()

    while True:
        console.print("\n[bold]Configuration Menu:[/bold]")
        console.print("1. Add provider")
        console.print("2. Add agent")
        console.print("3. List current configuration")
        console.print("4. Finish setup")

        choice = prompt(
            "Select an option (1-4): ", validator=choice_validator(["1", "2", "3", "4"])
        )

        if choice == "1":
            add_provider(config)
        elif choice == "2":
            add_agent(config)
        elif choice == "3":
            list_config(config)
        elif choice == "4":
            if not config.providers:
                console.print("[red]At least one provider is required.[/red]")
                continue
            if not config.agents:
                console.print("[red]At least one agent is required.[/red]")
                continue
            break

    return config


def choice_validator(choices: list[str]) -> Validator:
    """Create a validator for multiple choice input."""

    def validate(text: str) -> bool:
        return text in choices

    return Validator.from_callable(validate, error_message="Invalid choice")


def add_provider(config: GrapeCoderConfig) -> None:
    """Add a new provider configuration."""
    console.print("\n[bold]Add Provider[/bold]")

    # Provider name
    provider_name = prompt("Provider name: ").strip()
    if not provider_name:
        console.print("[red]Provider name is required.[/red]")
        return

    if provider_name in config.providers:
        console.print(f"[red]Provider '{provider_name}' already exists.[/red]")
        return

    # Provider type
    console.print("\nAvailable provider types:")
    for i, provider_type in enumerate(ProviderType, 1):
        console.print(f"{i}. {provider_type.value}")

    type_choice = prompt(
        "Select provider type (1-6): ",
        validator=choice_validator([str(i) for i in range(1, 7)]),
    )
    provider_type = list(ProviderType)[int(type_choice) - 1]

    # API key (hidden input)
    api_key = prompt("API key: ", is_password=True).strip()
    if not api_key:
        console.print("[red]API key is required.[/red]")
        return

    # Base URL (for custom providers)
    api_base_url = None
    if provider_type == ProviderType.CUSTOM:
        api_base_url = prompt("Base URL: ").strip()
        if not api_base_url:
            console.print("[red]Base URL is required for custom providers.[/red]")
            return

    # Create provider config
    try:
        provider_config = ProviderConfig(
            provider=provider_type, api_key=api_key, api_base_url=api_base_url
        )
        config.providers[provider_name] = provider_config
        console.print(f"[green]Provider '{provider_name}' added successfully.[/green]")

        # Show suggested models
        suggested = ProviderFactory.get_suggested_models(provider_type)
        if suggested:
            console.print(
                f"Suggested models for {provider_type.value}: {', '.join(suggested[:3])}"
            )

    except Exception as e:
        console.print(f"[red]Error creating provider: {e}[/red]")


def add_agent(config: GrapeCoderConfig) -> None:
    """Add a new agent configuration."""
    console.print("\n[bold]Add Agent[/bold]")

    if not config.providers:
        console.print("[red]Add at least one provider first.[/red]")
        return

    # Agent name
    agent_name = prompt("Agent name: ").strip()
    if not agent_name:
        console.print("[red]Agent name is required.[/red]")
        return

    if agent_name in config.agents:
        console.print(f"[red]Agent '{agent_name}' already exists.[/red]")
        return

    # Provider selection
    console.print("\nAvailable providers:")
    provider_list = list(config.providers.keys())
    for i, provider in enumerate(provider_list, 1):
        provider_config = config.providers[provider]
        console.print(f"{i}. {provider} ({provider_config.provider.value})")

    provider_choice = prompt(
        f"Select provider (1-{len(provider_list)}): ",
        validator=choice_validator([str(i) for i in range(1, len(provider_list) + 1)]),
    )
    provider_ref = provider_list[int(provider_choice) - 1]

    # Model name with suggestions
    provider_config = config.providers[provider_ref]
    suggested = ProviderFactory.get_suggested_models(provider_config.provider)

    if suggested:
        console.print(f"Suggested models: {', '.join(suggested)}")

    # Add guidance for custom providers
    if provider_config.provider == ProviderType.CUSTOM:
        console.print(
            "[yellow]Note: For OpenAI-compatible APIs, the model name will be automatically prefixed with 'openai/'[/yellow]"
        )

    model_name = prompt("Model name: ").strip()
    if not model_name:
        console.print("[red]Model name is required.[/red]")
        return

    # Validate model format
    if not ProviderFactory.validate_model_format(provider_config.provider, model_name):
        console.print("[red]Invalid model name format.[/red]")
        return

    # Create agent config
    try:
        agent_config = AgentConfig(provider_ref=provider_ref, model_name=model_name)
        config.agents[agent_name] = agent_config
        console.print(f"[green]Agent '{agent_name}' added successfully.[/green]")

    except Exception as e:
        console.print(f"[red]Error creating agent: {e}[/red]")


def list_config(config: GrapeCoderConfig) -> None:
    """Display current configuration."""
    console.print("\n[bold]Current Configuration:[/bold]")

    if config.providers:
        console.print("\n[underline]Providers:[/underline]")
        for name, provider_config in config.providers.items():
            console.print(f"  {name}: {provider_config.provider.value}")
            if provider_config.api_base_url:
                console.print(f"    Base URL: {provider_config.api_base_url}")
    else:
        console.print("\nNo providers configured.")

    if config.agents:
        console.print("\n[underline]Agents:[/underline]")
        for name, agent_config in config.agents.items():
            console.print(
                f"  {name}: {agent_config.provider_ref} -> {agent_config.model_name}"
            )
    else:
        console.print("\nNo agents configured.")
