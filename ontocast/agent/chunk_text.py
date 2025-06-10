import logging
from ontocast.onto import AgentState, Chunk, Status
from ontocast.toolbox import ToolBox
from ontocast.text_utils import render_text_hash


logger = logging.getLogger(__name__)


def chunk_text(state: AgentState, tools: ToolBox) -> AgentState:
    logger.debug("Converting documents. NB: processing one file")
    if state.input_text is not None:
        chunks_txt: list[str] = tools.chunker(state.input_text)

        if state.max_chunks is not None:
            chunks_txt = chunks_txt[: state.max_chunks]

        for chunk_txt in chunks_txt:
            state.chunks.append(
                Chunk(
                    text=chunk_txt,
                    hid=render_text_hash(chunk_txt),
                    doc_iri=state.doc_iri,
                )
            )
        state.status = Status.SUCCESS
    else:
        state.status = Status.FAILED

    return state
