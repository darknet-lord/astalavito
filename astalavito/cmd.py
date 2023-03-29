import click


@click.group()
def cli():
    pass


@click.command()
@click.option("--name", required=True, type=str)
@click.option("--url", required=True, type=str)
@click.option("--state", type=click.Choice(['enabled', 'disabled']), default='disabled')
def add_filter(
) -> bool:
    raise NotImplementedError  # TODO


@click.command()
def list_filters() -> None:
    raise NotImplemented  # TODO


def main():
    cli.add_command(add_filter)
    cli.add_command(list_filters)
    cli()


if __name__ == "__main__":
    main()

