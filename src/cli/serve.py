import logging
import os
import tempfile
from robyn import Robyn
from dotenv import load_dotenv
import click
import pathlib
from src.agent import create_agent_graph, AgentState
from src.tools import FilesystemTripleStoreManager, OntologyManager, LLMTool, Tool
from src.onto import ToolType
from langgraph.graph.state import CompiledStateGraph
from src.tools.setup import setup_tools
from src.cli.util import pdf2markdown
from docling.document_converter import DocumentConverter


app = Robyn(__file__)

workflow: CompiledStateGraph
converter: DocumentConverter

logger = logging.getLogger(__name__)


@app.post("/process")
async def process_document_endpoint(request):
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            data = await request.json()
            input_text = data.get("text")
            if not input_text:
                return {"error": "'text' field is required in JSON"}, 400
        else:
            data = await request.form()
            file = data.get("file")

            if not file:
                return {"error": "file is required"}, 400

            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                if file.filename.endswith(".pdf"):
                    json_data = pdf2markdown(temp_file_path, converter=converter)
                    input_text = json_data["text"]
                else:
                    input_text = content.decode("utf-8")
            finally:
                os.unlink(temp_file_path)

        state = AgentState(input_text=input_text)
        output_state = await workflow.ainvoke(state)
        response = {
            "ontology": output_state.current_ontology.serialize(),
            "facts": output_state.graph_facts.serialize(format="turtle"),
        }

        return response, 200

    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        return {"error": str(e)}, 500


@click.command()
@click.option(
    "--env-path", type=click.Path(path_type=pathlib.Path), required=True, default=".env"
)
@click.option(
    "--ontology-directory", type=click.Path(path_type=pathlib.Path), required=True
)
@click.option(
    "--working-directory", type=click.Path(path_type=pathlib.Path), required=True
)
@click.option("--model-name", type=str, default="gpt-4o-mini")
@click.option("--temperature", type=float, default=0.0)
@click.option("--port", type=int, default=8999)
@click.option("--debug", is_flag=True, default=False)
def run(
    env_path: pathlib.Path,
    ontology_directory: pathlib.Path,
    working_directory: pathlib.Path,
    model_name: str,
    temperature: float,
    port: int,
    debug: bool,
):
    if debug:
        logger_conf = "logging.debug.conf"
        logging.config.fileConfig(logger_conf, disable_existing_loggers=False)
        logger.debug("debug is on")

    _ = load_dotenv(dotenv_path=env_path.expanduser())

    if "OPENAI_API_KEY" not in os.environ:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    llm_tool: LLMTool = LLMTool.create(model=model_name, temperature=temperature)

    tsm_tool: FilesystemTripleStoreManager = FilesystemTripleStoreManager(
        working_directory=working_directory, ontology_path=ontology_directory
    )
    om_tool: OntologyManager = OntologyManager()

    tools: dict[ToolType, Tool] = {
        ToolType.LLM: llm_tool,
        ToolType.TRIPLE_STORE: tsm_tool,
        ToolType.ONTOLOGY_MANAGER: om_tool,
    }

    setup_tools(tools)

    working_directory.mkdir(parents=True, exist_ok=True)

    global workflow
    workflow = create_agent_graph(tools)

    global converter
    converter = DocumentConverter()

    app.start(port=port)


if __name__ == "__main__":
    run()
