import logging
import sys
from ontocast.onto import AgentState, WorkflowNode, Status
from functools import wraps
from typing import Callable


logger = logging.getLogger(__name__)


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


def count_visits_conditional_success(state: AgentState, current_node) -> AgentState:
    state.node_visits[current_node] += 1
    if state.status == Status.SUCCESS:
        logger.info("Status is SUCCESS, proceeding to next node")
        state.clear_failure()
    elif state.node_visits[current_node] >= state.max_visits:
        logger.error(f"Maximum visits exceeded for {current_node}")
        state.set_failure(current_node, reason="Maximum visits exceeded")
        state.status = Status.SUCCESS
    return state


def wrap_with(func, node_name, post_func) -> tuple[WorkflowNode, Callable]:
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
        state = func(state)
        state = post_func(state, node_name)
        return state

    return node_name, wrapper
