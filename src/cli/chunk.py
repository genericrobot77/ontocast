import sys
import pathlib
import click
from src.cli.util import crawl_directories
from src.chunk import split
from suthing import FileHandle
import json

import logging

logger = logging.getLogger(__name__)


def process(fn_json: pathlib.Path, save=False):
    jdata = FileHandle.load(fn_json)
    docs = split(jdata["text"])
    docs_txt = [x.page_content for x in docs]

    sizes = [len(x.page_content) for x in docs]
    logger.debug(f"Chunk size: {sizes}")

    if save:
        jdata["chunks"] = docs_txt
        with open(fn_json, "w", encoding="utf-8") as f:
            json.dump(jdata, f, ensure_ascii=False, indent=4)

    return docs_txt


@click.command()
@click.option("--input-path", type=click.Path(path_type=pathlib.Path), required=True)
@click.option("--output-path", type=click.Path(path_type=pathlib.Path), required=True)
@click.option("--prefix", type=click.STRING, default=None)
def main(input_path, output_path, prefix):
    input_path = input_path.expanduser()
    output_path = output_path.expanduser()

    files = sorted(
        crawl_directories(input_path.expanduser(), suffixes=(".json",), prefix=prefix)
    )

    for f in files:
        process(f)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    main()
