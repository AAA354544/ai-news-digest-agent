from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from src.config import validate_runtime_config
from src.notifiers.recipients import get_enabled_recipients, load_recipients, parse_email_list
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


def _resolve_cli_recipients(to: str | None, group: str | None) -> list[str] | None:
    collected: list[str] = []
    if to:
        collected.extend(parse_email_list(to))
    if group:
        recipients_data = load_recipients()
        collected.extend(get_enabled_recipients(recipients_data, group=group))
    deduped: list[str] = []
    seen: set[str] = set()
    for email in collected:
        key = email.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(key)
    return deduped if deduped else None


def show_status() -> None:
    console.print(
        Panel(
            "[bold]ai-news-digest-agent[/bold]\n"
            "Core pipeline + CLI + Streamlit + GitHub Actions are ready.\n"
            "Current stage: Optimization Round 1 stabilization (pending verification)."
        )
    )


@app.callback()
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        show_status()


@app.command()
def status() -> None:
    show_status()


@app.command("preflight")
def preflight_cmd(
    mode: str = typer.Option(
        "local",
        "--mode",
        help="Validation mode: local | send-email | github-actions-report | github-actions-send",
    ),
) -> None:
    result = validate_runtime_config(mode=mode)
    warnings = result.get("warnings", []) if isinstance(result, dict) else []
    errors = result.get("errors", []) if isinstance(result, dict) else []
    ok = bool(result.get("ok")) if isinstance(result, dict) else False

    if warnings:
        for warning in warnings:
            console.print(f"[yellow][warning][/yellow] {warning}")

    if not ok:
        for error in errors:
            console.print(f"[red][error][/red] {error}")
        raise typer.Exit(code=1)

    console.print(f"[green]Preflight passed.[/green] mode={mode}")


@app.command("fetch")
def fetch_cmd() -> None:
    console.print("[cyan]Running fetch step...[/cyan]")
    path = run_fetch_step()
    console.print(f"[green]Fetch completed.[/green] raw_path={path}")


@app.command("clean")
def clean_cmd() -> None:
    console.print("[cyan]Running clean step...[/cyan]")
    path = run_clean_step()
    console.print(f"[green]Clean completed.[/green] cleaned_path={path}")


@app.command("analyze")
def analyze_cmd(
    llm_limit: Optional[int] = typer.Option(None, "--llm-limit", help="LLM candidate limit for test runs."),
) -> None:
    console.print("[cyan]Running analyze step...[/cyan]")
    path = run_analyze_step(limit_for_test=llm_limit)
    console.print(f"[green]Analyze completed.[/green] digest_path={path}")


@app.command("report")
def report_cmd() -> None:
    console.print("[cyan]Running report step...[/cyan]")
    md_path, html_path = run_report_step()
    console.print(f"[green]Report completed.[/green] markdown_path={md_path} html_path={html_path}")


@app.command("send-email")
def send_email_cmd(
    to: Optional[str] = typer.Option(None, "--to", help="Comma/semicolon/newline separated recipient emails."),
    group: Optional[str] = typer.Option(None, "--group", help="Recipient group name from data/recipients.local.json."),
) -> None:
    console.print("[cyan]Running email step...[/cyan]")
    recipients = _resolve_cli_recipients(to=to, group=group)
    if recipients is None:
        console.print("[yellow]Using default RECIPIENT_EMAIL from environment.[/yellow]")
    else:
        console.print(f"[cyan]Resolved recipients: {len(recipients)}[/cyan]")
    result = run_email_step(recipients=recipients)
    console.print(f"[green]Email sent.[/green] recipients={result.get('recipient_count')}")


@app.command("run-pipeline")
def run_pipeline_cmd(
    send_email: bool = typer.Option(False, "--send-email", help="Send email after report generation."),
    llm_limit: Optional[int] = typer.Option(None, "--llm-limit", help="LLM candidate limit for this run."),
    to: Optional[str] = typer.Option(None, "--to", help="Comma/semicolon/newline separated recipient emails."),
    group: Optional[str] = typer.Option(None, "--group", help="Recipient group name from data/recipients.local.json."),
) -> None:
    console.print("[cyan]Running full pipeline...[/cyan]")
    recipients = _resolve_cli_recipients(to=to, group=group) if send_email else None
    if send_email and recipients is None:
        console.print("[yellow]Using default RECIPIENT_EMAIL from environment.[/yellow]")
    if send_email and recipients is not None:
        console.print(f"[cyan]Resolved recipients: {len(recipients)}[/cyan]")
    outputs = run_full_pipeline(send_email=send_email, llm_candidate_limit=llm_limit, recipients=recipients)
    console.print("[green]Pipeline completed.[/green]")
    for key, value in outputs.items():
        console.print(f"{key}: {value}")
    if send_email:
        email_result = outputs.get("email_result") if isinstance(outputs, dict) else None
        count = email_result.get("recipient_count") if isinstance(email_result, dict) else "unknown"
        console.print(f"email: sent recipients={count}")


if __name__ == "__main__":
    app()
