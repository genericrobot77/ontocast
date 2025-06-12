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
    """Update ontology properties using LLM analysis.

    This function uses the LLM tool to analyze and update the properties
    of a given ontology based on its graph content.

    Args:
        o: The ontology to update.
        llm_tool: The LLM tool instance for analysis.
    """
    props = render_ontology_summary(o.graph, llm_tool)
    o.set_properties(**props.model_dump())


def update_ontology_manager(om: OntologyManager, llm_tool: LLMTool):
    """Update properties for all ontologies in the manager.

    This function iterates through all ontologies in the manager and updates
    their properties using the LLM tool.

    Args:
        om: The ontology manager containing ontologies to update.
        llm_tool: The LLM tool instance for analysis.
    """
    for o in om.ontologies:
        update_ontology_properties(o, llm_tool)


class ToolBox:
    """A container class for all tools used in the ontology processing workflow.

    This class initializes and manages various tools needed for document processing,
    ontology management, and LLM interactions.

    Attributes:
        llm: LLM tool for text processing and analysis.
        triple_store_manager: Manager for RDF triple storage.
        ontology_manager: Manager for ontology operations.
        converter: Tool for document conversion.
        chunker: Tool for text chunking.
        aggregator: Tool for aggregating RDF graphs.
    """

    def __init__(self, **kwargs):
        """Initialize the ToolBox with required tools.

        Args:
            working_directory: Path to the working directory.
            ontology_directory: Optional path to ontology directory.
            model_name: Name of the LLM model to use.
            llm_base_url: Optional base URL for LLM API.
            temperature: Temperature setting for LLM.
            llm_provider: Provider for LLM service (default: "openai").
        """
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
    """Initialize the toolbox with ontologies and their properties.

    This function fetches ontologies from the triple store and updates
    their properties using the LLM tool.

    Args:
        toolbox: The ToolBox instance to initialize.
    """
    toolbox.ontology_manager.ontologies = (
        toolbox.triple_store_manager.fetch_ontologies()
    )
    update_ontology_manager(om=toolbox.ontology_manager, llm_tool=toolbox.llm)


def render_ontology_summary(graph: RDFGraph, llm_tool) -> OntologyProperties:
    """Generate a summary of ontology properties using LLM analysis.

    This function uses the LLM tool to analyze an RDF graph and generate
    a structured summary of its properties.

    Args:
        graph: The RDF graph to analyze.
        llm_tool: The LLM tool instance for analysis.

    Returns:
        OntologyProperties: A structured summary of the ontology properties.
    """
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
