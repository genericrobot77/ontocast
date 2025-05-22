import logging.config
import os
from typing import Optional
from robyn import Robyn
from dotenv import load_dotenv
import click
import pathlib
from io import BytesIO
from src.agent import create_agent_graph, AgentState
from src.tools import (
    FilesystemTripleStoreManager,
    OntologyManager,
    LLMTool,
    Converter,
    ChunkerTool,
)
from src.onto import ToolType, RDFGraph
from langgraph.graph.state import CompiledStateGraph
from src.tools.setup import setup_tools
from robyn import Request, Response, Headers
import logging

logger = logging.getLogger(__name__)


def create_app(**kwargs):
    app = Robyn(__file__)

    workflow: CompiledStateGraph = create_agent_graph(tools)

    @app.post("/process")
    async def process_document_endpoint(request: Request):
        head_chunks = kwargs.pop("head_chunks")
        logger.debug(f"head: {head_chunks}")

        try:
            content_type = request.headers["content-type"]
            logger.debug(f"{content_type}")
            if content_type.startswith("application/json"):
                data = await request.json()
                input_text = data.get("text")
                if not input_text:
                    return Response(
                        status_code=400, description="'text' field is required in JSON"
                    )
            elif content_type.startswith("multipart/form-data"):
                files = request.files
                if not files:
                    return Response(status_code=400, description="No file uploaded")

                logger.debug(f"{files.keys()}")
                for filename, file_content in files.items():
                    file_extension = pathlib.Path(filename).suffix.lower()

                    if file_extension in tools[ToolType.CONVERTER].supported_extensions:
                        supported_file = BytesIO(file_content)
                        result = tools[ToolType.CONVERTER](supported_file)
                        input_text = result["text"]
                    else:
                        try:
                            input_text = file_content.decode("utf-8")
                        except UnicodeDecodeError:
                            return Response(
                                status_code=400,
                                description="Unsupported file type: {file_extension}",
                            )

            logger.debug(f"{filename} : {input_text[:200]}")

            chunker = tools[ToolType.CHUNKER]

            docs = chunker(input_text)

            logger.debug(f"len docs : {len(docs)}")
            logger.debug(f"docs: {docs}")

            docs_txt = [x.page_content for x in docs]
            sizes = [len(x.page_content) for x in docs]
            logger.debug(f"Chunk size: {sizes}")
            facts = RDFGraph()
            if head_chunks is not None:
                docs_txt = docs_txt[:head_chunks]

            for doc_txt in docs_txt:
                state = AgentState(input_text=doc_txt)
                output_state = await workflow.ainvoke(state)
                facts += output_state.graph_facts

            response_body = {
                "ontology": output_state.current_ontology.serialize(),
                "facts": facts(format="turtle"),
            }

            return Response(
                status_code=200,
                headers=Headers({}),
                response_type="json",
                description=response_body,
            )

        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {"error": str(e)}, 500, {}

    return app


@click.command()
@click.option(
    "--env-path", type=click.Path(path_type=pathlib.Path), required=True, default=".env"
)
@click.option(
    "--ontology-directory", type=click.Path(path_type=pathlib.Path), default=None
)
@click.option(
    "--working-directory", type=click.Path(path_type=pathlib.Path), required=True
)
@click.option("--model-name", type=str, default="gpt-4o-mini")
@click.option("--temperature", type=float, default=0.0)
@click.option("--head-chunks", type=int, default=None)
@click.option("--port", type=int, default=8999)
@click.option("--debug", is_flag=True, default=False)
def run(
    env_path: pathlib.Path,
    ontology_directory: Optional[pathlib.Path],
    working_directory: pathlib.Path,
    model_name: str,
    temperature: float,
    port: int,
    head_chunks: Optional[int],
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
    converter_tool: Converter = Converter()
    chunker_tool: ChunkerTool = ChunkerTool()

    global tools
    tools = {
        ToolType.LLM: llm_tool,
        ToolType.TRIPLE_STORE: tsm_tool,
        ToolType.ONTOLOGY_MANAGER: om_tool,
        ToolType.CONVERTER: converter_tool,
        ToolType.CHUNKER: chunker_tool,
    }

    setup_tools(tools)

    working_directory.mkdir(parents=True, exist_ok=True)

    app = create_app(head_chunks=head_chunks)

    app.start(port=port)


if __name__ == "__main__":
    run()
