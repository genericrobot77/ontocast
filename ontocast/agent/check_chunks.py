import logging
from collections import defaultdict

from ontocast.onto import AgentState, Status

logger = logging.getLogger(__name__)


def check_chunks_empty(state: AgentState) -> AgentState:
    logger.info(
        f"Chunks (rem): {len(state.chunks)}, "
        f"chunks proc: {len(state.chunks_processed)}. "
        f"Setting up current chunk"
    )

    if state.current_chunk is not None:
        state.chunks_processed.append(state.current_chunk)

    if state.chunks:
        state.current_chunk = state.chunks.pop(0)
        state.node_visits = defaultdict(int)
        state.status = Status.FAILED
        logger.info(
            "Chunk available, setting status to FAILED"
            " and proceeding to SELECT_ONTOLOGY"
        )
    else:
        state.current_chunk = None
        state.status = Status.SUCCESS
        logger.info(
            "No more chunks, setting status to SUCCESS "
            "and proceeding to AGGREGATE_FACTS"
        )

    return state
