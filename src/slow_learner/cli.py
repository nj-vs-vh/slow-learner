import json
import pathlib
from typing import Optional

import click
from tqdm import tqdm

from slow_learner.type_learner import TypeLearner


@click.group()
def cli():
    pass


@cli.command()
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, readable=True),
)
@click.option("--output-file", default=None, help="File to write generated type declarations")
@click.option("--type-name", default="LearntType", help="Generated type's name")
@click.option(
    "--spread",
    default=False,
    is_flag=True,
    help="If set, each input file is expected to contain a JSON list, and the type of it's items is learned",
)
@click.option("--max-literal-type-size", default=5, type=int)
def learn(
    inputs: list[str], output_file: Optional[str], type_name: str, max_literal_type_size: int, spread: bool
) -> None:
    output_path = pathlib.Path(output_file or type_name + ".py")
    if output_path.exists():
        click.secho(f"File already exists: {output_path.resolve()}", fg="red")
        return

    input_paths = [pathlib.Path(input_) for input_ in inputs]
    missing_input_paths = [input_path for input_path in input_paths if not input_path.exists()]
    if missing_input_paths:
        click.secho(f"Some input paths are missing: {missing_input_paths}", fg="red")
        return

    tl = TypeLearner(max_literal_type_size=max_literal_type_size)
    with tqdm() as progress_bar:
        for input_path in input_paths:
            try:
                data = json.loads(input_path.read_text())
                if spread:
                    assert isinstance(data, list)
                    items = data
                else:
                    items = [data]
                for idx, item in enumerate(items):
                    try:
                        tl.observe(item)
                    except Exception as e:
                        click.secho(f"Error parsing item #{idx}, ignoring: {e!r}", fg="red")
                    finally:
                        progress_bar.update()
            except Exception as e:
                click.secho(f"Error parsing data from {input_path}, ignoring: {e!r}", fg="red")

    paths_in_doc = 10
    doc = f"Source JSON files:\n" + "\n".join(
        "- " + str(input_path.resolve()) for input_path in input_paths[:paths_in_doc]
    )
    if len(input_paths) > paths_in_doc:
        doc += f"\n- {len(input_paths) - paths_in_doc} more..."
    typedef = tl.generate_type_definition(type_name=type_name, doc=doc)
    output_path.write_text(typedef)
