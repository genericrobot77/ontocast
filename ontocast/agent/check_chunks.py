import logging
from ontocast.onto import AgentState
from ontocast.onto import Status
from collections import defaultdict

logger = logging.getLogger(__name__)


def check_chunks_empty(state: AgentState) -> AgentState:
    logger.debug(f"Setting current if chunks are available: {len(state.chunks)}")

    if state.chunks:
        state.current_chunk = state.chunks.pop(0)
        state.node_visits = defaultdict()
        state.status = Status.FAILED
        return state

    state.current_chunk = None
    state.status = Status.SUCCESS
    return state
