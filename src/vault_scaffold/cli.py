import typer

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
    typer.echo("vault-scaffold init — not yet implemented")


@app.command()
def doctor() -> None:
    """Diagnose the current vault setup and report health checks."""
    typer.echo("vault-scaffold doctor — not yet implemented")
