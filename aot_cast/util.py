import logging
import sys
from aot_cast.onto import AgentState, WorkflowNode
from functools import wraps
from typing import Callable
from hashlib import sha256


logger = logging.getLogger(__name__)


def get_text_hash(text: str, digits=12) -> str:
    """Generate a hash from the text."""

    return sha256(text.encode("utf-8")).hexdigest()[:digits]


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


def modifier(state: AgentState, node_name) -> AgentState:
    state.node_visits[node_name] += 1
    return state


def add_counter(func, node_name) -> tuple[WorkflowNode, Callable]:
    """Add a visit counter to a function.

    Args:
        func: The function to wrap
        node_name: The name of the node

    Returns:
        A tuple of (node_name, wrapped_function)
    """

    @wraps(func)
    def wrapper(state: AgentState):
        logger.info(f"Starting to execute {node_name}")
        result = func(state)
        return modifier(result, node_name)

    return node_name, wrapper
