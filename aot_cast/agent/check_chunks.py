import logging
from aot_cast.onto import AgentState
from aot_cast.tool import ToolBox
from aot_cast.onto import Status

logger = logging.getLogger(__name__)


def check_chunks_empty(state: AgentState, tools: ToolBox) -> AgentState:
    logger.debug("Converting documents. NB: processing one file")

    if not all(c.processed for c in state.chunks.values()):
        for _, chunk in state.chunks.items():
            if not chunk.processed:
                state.current_chunk = chunk
                state.node_visits = dict()
                state.status = Status.FAILED
                return state

    state.current_chunk = None
    state.status = Status.SUCCESS
    return state
