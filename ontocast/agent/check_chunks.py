import logging
from ontocast.onto import AgentState
from ontocast.onto import Status
from collections import defaultdict

logger = logging.getLogger(__name__)


def check_chunks_empty(state: AgentState) -> AgentState:
    logger.info(f"Chunks remaining: {len(state.chunks)}, setting up current chunk")

    if state.chunks:
        state.current_chunk = state.chunks.pop(0)
        state.node_visits = defaultdict(int)
        state.status = Status.FAILED
        logger.info(
            "Chunk available, setting status to FAILED and proceeding to SELECT_ONTOLOGY"
        )
    else:
        state.current_chunk = None
        state.status = Status.SUCCESS
        logger.info(
            "No more chunks, setting status to SUCCESS and proceeding to AGGREGATE_FACTS"
        )

    return state
