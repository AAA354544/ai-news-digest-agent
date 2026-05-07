import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(help="AI News Digest Agent CLI", invoke_without_command=True)
console = Console()


def show_status() -> None:
    console.print(
        Panel(
            "[bold]ai-news-digest-agent[/bold]\n"
            "Status: Module 0 - Project Skeleton\n"
            "No real fetch/LLM/email logic yet."
        )
    )


@app.callback()
def main(ctx: typer.Context) -> None:
    """Default entry: show status when no subcommand is provided."""
    if ctx.invoked_subcommand is None:
        show_status()


@app.command()
def status() -> None:
    """Show current project status."""
    show_status()


if __name__ == "__main__":
    app()
