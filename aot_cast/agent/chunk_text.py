import logging
from aot_cast.onto import AgentState, Chunk
from aot_cast.tool import ToolBox
from aot_cast.util import render_text_hash


logger = logging.getLogger(__name__)


def chunk_text(state: AgentState, tools: ToolBox) -> AgentState:
    logger.debug("Converting documents. NB: processing one file")
    docs = tools.chunker(state.input_text)

    if state.max_chunks is not None:
        docs = docs[: state.max_chunks]

    for j, doc in enumerate(docs):
        hid = render_text_hash(doc)
        state.chunks[hid] = Chunk(
            text=doc, hash=render_text_hash(doc), parent_doc_hash=state.input_text_hash
        )

    return state
