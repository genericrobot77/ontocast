from aot_cast.agent import load_document
import click
import pathlib


@click.command()
@click.option("--doc-path", type=click.Path(path_type=pathlib.Path), required=True)
def run(doc_path: pathlib.Path):
    text = load_document(doc_path)
    print(text)


if __name__ == "__main__":
    run()
