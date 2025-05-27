import logging
from aot_cast.onto import AgentState, Status
from aot_cast.tool import ToolBox
import pathlib
from io import BytesIO
from aot_cast.util import render_text_hash

logger = logging.getLogger(__name__)


def convert_document(state: AgentState, tools: ToolBox) -> AgentState:
    logger.debug("Converting documents. NB: processing one file")

    state.status = Status.SUCCESS
    if state.input_text is None:
        files = state.files
        for filename, file_content in files.items():
            file_extension = pathlib.Path(filename).suffix.lower()

            if file_extension in tools.converter.supported_extensions:
                supported_file = BytesIO(file_content)
                result = tools.converter(supported_file)
            elif file_extension == ".json":
                result = file_content
            else:
                state.status = Status.FAILED
                return state

            state.input_text = result["text"]
    state.input_text_hash = render_text_hash(state.input_text)
    return state
