from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from src.pipeline import (
    run_analyze_step,
    run_clean_step,
    run_email_step,
    run_fetch_step,
    run_full_pipeline,
    run_report_step,
)

app = typer.Typer(help="AI News Digest Agent CLI", invoke_without_command=True)
console = Console()


def show_status() -> None:
    console.print(
        Panel(
            "[bold]ai-news-digest-agent[/bold]\n"
            "Modules 0-5 complete, modules 6-9 implemented (pending verification)."
        )
    )


@app.callback()
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        show_status()


@app.command()
def status() -> None:
    show_status()


@app.command("fetch")
def fetch_cmd(
    topic: Optional[str] = typer.Option(None, "--topic", help="Override digest topic for this run."),
) -> None:
    console.print("[cyan]Running fetch step...[/cyan]")
    path = run_fetch_step(topic_override=topic)
    console.print(f"[green]Fetch completed.[/green] raw_path={path}")


@app.command("clean")
def clean_cmd() -> None:
    console.print("[cyan]Running clean step...[/cyan]")
    path = run_clean_step()
    console.print(f"[green]Clean completed.[/green] cleaned_path={path}")


@app.command("analyze")
def analyze_cmd(
    llm_limit: Optional[int] = typer.Option(None, "--llm-limit", help="LLM candidate limit for test runs."),
    topic: Optional[str] = typer.Option(None, "--topic", help="Override digest topic for this run."),
) -> None:
    console.print("[cyan]Running analyze step...[/cyan]")
    path = run_analyze_step(limit_for_test=llm_limit, topic_override=topic)
    console.print(f"[green]Analyze completed.[/green] digest_path={path}")


@app.command("report")
def report_cmd() -> None:
    console.print("[cyan]Running report step...[/cyan]")
    md_path, html_path = run_report_step()
    console.print(f"[green]Report completed.[/green] markdown_path={md_path} html_path={html_path}")


@app.command("send-email")
def send_email_cmd() -> None:
    console.print("[cyan]Running email step...[/cyan]")
    run_email_step()
    console.print("[green]Email sent.[/green]")


@app.command("run-pipeline")
def run_pipeline_cmd(
    send_email: bool = typer.Option(False, "--send-email", help="Send email after report generation."),
    llm_limit: Optional[int] = typer.Option(None, "--llm-limit", help="LLM candidate limit for this run."),
    topic: Optional[str] = typer.Option(None, "--topic", help="Override digest topic for this run."),
) -> None:
    console.print("[cyan]Running full pipeline...[/cyan]")
    outputs = run_full_pipeline(send_email=send_email, llm_candidate_limit=llm_limit, topic_override=topic)
    console.print("[green]Pipeline completed.[/green]")
    for key, value in outputs.items():
        console.print(f"{key}: {value}")
    if send_email:
        console.print("email: sent")


if __name__ == "__main__":
    app()
