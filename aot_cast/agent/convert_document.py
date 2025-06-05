import logging
from aot_cast.onto import AgentState, Status
from aot_cast.toolbox import ToolBox
import pathlib
from io import BytesIO

logger = logging.getLogger(__name__)


def convert_document(state: AgentState, tools: ToolBox) -> AgentState:
    logger.debug("Converting documents. NB: processing one file")

    state.status = Status.SUCCESS
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

        state.set_text(result["text"])
    return state
