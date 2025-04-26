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

app = Robyn(__file__)

workflow: CompiledStateGraph


@app.post("/process")
async def process_document_endpoint(request):
    try:
        data = await request.form()
        file = data.get("file")

        if not file:
            return {"error": "file is required"}, 400

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            state = AgentState(
                input_text=content.decode("utf-8"),
            )

            state = AgentState(ontology_path="data/ontologies")
            output = await workflow.ainvoke(state)
            workflow.run(state)

            return output.dict(), 200
        finally:
            os.unlink(temp_file_path)

    except Exception as e:
        return {"error": str(e)}, 500


@click.command()
@click.option("--env-path", type=click.Path(path_type=pathlib.Path), required=True)
@click.option(
    "--ontology-directory", type=click.Path(path_type=pathlib.Path), required=True
)
@click.option(
    "--working-directory", type=click.Path(path_type=pathlib.Path), required=True
)
@click.option("--model-name", type=str, default="gpt-4o-mini")
@click.option("--temperature", type=float, default=0.0)
@click.option("--port", type=int, default=8999)
def run(
    env_path: pathlib.Path,
    ontology_directory: pathlib.Path,
    working_directory: pathlib.Path,
    model_name: str,
    temperature: float,
    port: int,
):
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

    app.start(port=port)


if __name__ == "__main__":
    run()
