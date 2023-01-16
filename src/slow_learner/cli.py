import json
import pathlib
from slow_learner.type_learner import TypeLearner

import click


@click.group()
def cli():
    pass


@cli.command()
@click.argument("inputs", nargs=-1, required=True, type=click.Path(exists=True, readable=True))
@click.option("--type", default="LearntType")
def learn(inputs: list[str], type: str) -> None:
    tl = TypeLearner(max_literal_type_size=0)
    for inp in inputs:
        try:
            tl.observe(json.loads(pathlib.Path(inp).read_text()))
        except Exception as e:
            click.secho(f"Error parsing data from {inp}: {e!r}", fg="red")
    click.echo(
        tl.generate_type_definition(
            type_name=type,
            doc=f"Source JSON files:\n" + "\n".join(inputs[:10]),
        )
    )
