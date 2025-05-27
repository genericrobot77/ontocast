import logging.config
import asyncio
import os
from typing import Optional, Dict, Any
from robyn import Robyn
from dotenv import load_dotenv
import click
import pathlib
from io import BytesIO
from aot_cast.onto import AgentState, RDFGraph
from aot_cast.agent import create_agent_graph, init_toolbox
from aot_cast.tools import ToolBox
from langgraph.graph.state import CompiledStateGraph
from robyn import Request, Response, Headers
import logging
from aot_cast.cli.util import crawl_directories
from suthing import FileHandle

logger = logging.getLogger(__name__)


async def process_text(
    workflow: CompiledStateGraph,
    tools: ToolBox,
    input_text: Optional[str] = None,
    chunks: Optional[list[str]] = None,
    head_chunks: Optional[int] = None,
    max_visits: int = 3,
) -> Dict[str, Any]:
    """
    Process text through the agent workflow to extract facts.

    Args:
        input_text: The input text to process
        workflow: The compiled agent workflow
        tools: ToolBox containing all tools
        head_chunks: Optional number of chunks to process
        max_visits: Maximum number of visits allowed per node

    Returns:
        Dictionary containing ontology and facts
    """
    if input_text is not None:
        docs = tools.chunker(input_text)
    elif chunks is not None:
        docs = chunks
    else:
        raise ValueError("either input_text or chunks should be provided")

    logger.debug(f"len docs: {len(docs)}")
    logger.debug(f"docs: {docs}")

    sizes = [len(x) for x in docs]
    logger.debug(f"chunk sizes: {sizes}")

    if head_chunks is not None:
        docs = docs[:head_chunks]

    all_facts = RDFGraph()
    for doc in docs:
        state = AgentState(input_text=doc, max_visits=max_visits)

        # Use astream to get the final state
        final_state = None
        async for chunk in workflow.astream(state, stream_mode="values"):
            final_state = chunk

        if final_state:
            gf = final_state.pop("graph_facts", RDFGraph())
            all_facts += gf

            gf = final_state.pop("current_ontology", RDFGraph())

        if final_state and "current_ontology" in final_state:
            if final_state.current_ontology:
                final_ontology = final_state.current_ontology

        if final_state and hasattr(final_state, "status"):
            final_status = final_state.status

    return {"facts": all_facts, "ontology": final_ontology, "status": final_status}


async def process_file(
    file_path: pathlib.Path,
    workflow: CompiledStateGraph,
    tools: ToolBox,
    head_chunks: Optional[int] = None,
    max_visits: int = 3,
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

    if file_extension in tools.converter.supported_extensions:
        with open(file_path, "rb") as f:
            result = tools.converter(BytesIO(f.read()))
            input_text = result["text"]
            chunks = None
    elif file_extension == ".json":
        jdata = FileHandle.load(file_path, encoding="utf-8")
        input_text = jdata.pop("text", None)
        chunks = jdata.pop("chunks", None)

    return await process_text(
        workflow,
        tools,
        head_chunks=head_chunks,
        input_text=input_text,
        chunks=chunks,
        max_visits=max_visits,
    )


def create_app(tools: ToolBox, head_chunks: Optional[int] = None, max_visits: int = 3):
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

                    if file_extension in tools.converter.supported_extensions:
                        supported_file = BytesIO(file_content)
                        result = tools.converter(supported_file)
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

            result = await process_text(
                workflow,
                tools,
                input_text=input_text,
                head_chunks=head_chunks,
                max_visits=max_visits,
            )

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
@click.option("--logging-level", type=click.STRING)
@click.option("--input-path", type=click.Path(path_type=pathlib.Path), default=None)
@click.option("--output-path", type=click.Path(path_type=pathlib.Path), default=None)
@click.option(
    "--max-visits",
    type=int,
    default=3,
    help="Maximum number of visits allowed per node",
)
def run(
    env_path: pathlib.Path,
    ontology_directory: Optional[pathlib.Path],
    working_directory: pathlib.Path,
    model_name: str,
    temperature: float,
    port: int,
    head_chunks: Optional[int],
    logging_level: Optional[str],
    input_path: Optional[pathlib.Path],
    output_path: Optional[pathlib.Path],
    max_visits: int,
):
    if logging_level is not None:
        try:
            logger_conf = f"logging.{logging_level}.conf"
            logging.config.fileConfig(logger_conf, disable_existing_loggers=False)
            logger.debug("debug is on")
        except Exception as e:
            logger.error(f"could set logging level correctly {e}")

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
        input_path = input_path.expanduser()
        output_path = output_path.expanduser()
        output_path.mkdir(parents=True, exist_ok=True)

        files = sorted(
            crawl_directories(
                input_path,
                suffixes=tuple([".json"] + list(tools.converter.supported_extensions)),
            )
        )

        async def process_files():
            for file_path in files:
                try:
                    result = await process_file(
                        file_path, workflow, tools, head_chunks, max_visits=max_visits
                    )
                    ontology = result["ontology"]
                    facts = result["facts"]

                    onto_file = output_path / f"{file_path.stem}.ontology.ttl"
                    facts_file = output_path / f"{file_path.stem}.facts.ttl"

                    ontology.graph.serialize(destination=onto_file)
                    facts.graph.serialize(destination=facts_file)

                except Exception as e:
                    logger.error(f"Error processing {file_path}: {str(e)}")

        asyncio.run(process_files())
    else:
        app = create_app(tools, head_chunks, max_visits=max_visits)
        logger.info(f"Starting server on port {port}")
        app.start(port=port)


if __name__ == "__main__":
    run()
