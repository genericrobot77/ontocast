import logging
from ontocast.onto import AgentState, Status
from ontocast.toolbox import ToolBox
import pathlib
import json
from io import BytesIO

logger = logging.getLogger(__name__)


def convert_document(state: AgentState, tools: ToolBox) -> AgentState:
    logger.debug("Converting documents. NB: processing only one file")

    state.status = Status.SUCCESS
    files = state.files
    for filename, file_content in files.items():
        file_extension = pathlib.Path(filename).suffix.lower()

        if file_content is None:
            try:
                with open(filename, "rb") as f:
                    file_content = f.read()
                if file_extension == ".json":
                    file_content = json.loads(file_content)
            except Exception as e:
                logger.error(f"Failed to load file {filename}: {str(e)}")
                state.status = Status.FAILED
                return state

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
