import logging
from aot_cast.onto import AgentState, Chunk, Status
from aot_cast.tool import ToolBox
from aot_cast.text_utils import render_text_hash


logger = logging.getLogger(__name__)


def chunk_text(state: AgentState, tools: ToolBox) -> AgentState:
    logger.debug("Converting documents. NB: processing one file")
    if state.input_text is not None:
        docs = tools.chunker(state.input_text)

        if state.max_chunks is not None:
            docs = docs[: state.max_chunks]

        for doc in docs:
            hid = render_text_hash(doc)
            state.chunks[hid] = Chunk(
                text=doc,
                hid=hid,
                iri=state.render_chunk_iri(hid),
                parent_doc_hash=state.doc_hid,
            )
        state.status = Status.SUCCESS
    else:
        state.status = Status.FAILED

    return state
