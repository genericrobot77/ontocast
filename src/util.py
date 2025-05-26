import hashlib
import logging
import sys
from src.onto import AgentState, WorkflowNode
from functools import wraps
from typing import Callable


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
        result = func(state)
        return modifier(result, node_name)

    return node_name, wrapper
