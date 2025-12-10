"""CLI configuration interface for Grape Coder."""

from rich.console import Console
from rich.table import Table
from prompt_toolkit import prompt
from prompt_toolkit.validation import Validator

from grape_coder.config.models import ProviderConfig, AgentConfig, GrapeCoderConfig, ProviderType
from grape_coder.config.manager import get_config_manager, ConfigManager
from grape_coder.config.litellm_integration import ProviderFactory
from grape_coder.agents.identifiers import get_agent_values

console = Console()


def run_config_setup() -> None:
    """Run interactive configuration menu for providers and agents."""
    console.print("[bold blue]Grape Coder Configuration[/bold blue]")

    config_manager = get_config_manager()

    # Load existing config or create new one
    if config_manager.config_exists():
        config = config_manager.config or GrapeCoderConfig()
        console.print("[green]Configuration loaded successfully.[/green]")
    else:
        config = GrapeCoderConfig()
        console.print(
            "[yellow]No existing configuration found. Starting fresh.[/yellow]"
        )

    # Show current status and main menu
    main_menu(config_manager, config)


def main_menu(config_manager: ConfigManager, config: GrapeCoderConfig) -> None:
    """Display main configuration menu."""
    while True:
        # Show current status
        show_config_status(config)

        console.print("\n[bold]Configuration Options:[/bold]")
        console.print("1. Add a provider")
        console.print("2. Remove a provider")
        console.print("3. Setup models for agents")
        console.print("4. Exit")

        choice = prompt(
            "Select an option (1-4): ", validator=choice_validator(["1", "2", "3", "4"])
        )

        if choice == "1":
            add_provider(config)
        elif choice == "2":
            remove_provider(config)
        elif choice == "3":
            map_models_to_agents(config)
        elif choice == "4":
            # Save and exit
            try:
                config_manager.save_config(config)
                console.print(
                    f"[bold green]Configuration saved to: {config_manager.get_config_path()}[/bold green]"
                )
                console.print("[bold green]Goodbye![/bold green]")
                break
            except Exception as e:
                console.print(f"[red]Error saving configuration: {e}[/red]")
                import typer

                raise typer.Exit(1)


def show_config_status(config: GrapeCoderConfig) -> None:
    """Display current configuration status."""
    console.print(
        "\n[bold underline]Current Configuration Status:[/bold underline]")

    # Providers table
    providers_table = Table(title="Providers")
    providers_table.add_column("Name", style="cyan")
    providers_table.add_column("Type", style="magenta")
    providers_table.add_column("Base URL", style="green")

    if config.providers:
        for name, provider_config in config.providers.items():
            base_url = provider_config.api_base_url or "Using default"
            providers_table.add_row(
                name, provider_config.provider.value, base_url)
    else:
        providers_table.add_row("No providers configured", "", "")

    console.print(providers_table)

    # Agents table
    agents_table = Table(title="Agent Mappings")
    agents_table.add_column("Agent", style="cyan")
    agents_table.add_column("Provider", style="magenta")
    agents_table.add_column("Model", style="green")

    if config.agents:
        for name, agent_config in config.agents.items():
            agents_table.add_row(
                name, agent_config.provider_ref, agent_config.model_name
            )
    else:
        agents_table.add_row("No agents configured", "", "")

    console.print(agents_table)


def remove_provider(config: GrapeCoderConfig) -> None:
    """Remove a provider configuration."""
    console.print("\n[bold]Remove Provider[/bold]")

    if not config.providers:
        console.print("[red]No providers configured to remove.[/red]")
        return

    # List providers
    provider_list = list(config.providers.keys())
    console.print("\nAvailable providers:")
    for i, provider in enumerate(provider_list, 1):
        provider_config = config.providers[provider]
        console.print(f"{i}. {provider} ({provider_config.provider.value})")

    choice = prompt(
        f"Select provider to remove (1-{len(provider_list)}): ",
        validator=choice_validator(
            [str(i) for i in range(1, len(provider_list) + 1)]),
    )

    provider_to_remove = provider_list[int(choice) - 1]

    # Check if any agents are using this provider
    dependent_agents = [
        agent_name
        for agent_name, agent_config in config.agents.items()
        if agent_config.provider_ref == provider_to_remove
    ]

    if dependent_agents:
        console.print(
            f"[red]Cannot remove provider '{provider_to_remove}' because it's used by agents: {', '.join(dependent_agents)}[/red]"
        )
        console.print(
            "[yellow]Please reconfigure or remove these agents first.[/yellow]"
        )
        return

    # Remove provider
    del config.providers[provider_to_remove]
    console.print(
        f"[green]Provider '{provider_to_remove}' removed successfully.[/green]"
    )


def map_models_to_agents(config: GrapeCoderConfig) -> None:
    """Map models to agents using predefined agent identifiers."""
    console.print("\n[bold]Map Models to Agents[/bold]")

    if not config.providers:
        console.print(
            "[red]No providers configured. Add a provider first.[/red]")
        return

    # Define available agents directly
    available_agents = get_agent_values()

    # Show available agents
    console.print("\nAvailable agents:")
    for i, agent in enumerate(available_agents, 1):
        console.print(f"{i}. {agent}")

    # Select agent
    agent_choice = prompt(
        f"Select agent to configure (1-{len(available_agents)}): ",
        validator=choice_validator(
            [str(i) for i in range(1, len(available_agents) + 1)]
        ),
    )

    selected_agent = available_agents[int(agent_choice) - 1]

    # Select provider
    console.print("\nAvailable providers:")
    provider_list = list(config.providers.keys())
    for i, provider in enumerate(provider_list, 1):
        provider_config = config.providers[provider]
        console.print(f"{i}. {provider} ({provider_config.provider.value})")

    provider_choice = prompt(
        f"Select provider (1-{len(provider_list)}): ",
        validator=choice_validator(
            [str(i) for i in range(1, len(provider_list) + 1)]),
    )

    selected_provider = provider_list[int(provider_choice) - 1]

    # Get model name with suggestions
    provider_config = config.providers[selected_provider]
    suggested = ProviderFactory.get_suggested_models(provider_config.provider)

    if suggested:
        console.print(
            f"Suggested models for {provider_config.provider.value}: {', '.join(suggested)}"
        )

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

    # Create or update agent config
    try:
        agent_config = AgentConfig(
            provider_ref=selected_provider, model_name=model_name
        )
        config.agents[selected_agent] = agent_config
        console.print(
            f"[green]Agent '{selected_agent}' mapped to {selected_provider}/{model_name} successfully.[/green]"
        )
    except Exception as e:
        console.print(f"[red]Error creating agent mapping: {e}[/red]")


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
