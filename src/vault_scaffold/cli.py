import typer

from .commands import doctor as doctor_cmd
from .commands import init as init_cmd
from .commands import status as status_cmd
from .commands import update as update_cmd

app = typer.Typer(
    name="vault-scaffold",
    help="CLI installer for claude-vault-scaffold.",
    no_args_is_help=True,
)


@app.command()
def init(
    path: str = typer.Argument(".", help="Target vault directory (default: current directory)"),
) -> None:
    """Idempotently set up a new or existing vault with claude-vault-scaffold."""
    init_cmd.run(path)


@app.command()
def doctor(
    path: str = typer.Argument(".", help="Target vault directory (default: current directory)"),
) -> None:
    """Diagnose the current vault setup and report health checks."""
    doctor_cmd.run_from_cli(path)


@app.command()
def status(
    path: str = typer.Argument(".", help="Target vault directory (default: current directory)"),
) -> None:
    """Show installed vs. available scaffold version."""
    status_cmd.run(path)


@app.command()
def update(
    path: str = typer.Argument(".", help="Target vault directory (default: current directory)"),
) -> None:
    """Update an existing vault to the current scaffold version."""
    update_cmd.run(path)
