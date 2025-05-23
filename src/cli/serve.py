import logging.config
import asyncio
import os
from typing import Optional, Dict, Any
from robyn import Robyn
from dotenv import load_dotenv
import click
import pathlib
from io import BytesIO
from src.agent import create_agent_graph, AgentState, init_toolbox
from src.tools import ToolBox
from src.onto import RDFGraph
from langgraph.graph.state import CompiledStateGraph
from robyn import Request, Response, Headers
import logging
from src.cli.util import crawl_directories
import json

logger = logging.getLogger(__name__)


async def process_text(
    input_text: str,
    workflow: CompiledStateGraph,
    tools: ToolBox,
    head_chunks: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process text through the agent workflow to extract facts.

    Args:
        input_text: The input text to process
        workflow: The compiled agent workflow
        tools: ToolBox containing all tools
        head_chunks: Optional number of chunks to process

    Returns:
        Dictionary containing ontology and facts
    """
    docs = tools.chunker_tool(input_text)

    logger.debug(f"len docs : {len(docs)}")
    logger.debug(f"docs: {docs}")

    sizes = [len(x) for x in docs]
    logger.debug(f"chunk sizes: {sizes}")

    facts = RDFGraph()
    if head_chunks is not None:
        docs = docs[:head_chunks]

    for doc in docs:
        state = AgentState(input_text=doc)
        output_state: AgentState = await workflow.ainvoke(state)
        facts += output_state.graph_facts

    return {
        "ontology": output_state.current_ontology.graph.serialize(format="turtle"),
        "facts": facts.serialize(format="turtle"),
    }


async def process_file(
    file_path: pathlib.Path,
    workflow: CompiledStateGraph,
    tools: ToolBox,
    head_chunks: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process a file through the agent workflow.

    Args:
        file_path: Path to the file to process
        workflow: The compiled agent workflow
        tools: ToolBox containing all tools
        head_chunks: Optional number of chunks to process

    Returns:
        Dictionary containing ontology and facts
    """
    file_extension = file_path.suffix.lower()

    if file_extension in tools.converter_tool.supported_extensions:
        with open(file_path, "rb") as f:
            result = tools.converter_tool(BytesIO(f.read()))
            input_text = result["text"]
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            input_text = f.read()

    return await process_text(input_text, workflow, tools, head_chunks)


def create_app(tools: ToolBox, head_chunks: Optional[int] = None):
    app = Robyn(__file__)
    workflow: CompiledStateGraph = create_agent_graph(tools)

    @app.post("/process")
    async def process(request: Request):
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
                    return Response(status_code=400, description="No file provided")

                logger.debug(f"{files.keys()}")
                for filename, file_content in files.items():
                    file_extension = pathlib.Path(filename).suffix.lower()

                    if file_extension in tools.converter_tool.supported_extensions:
                        supported_file = BytesIO(file_content)
                        result = tools.converter_tool(supported_file)
                        input_text = result["text"]
                    else:
                        try:
                            input_text = file_content.decode("utf-8")
                        except UnicodeDecodeError:
                            return Response(
                                status_code=400,
                                description=f"Unsupported file type: {file_extension}",
                            )
                    # process only one file
                    break

            result = await process_text(input_text, workflow, tools, head_chunks)

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

    tools: ToolBox = ToolBox(
        working_directory=working_directory,
        ontology_directory=ontology_directory,
        model_name=model_name,
        temperature=temperature,
    )
    init_toolbox(tools)

    workflow: CompiledStateGraph = create_agent_graph(tools)

    if input_path and output_path:
        # Process files in directory
        input_path = input_path.expanduser()
        output_path = output_path.expanduser()
        output_path.mkdir(parents=True, exist_ok=True)

        files = sorted(
            crawl_directories(
                input_path,
                suffixes=(".txt", ".md", ".json", ".pdf"),
                # suffixes=(".txt", ".md", ".json", ".pdf", ".docx")
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
