import logging
from ontocast.onto import AgentState, Chunk, Status
from ontocast.toolbox import ToolBox
from ontocast.text_utils import render_text_hash


logger = logging.getLogger(__name__)


def chunk_text(state: AgentState, tools: ToolBox) -> AgentState:
    logger.debug("Converting documents. NB: processing one file")
    if state.input_text is not None:
        docs = tools.chunker(state.input_text)

        if state.max_chunks is not None:
            docs = docs[: state.max_chunks]

        for doc in docs:
            state.chunks.append(
                Chunk(text=doc, hid=render_text_hash(doc), doc_iri=state.doc_iri)
            )
        state.status = Status.SUCCESS
    else:
        state.status = Status.FAILED

    return state
