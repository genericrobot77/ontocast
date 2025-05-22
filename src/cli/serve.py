import logging.config
import asyncio
import os
from typing import Optional, Dict, Any
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
from src.cli.util import crawl_directories
import json

logger = logging.getLogger(__name__)


async def process_text_to_facts(
    input_text: str,
    workflow: CompiledStateGraph,
    tools: Dict[ToolType, Any],
    head_chunks: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process text through the agent workflow to extract facts.

    Args:
        input_text: The input text to process
        workflow: The compiled agent workflow
        tools: Dictionary of tools to use
        head_chunks: Optional number of chunks to process

    Returns:
        Dictionary containing ontology and facts
    """
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

    return {
        "ontology": output_state.current_ontology.serialize(),
        "facts": facts(format="turtle"),
    }


async def process_file(
    file_path: pathlib.Path,
    workflow: CompiledStateGraph,
    tools: Dict[ToolType, Any],
    head_chunks: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process a file through the agent workflow.

    Args:
        file_path: Path to the file to process
        workflow: The compiled agent workflow
        tools: Dictionary of tools to use
        head_chunks: Optional number of chunks to process

    Returns:
        Dictionary containing ontology and facts
    """
    file_extension = file_path.suffix.lower()

    if file_extension in tools[ToolType.CONVERTER].supported_extensions:
        with open(file_path, "rb") as f:
            result = tools[ToolType.CONVERTER](BytesIO(f.read()))
            input_text = result["text"]
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            input_text = f.read()

    return await process_text_to_facts(input_text, workflow, tools, head_chunks)


def create_app(tools: Dict[ToolType, Any], head_chunks: Optional[int] = None):
    app = Robyn(__file__)
    workflow: CompiledStateGraph = create_agent_graph(tools)

    @app.post("/process")
    async def process_document_endpoint(request: Request):
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
                result = await process_text_to_facts(
                    input_text, workflow, tools, head_chunks
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
                                description=f"Unsupported file type: {file_extension}",
                            )

                    result = await process_text_to_facts(
                        input_text, workflow, tools, head_chunks
                    )
                    break  # Process only the first file

            return Response(
                status_code=200,
                headers=Headers({}),
                response_type="json",
                description=result,
            )

        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {"error": str(e)}, 500, {}

    return app


async def create_tools(
    working_directory: pathlib.Path,
    ontology_directory: Optional[pathlib.Path],
    model_name: str,
    temperature: float,
) -> Dict[ToolType, Any]:
    """Create and setup tools for processing."""
    llm_tool: LLMTool = await LLMTool.acreate(model=model_name, temperature=temperature)

    tsm_tool: FilesystemTripleStoreManager = FilesystemTripleStoreManager(
        working_directory=working_directory, ontology_path=ontology_directory
    )
    om_tool: OntologyManager = OntologyManager()
    converter_tool: Converter = Converter()
    chunker_tool: ChunkerTool = ChunkerTool()

    tools = {
        ToolType.LLM: llm_tool,
        ToolType.TRIPLE_STORE: tsm_tool,
        ToolType.ONTOLOGY_MANAGER: om_tool,
        ToolType.CONVERTER: converter_tool,
        ToolType.CHUNKER: chunker_tool,
    }

    setup_tools(tools)
    return tools


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
@click.option("--input-path", type=click.Path(path_type=pathlib.Path), default=None)
@click.option("--output-path", type=click.Path(path_type=pathlib.Path), default=None)
def run(
    env_path: pathlib.Path,
    ontology_directory: Optional[pathlib.Path],
    working_directory: pathlib.Path,
    model_name: str,
    temperature: float,
    port: int,
    head_chunks: Optional[int],
    debug: bool,
    input_path: Optional[pathlib.Path],
    output_path: Optional[pathlib.Path],
):
    if debug:
        logger_conf = "logging.debug.conf"
        logging.config.fileConfig(logger_conf, disable_existing_loggers=False)
        logger.debug("debug is on")

    _ = load_dotenv(dotenv_path=env_path.expanduser())

    if "OPENAI_API_KEY" not in os.environ:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    working_directory.mkdir(parents=True, exist_ok=True)

    # Create tools and workflow
    tools = asyncio.run(
        create_tools(working_directory, ontology_directory, model_name, temperature)
    )
    workflow: CompiledStateGraph = create_agent_graph(tools)

    if input_path and output_path:
        # Process files in directory
        input_path = input_path.expanduser()
        output_path = output_path.expanduser()
        output_path.mkdir(parents=True, exist_ok=True)

        files = sorted(
            crawl_directories(
                input_path, suffixes=(".txt", ".md", ".json", ".pdf", ".docx")
            )
        )

        async def process_files():
            for file_path in files:
                try:
                    result = await process_file(file_path, workflow, tools, head_chunks)
                    output_file = output_path / f"{file_path.stem}_facts.json"

                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=4)

                    logger.info(f"Processed {file_path} -> {output_file}")
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {str(e)}")

        asyncio.run(process_files())
    else:
        # Run as server
        app = create_app(tools, head_chunks)
        logger.info(f"Starting server on port {port}")
        app.start(port=port)


if __name__ == "__main__":
    run()
