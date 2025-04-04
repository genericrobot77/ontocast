import sys
import pathlib
import click
from src.cli.util import crawl_directories, pdf2markdown
import json

import logging

logger = logging.getLogger(__name__)


def process_batch(output_path, f: pathlib.Path):
    fn_json = (output_path / f.name).with_suffix(".json")
    jdata = pdf2markdown(f)
    with open(fn_json, "w", encoding="utf-8") as f:
        json.dump(jdata, f, ensure_ascii=False, indent=4)


@click.command()
@click.option("--input-path", type=click.Path(path_type=pathlib.Path), required=True)
@click.option("--output-path", type=click.Path(path_type=pathlib.Path), required=True)
def main(input_path, output_path):
    input_path = input_path.expanduser()
    output_path = output_path.expanduser()

    files = sorted(crawl_directories(input_path.expanduser(), suffixes=(".pdf",)))
    files = files

    for f in files:
        process_batch(output_path, f)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    main()
