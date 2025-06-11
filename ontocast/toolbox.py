import pathlib
from typing import Optional

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from ontocast.onto import Ontology, OntologyProperties, RDFGraph
from ontocast.tool import (
    ChunkerTool,
    ConverterTool,
    FilesystemTripleStoreManager,
    TripleStoreManager,
)
from ontocast.tool.aggregate import ChunkRDFGraphAggregator
from ontocast.tool.llm import LLMTool
from ontocast.tool.ontology_manager import OntologyManager


def update_ontology_properties(o: Ontology, llm_tool: LLMTool):
    props = render_ontology_summary(o.graph, llm_tool)
    o.set_properties(**props.model_dump())


def update_ontology_manager(om: OntologyManager, llm_tool: LLMTool):
    for o in om.ontologies:
        update_ontology_properties(o, llm_tool)


class ToolBox:
    def __init__(self, **kwargs):
        working_directory: pathlib.Path = kwargs.pop("working_directory")
        ontology_directory: Optional[pathlib.Path] = kwargs.pop("ontology_directory")
        model_name: str = kwargs.pop("model_name")
        llm_base_url: Optional[str] = kwargs.pop("llm_base_url")
        temperature: float = kwargs.pop("temperature")
        llm_provider: str = kwargs.pop("llm_provider", "openai")

        self.llm: LLMTool = LLMTool.create(
            provider=llm_provider,
            model=model_name,
            temperature=temperature,
            base_url=llm_base_url,
        )
        self.triple_store_manager: TripleStoreManager = FilesystemTripleStoreManager(
            working_directory=working_directory, ontology_path=ontology_directory
        )
        self.ontology_manager: OntologyManager = OntologyManager()
        self.converter: ConverterTool = ConverterTool()
        self.chunker: ChunkerTool = ChunkerTool()
        self.aggregator: ChunkRDFGraphAggregator = ChunkRDFGraphAggregator()


def init_toolbox(toolbox: ToolBox):
    toolbox.ontology_manager.ontologies = (
        toolbox.triple_store_manager.fetch_ontologies()
    )
    update_ontology_manager(om=toolbox.ontology_manager, llm_tool=toolbox.llm)


def render_ontology_summary(graph: RDFGraph, llm_tool) -> OntologyProperties:
    ontology_str = graph.serialize(format="turtle")

    # Define the output parser
    parser = PydanticOutputParser(pydantic_object=OntologyProperties)

    # Create the prompt template with format instructions
    prompt = PromptTemplate(
        template=(
            "Below is an ontology in Turtle format:\n\n"
            "```ttl\n{ontology_str}\n```\n\n"
            "{format_instructions}"
        ),
        input_variables=["ontology_str"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    response = llm_tool(prompt.format_prompt(ontology_str=ontology_str))

    return parser.parse(response.content)
