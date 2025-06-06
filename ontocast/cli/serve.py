import logging.config
import asyncio
import os
from typing import Optional
from robyn import Robyn
from dotenv import load_dotenv
import click
import pathlib
from ontocast.onto import AgentState, RDFGraph
from ontocast.stategraph import create_agent_graph
from langgraph.graph.state import CompiledStateGraph
from robyn import Request, Response, Headers
import logging
from ontocast.cli.util import crawl_directories
from ontocast.toolbox import init_toolbox, ToolBox

logger = logging.getLogger(__name__)


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
                if "text" not in data:
                    return Response(
                        status_code=400, description="'text' field is required in JSON"
                    )
                request.files = {"input.json": data}
            elif content_type.startswith("multipart/form-data"):
                files = request.files
                logger.debug(f"{files.keys()}")
                if not files:
                    return Response(status_code=400, description="No file provided")
            else:
                return Response(status_code=400, description="No data provided")

            state = AgentState(
                files=files, max_visits=max_visits, max_chunks=head_chunks
            )

            async for chunk in workflow.astream(state, stream_mode="values"):
                state = chunk

            result = {
                "facts": state.all_facts,
                "ontology": state.final_ontology,
                "status": state.status,
            }

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
                    state = AgentState(
                        files=files, max_visits=max_visits, max_chunks=head_chunks
                    )

                    async for chunk in workflow.astream(state, stream_mode="values"):
                        state = chunk

                    facts = state.pop("graph_facts", RDFGraph())
                    ontology = state.pop("current_ontology", RDFGraph())

                    onto_file = output_path / f"{file_path.stem}.ontology.ttl"
                    facts_file = output_path / f"{file_path.stem}.facts.ttl"

                    ontology.graph.serialize(destination=onto_file)
                    facts.serialize(destination=facts_file)

                except Exception as e:
                    logger.error(f"Error processing {file_path}: {str(e)}")

        asyncio.run(process_files())
    else:
        app = create_app(tools, head_chunks, max_visits=max_visits)
        logger.info(f"Starting server on port {port}")
        app.start(port=port)


if __name__ == "__main__":
    run()
