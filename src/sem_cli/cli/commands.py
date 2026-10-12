"""Typer CLI command specifications for sem-cli."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from sem_cli import __version__
from sem_cli.analytics.hotspots import rank_hotspots
from sem_cli.cli.interactive_tui import render_home_screen
from sem_cli.cli.terminal_ui import render_analysis_results
from sem_cli.config.settings import AppConfig, load_config
from sem_cli.persistence.repositories import RepositoryDatabase
from sem_cli.repository.git_client import get_git_version, is_git_installed
from sem_cli.repository.url_parser import parse_and_validate_target
from sem_cli.services.ai_service import GeminiAIService, build_evidence_payload
from sem_cli.services.analysis_service import CompletedAnalysis, execute_analysis_pipeline
from sem_cli.services.report_service import (
    generate_csv_report,
    generate_json_report,
    generate_markdown_report,
)
from sem_cli.ui.console import SYM_FAIL, SYM_INFO, SYM_OK, SYM_WARN, console
from sem_cli.ui.panels import create_header_banner
from sem_cli.ui.tables import (
    build_comparison_table,
    build_findings_table,
    build_hotspots_table,
    build_runs_table,
)

app = typer.Typer(
    name="sem",
    help="Software Engineering Metrics & Intelligence CLI (ISWE402L)",
    no_args_is_help=False,
    invoke_without_command=True,
)


def _resolve_target_or_run(target_or_run: str | None, db: RepositoryDatabase) -> tuple[str | None, str | None]:
    """Helper to detect if target_or_run is a run_id or a repository path/URL."""
    if not target_or_run:
        target_or_run = "."

    # Check if it matches an existing run_id
    run_rec = db.get_run(target_or_run)
    if run_rec:
        return None, target_or_run

    return target_or_run, None


@app.callback()
def main_entry(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option("--version", "-v", help="Show version and exit.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable ANSI color output.")] = False,
) -> None:
    """Main callback executing when no subcommand is given (interactive home screen)."""
    if version:
        console.print(f"sem-cli version {__version__}")
        raise typer.Exit(0)

    if ctx.invoked_subcommand is None:
        config = load_config()
        choice = render_home_screen(console, config)
        if choice in ("q", "quit", "exit"):
            console.print("[dim]Exiting sem-cli. Goodbye![/dim]")
            raise typer.Exit(0)
        elif choice == "1":
            target = Prompt.ask("[bold cyan]Enter repository URL or path[/bold cyan]", default=".")
            ctx.invoke(analyze, target=target)
        elif choice == "2":
            target = Prompt.ask("[bold cyan]Enter repository URL or path[/bold cyan]", default=".")
            ctx.invoke(metrics_cmd, target=target)
        elif choice == "3":
            target = Prompt.ask("[bold cyan]Enter repository URL or path[/bold cyan]", default=".")
            ctx.invoke(hotspots_cmd, target=target)
        elif choice == "4":
            target = Prompt.ask("[bold cyan]Enter repository URL or path[/bold cyan]", default=".")
            ctx.invoke(history_cmd, target=target)
        elif choice == "5":
            target = Prompt.ask("[bold cyan]Enter repository URL or path[/bold cyan]", default=".")
            ctx.invoke(security_cmd, target=target)
        elif choice == "6":
            target = Prompt.ask("[bold cyan]Enter repository URL or path[/bold cyan]", default=".")
            ctx.invoke(stats_cmd, target=target)
        elif choice == "7":
            target = Prompt.ask("[bold cyan]Enter repository URL or path[/bold cyan]", default=".")
            question = Prompt.ask("[bold cyan]What would you like to ask Gemini?[/bold cyan]")
            ctx.invoke(ask_cmd, target=target, question=question)
        elif choice == "8":
            target = Prompt.ask("[bold cyan]Enter repository URL or path[/bold cyan]", default=".")
            fmt = Prompt.ask("[bold cyan]Format (markdown/json/csv)[/bold cyan]", default="markdown")
            ctx.invoke(report_cmd, target=target, format=fmt)


@app.command("analyze")
def analyze(
    target: Annotated[str, typer.Argument(help="Local directory path or remote Git repository URL.")],
    ref: Annotated[Optional[str], typer.Option("--ref", "-r", help="Git branch, tag, or commit SHA.")] = None,
    history_depth: Annotated[Optional[int], typer.Option("--history-depth", "-d", help="Max history depth.")] = None,
    profile: Annotated[str, typer.Option("--profile", "-p", help="Analysis profile ('quick' or 'full').")] = "full",
    no_ai: Annotated[bool, typer.Option("--no-ai", help="Disable Gemini AI analysis.")] = False,
    business_context: Annotated[Optional[str], typer.Option("--business-context", "-b", help="Business context description.")] = None,
) -> None:
    """Analyze a Git repository (URL or local path) and persist measurements in SQLite."""
    config = load_config()
    use_ai = not no_ai and (config.ai.enabled or bool(config.ai.api_key))

    try:
        with Progress(
            SpinnerColumn(style="bold cyan"),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task_id = progress.add_task("Initializing analysis...", total=1.0)

            def _update_progress(desc: str, pct: float) -> None:
                progress.update(task_id, description=f"[cyan]{desc}[/cyan]", completed=pct)

            analysis = execute_analysis_pipeline(
                target,
                config,
                requested_ref=ref,
                history_depth=history_depth,
                profile=profile,
                use_ai=use_ai,
                business_context=business_context,
                progress_callback=_update_progress,
            )

        render_analysis_results(console, analysis)
        if analysis.status == "partial":
            raise typer.Exit(7)
        raise typer.Exit(0)

    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"\n[bold red]{SYM_FAIL} Repository analysis failed:[/bold red] {exc}\n")
        raise typer.Exit(3 if "clone" in str(exc).lower() or "git" in str(exc).lower() else 4)


@app.command("metrics")
def metrics_cmd(
    target: Annotated[str, typer.Argument(help="Repository URL or local path.")] = ".",
) -> None:
    """Display software metrics catalogue for a repository."""
    config = load_config()
    db = RepositoryDatabase(config.db_path)
    parsed = parse_and_validate_target(target)
    run_rec = db.get_latest_run_for_repo(parsed.normalized_url)

    if not run_rec:
        console.print(f"[yellow]No existing analysis found for '{target}'. Running analysis first...[/yellow]")
        analysis = execute_analysis_pipeline(target, config, profile="quick")
        metrics = analysis.metrics
    else:
        metrics = db.get_metrics_for_run(run_rec["id"])

    table = Table(
        title=f"Software Metrics Catalogue — {parsed.display_name}",
        title_style="bold cyan",
        border_style="dim",
        expand=True,
    )
    table.add_column("Category", style="bold cyan", width=14)
    table.add_column("Metric Name", style="bold white", width=28)
    table.add_column("Value", justify="right", style="bold green", width=14)
    table.add_column("Unit", style="dim", width=10)
    table.add_column("Scope", style="dim", width=12)
    table.add_column("Explanation", ratio=3)

    for m in metrics:
        if m.scope_type in ("repository", "file") and m.value is not None:
            val_str = f"{m.value:,.2f}" if isinstance(m.value, float) and not m.value.is_integer() else f"{int(m.value):,}"
            table.add_row(
                m.category.upper(),
                m.name,
                val_str,
                m.unit,
                m.scope_type,
                m.explanation or "",
            )

    console.print(table)


@app.command("hotspots")
def hotspots_cmd(
    target: Annotated[str, typer.Argument(help="Repository URL or local path.")] = ".",
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of hotspots to display.")] = 15,
) -> None:
    """Rank complexity and historical churn hotspots."""
    config = load_config()
    analysis = execute_analysis_pipeline(target, config, profile="full")
    console.print(build_hotspots_table(analysis.hotspots, limit=limit))


@app.command("history")
def history_cmd(
    target: Annotated[str, typer.Argument(help="Repository URL or local path.")] = ".",
    depth: Annotated[int, typer.Option("--depth", "-d", help="Max commits to mine.")] = 100,
) -> None:
    """Explore commit history, churn concentration, and contributor stats."""
    config = load_config()
    analysis = execute_analysis_pipeline(target, config, history_depth=depth, profile="quick")
    hist = analysis.history_result

    console.print(f"\n[bold cyan]Git History Summary — {analysis.repository_name}[/bold cyan]")
    console.print(f"Total Commits: [bold]{len(hist.commits):,}[/bold] · Total Churn: [bold]{hist.total_churn:,}[/bold] lines · Gini: [bold]{hist.gini_concentration}[/bold]\n")

    # Top contributors table
    c_table = Table(title="Top Contributors", border_style="dim", expand=True)
    c_table.add_column("Contributor", style="bold white")
    c_table.add_column("Email", style="dim")
    c_table.add_column("Commits", justify="right", style="bold cyan")
    c_table.add_column("First Active", style="dim")
    c_table.add_column("Last Active", style="dim")

    for c in hist.contributors[:10]:
        c_table.add_row(c.display_name, c.email, str(c.commit_count), c.first_commit_date[:10], c.last_commit_date[:10])
    console.print(c_table)


@app.command("security")
def security_cmd(
    target: Annotated[str, typer.Argument(help="Repository URL or local path.")] = ".",
) -> None:
    """Run security analysis, secret detection, and dependency risk audit."""
    config = load_config()
    analysis = execute_analysis_pipeline(target, config, profile="full")
    console.print(build_findings_table(analysis.findings, limit=30))


@app.command("stats")
def stats_cmd(
    target: Annotated[str, typer.Argument(help="Repository URL or local path.")] = ".",
) -> None:
    """Run descriptive statistics, distributions, and empirical correlations."""
    config = load_config()
    analysis = execute_analysis_pipeline(target, config, profile="full")

    # Descriptive table
    t = Table(title="Descriptive Statistics (Distributions)", border_style="dim", expand=True)
    t.add_column("Metric Array", style="bold cyan")
    t.add_column("Count", justify="right")
    t.add_column("Mean", justify="right")
    t.add_column("Median", justify="right")
    t.add_column("Std Dev", justify="right")
    t.add_column("IQR", justify="right")
    t.add_column("Min", justify="right")
    t.add_column("Max", justify="right")
    t.add_column("Skewness", justify="right")

    for k, s in analysis.descriptive_stats.items():
        t.add_row(k, str(s.count), str(s.mean), str(s.median), str(s.std_dev), str(s.iqr), str(s.min), str(s.max), str(s.skewness))
    console.print(t)

    if analysis.correlations:
        console.print("\n[bold cyan]Correlation Analysis:[/bold cyan]")
        for c in analysis.correlations:
            console.print(f"  • [bold white]{c.metric_x} vs {c.metric_y}:[/bold white] {c.interpretation}")


@app.command("compare")
def compare_cmd(
    target: Annotated[str, typer.Argument(help="Repository URL or local path.")] = ".",
    from_ref: Annotated[Optional[str], typer.Option("--from", help="Starting revision/ref.")] = None,
    to_ref: Annotated[Optional[str], typer.Option("--to", help="Target revision/ref.")] = None,
    run_a: Annotated[Optional[str], typer.Option("--run-a", help="First run ID.")] = None,
    run_b: Annotated[Optional[str], typer.Option("--run-b", help="Second run ID.")] = None,
) -> None:
    """Compare two analysis snapshots, metric deltas, and newly introduced hotspots."""
    config = load_config()
    db = RepositoryDatabase(config.db_path)

    if run_a and run_b:
        id_a, id_b = run_a, run_b
    elif from_ref and to_ref:
        console.print(f"[cyan]Analyzing revision {from_ref}...[/cyan]")
        res_a = execute_analysis_pipeline(target, config, requested_ref=from_ref)
        console.print(f"[cyan]Analyzing revision {to_ref}...[/cyan]")
        res_b = execute_analysis_pipeline(target, config, requested_ref=to_ref)
        id_a, id_b = res_a.run_id, res_b.run_id
    else:
        console.print("[red]Please specify either --run-a and --run-b, or --from and --to revisions.[/red]")
        raise typer.Exit(2)

    comp = db.compare_snapshots(id_a, id_b)
    console.print(build_comparison_table(comp["metric_deltas"], limit=20))
    console.print(f"\n[bold]New findings introduced:[/bold] {comp['new_findings_count']} · [bold]Resolved findings:[/bold] {comp['resolved_findings_count']}")


@app.command("ask")
def ask_cmd(
    target: Annotated[str, typer.Argument(help="Repository URL or local path.")] = ".",
    question: Annotated[str, typer.Argument(help="Question to ask Gemini regarding codebase.")] = "",
    mode: Annotated[str, typer.Option("--mode", "-m", help="Analysis mode.")] = "engineering_review",
) -> None:
    """Ask Google Gemini questions grounded in measured repository evidence."""
    config = load_config()
    ai_service = GeminiAIService(config.ai)
    if not ai_service.is_available():
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is not configured.")
        raise typer.Exit(6)

    console.print("[cyan]Gathering repository evidence for Gemini...[/cyan]")
    analysis = execute_analysis_pipeline(target, config, profile="full")

    payload = build_evidence_payload(
        repo_name=analysis.repository_name,
        commit_sha=analysis.commit_sha,
        metrics=analysis.metrics,
        findings=analysis.findings,
        hotspots=analysis.hotspots,
        risk=analysis.risk_assessment,
    )

    with console.status("[bold cyan]Consulting Gemini...[/bold cyan]"):
        res = ai_service.generate_review(payload, mode=mode, user_question=question)

    console.print(f"\n[bold cyan]Gemini Analysis — {analysis.repository_name}[/bold cyan]")
    console.print(f"[bold]Summary:[/bold] {res.executive_summary}\n")

    if res.main_risks:
        console.print("[bold yellow]Key Risks:[/bold yellow]")
        for r in res.main_risks:
            console.print(f"  • {r}")
        console.print()

    if res.recommended_actions:
        console.print("[bold green]Recommended Actions:[/bold green]")
        for a in res.recommended_actions:
            console.print(f"  • {a}")
        console.print()

    console.print(f"[dim]Limitations: {res.confidence_and_limitations}[/dim]\n")


@app.command("report")
def report_cmd(
    target: Annotated[str, typer.Argument(help="Repository target or Run ID.")] = ".",
    format: Annotated[str, typer.Option("--format", "-f", help="Format: markdown, json, csv, terminal.")] = "markdown",
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path.")] = None,
    no_ai: Annotated[bool, typer.Option("--no-ai", help="Omit AI section.")] = False,
) -> None:
    """Generate engineering report for a repository or historical run."""
    config = load_config()
    analysis = execute_analysis_pipeline(target, config, use_ai=not no_ai)

    fmt = format.lower()
    if fmt == "json":
        content = generate_json_report(analysis)
    elif fmt == "csv":
        content = generate_csv_report(analysis)
    elif fmt == "terminal":
        render_analysis_results(console, analysis)
        return
    else:
        content = generate_markdown_report(analysis)

    if output:
        out_p = Path(output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(content, encoding="utf-8")
        console.print(f"[green]{SYM_OK} Report written to {output}[/green]")
    else:
        console.print(content)


@app.command("export")
def export_cmd(
    target: Annotated[str, typer.Argument(help="Repository target or Run ID.")] = ".",
    format: Annotated[str, typer.Option("--format", "-f", help="Export format: json, csv, markdown.")] = "json",
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="Output file path.")] = None,
) -> None:
    """Export machine-readable metrics data."""
    report_cmd(target=target, format=format, output=output)


@app.command("runs")
def runs_cmd(
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max runs to display.")] = 20,
) -> None:
    """List historical analysis runs stored in SQLite."""
    config = load_config()
    db = RepositoryDatabase(config.db_path)
    runs_list = db.list_runs(limit=limit)
    console.print(build_runs_table(runs_list))


@app.command("doctor")
def doctor_cmd() -> None:
    """Verify Git, Python, SQLite database, analyzer tools, and AI configuration."""
    console.print("[bold cyan]Running sem-cli System Diagnostics (Doctor)...[/bold cyan]\n")

    # 1. Git
    if is_git_installed():
        git_ver = get_git_version()
        console.print(f"  {SYM_OK} Git CLI: Installed ({git_ver})")
    else:
        console.print(f"  {SYM_FAIL} Git CLI: Not found in PATH. Git is required for repository operations.")

    # 2. Python
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    console.print(f"  {SYM_OK} Python runtime: {py_ver}")

    # 3. SQLite Database
    config = load_config()
    try:
        db = RepositoryDatabase(config.db_path)
        console.print(f"  {SYM_OK} SQLite Database: Connected ({config.db_path})")
    except Exception as exc:
        console.print(f"  {SYM_FAIL} SQLite Database: Error: {exc}")

    # 4. Analyzers
    try:
        import radon
        console.print(f"  {SYM_OK} Radon analyzer: Installed (v{radon.__version__})")
    except ImportError:
        console.print(f"  {SYM_WARN} Radon analyzer: Not installed. AST fallback will be used.")

    try:
        import lizard
        console.print(f"  {SYM_OK} Lizard analyzer: Installed (multi-language complexity)")
    except ImportError:
        console.print(f"  {SYM_WARN} Lizard analyzer: Not installed.")

    # 5. Gemini AI
    ai_service = GeminiAIService(config.ai)
    if ai_service.is_available():
        console.print(f"  {SYM_OK} Gemini AI: Configured with API key (model: {config.ai.model})")
    else:
        console.print(f"  {SYM_INFO} Gemini AI: Optional (GEMINI_API_KEY is not set). Offline mode active.")

    console.print(f"\n[bold green]{SYM_OK} Doctor checks completed successfully![/bold green]\n")


@app.command("init")
def init_cmd() -> None:
    """Initialize local configuration file ~/.sem-cli/config.toml."""
    config = load_config()
    cfg_file = Path.home() / ".sem-cli" / "config.toml"
    if cfg_file.exists():
        console.print(f"[yellow]Configuration file already exists at {cfg_file}[/yellow]")
    else:
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        default_file = Path("config/default.toml")
        if default_file.exists():
            cfg_file.write_text(default_file.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            cfg_file.write_text("[analysis]\ndefault_profile = 'full'\n", encoding="utf-8")
        console.print(f"[green]{SYM_OK} Initialized configuration file at {cfg_file}[/green]")
