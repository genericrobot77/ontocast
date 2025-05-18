import hashlib
import logging
import sys


def get_document_hash(text: str) -> str:
    """Generate a hash from the input text."""
    return hashlib.md5(text.encode()).hexdigest()[:8]


def setup_logging(debug: bool = False) -> None:
    """
    Set up logging configuration for the project.

    Args:
        debug: If True, sets logging level to DEBUG, otherwise INFO
    """
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
