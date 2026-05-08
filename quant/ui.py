"""Rich terminal UI for quant lab."""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import sys

console = Console()

def verdict_symbol(decision: str) -> str:
    d = decision.upper()
    if "BUY" in d: return "✅"
    if "SELL" in d: return "❌"
    return "⚠️ "

def verdict_color(decision: str) -> str:
    d = decision.upper()
    if "BUY" in d: return "green"
    if "SELL" in d: return "red"
    return "yellow"

def print_decision(ticker: str, decision: str, confidence: float = 0.0, reasoning: str = ""):
    symbol = verdict_symbol(decision)
    color = verdict_color(decision)
    content = f"[bold {color}]{symbol} {decision}[/bold {color}] (confidence: {confidence:.0%})"
    if reasoning:
        content += f"\n_{reasoning[:200]}_"
    panel = Panel(content, title=f"🎯 {ticker}", border_style=color)
    console.print(panel)

def print_metrics(ticker: str, sharpe: float, max_dd: float, win_rate: float):
    color = "green" if sharpe > 1 else "red" if sharpe < 0 else "yellow"
    table = Table(title=f"📊 {ticker} Backtest Results", border_style=color)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")
    table.add_row("Sharpe Ratio", f"{'[green]' if sharpe > 1 else '[red]' if sharpe < 0 else '[yellow]'}{sharpe:.2f}[/]")
    table.add_row("Max Drawdown", f"{'[red]' if max_dd > 20 else '[yellow]' if max_dd > 10 else '[green]'}{max_dd:.1f}%[/]")
    table.add_row("Win Rate", f"{'[green]' if win_rate > 55 else '[yellow]' if win_rate > 45 else '[red]'}{win_rate:.1f}%[/]")
    console.print(table)

def print_briefing(path: str):
    try:
        with open(path) as f:
            content = f.read()
        console.print(Panel(content, title="📰 Morning Briefing", border_style="blue"))
    except FileNotFoundError:
        console.print(f"[red]Briefing not found: {path}[/red]")

def print_progress(msg: str):
    console.print(f"[dim]{msg}[/dim]")

def print_error(msg: str):
    console.print(f"[red]✗ {msg}[/red]")

def print_success(msg: str):
    console.print(f"[green]✓ {msg}[/green]")

def print_header(text: str):
    console.print(f"\n[bold blue]{text}[/bold blue]\n")
