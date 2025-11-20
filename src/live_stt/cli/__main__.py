import typer

app = typer.Typer()


def format_greeting(name: str) -> str:
    return f"Hello, {name}!"


@app.command()
def hello(name: str) -> None:
    """Say hello."""
    typer.echo(format_greeting(name))


if __name__ == "__main__":
    app()
