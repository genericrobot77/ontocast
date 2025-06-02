from pydantic import BaseModel, Field, ConfigDict
from rdflib import Graph, Namespace
from typing import Optional, Any
import logging
import pathlib
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema
from collections import defaultdict
import os

import re
from enum import StrEnum


logger = logging.getLogger(__name__)


ONTOLOGY_VOID_ID = "__void_ontology_name"
ONTOLOGY_VOID_IRI = "NULL"

DEFAULT_DOMAIN = "https://example.com"


def iri2namespace(iri, ontology=False):
    return f"{iri}#" if ontology else f"{iri}/"


class Status(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    COUNTS_EXCEEDED = "counts exceeded"


class ToolType(StrEnum):
    LLM = "llm"
    TRIPLE_STORE = "triple store manager"
    ONTOLOGY_MANAGER = "ontology manager"
    CONVERTER = "document converter"
    CHUNKER = "document chunker"


class FailureStages(StrEnum):
    FAILED_AT_ONTOLOGY_CRITIQUE = (
        "The produced ontology did not pass the critique stage."
    )
    FAILED_AT_FACTS_CRITIQUE = (
        "The produced graph of facts did not pass the critique stage."
    )
    FAILED_AT_PARSE_TEXT_TO_ONTOLOGY_TRIPLES = (
        "Failed to parse the text into ontology triples."
    )
    FAILED_AT_PARSE_TEXT_TO_FACTS_TRIPLES = (
        "Failed to parse the text into facts triples."
    )
    FAILED_AT_SUBLIMATE_ONTOLOGY = "The produced semantic could not be validated or separated into ontology and facts (technical issue)."


COMMON_PREFIXES = {
    "xsd": "<http://www.w3.org/2001/XMLSchema#>",
    "rdf": "<http://www.w3.org/1999/02/22-rdf-syntax-ns#>",
    "rdfs": "<http://www.w3.org/2000/01/rdf-schema#>",
    "owl": "<http://www.w3.org/2002/07/owl#>",
    "skos": "<http://www.w3.org/2004/02/skos/core#>",
    "foaf": "<http://xmlns.com/foaf/0.1/>",
    "schema": "<http://schema.org/>",
    "ex": "<http://example.org/>",
}

PROV = Namespace("http://www.w3.org/ns/prov#")
SCHEMA = Namespace("http://schema.org/")

PREFIX_PATTERN = re.compile(r"@prefix\s+(\w+):\s+<[^>]+>\s+\.")


class BasePydanticModel(BaseModel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def serialize(self, file_path: str | pathlib.Path) -> None:
        """
        Serialize the state to a JSON file.

        Args:
            file_path (Union[str, pathlib.Path]): Path to save the JSON file
        """
        state_json = self.model_dump_json(indent=4)
        if isinstance(file_path, str):
            file_path = pathlib.Path(file_path)
        file_path.write_text(state_json)

    @classmethod
    def load(cls, file_path: str | pathlib.Path):
        """
        Load state from a JSON file.

        Args:
            file_path (Union[str, pathlib.Path]): Path to the JSON file

        Returns:
            AgentState: The loaded state
        """
        if isinstance(file_path, str):
            file_path = pathlib.Path(file_path)
        state_json = file_path.read_text()
        return cls.model_validate_json(state_json)


class RDFGraph(Graph):
    """Subclass to attach schema support for Pydantic."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, handler: GetCoreSchemaHandler):
        return core_schema.union_schema(
            [
                # Allow direct Graph instances
                core_schema.is_instance_schema(cls),
                # Allow string conversion
                core_schema.chain_schema(
                    [
                        core_schema.str_schema(),
                        core_schema.no_info_plain_validator_function(
                            cls._from_turtle_str
                        ),
                    ]
                ),
            ],
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._to_turtle_str,
                info_arg=False,
                return_schema=core_schema.str_schema(),
            ),
        )

    @staticmethod
    def _ensure_prefixes(turtle_str: str) -> str:
        declared_prefixes = set(
            match.group(1) for match in PREFIX_PATTERN.finditer(turtle_str)
        )

        missing = {
            prefix: uri
            for prefix, uri in COMMON_PREFIXES.items()
            if prefix not in declared_prefixes
        }

        if not missing:
            return turtle_str

        prefix_block = (
            "\n".join(f"@prefix {prefix}: {uri} ." for prefix, uri in missing.items())
            + "\n\n"
        )

        return prefix_block + turtle_str

    @classmethod
    def _from_turtle_str(cls, turtle_str: str) -> "RDFGraph":
        turtle_str = bytes(turtle_str, "utf-8").decode("unicode_escape")
        patched_turtle = cls._ensure_prefixes(turtle_str)
        g = cls()
        g.parse(data=patched_turtle, format="turtle")
        return g

    @staticmethod
    def _to_turtle_str(g: Any) -> str:
        return g.serialize(format="turtle")

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        return instance


class OntologySelectorReport(BasePydanticModel):
    short_name: Optional[str] = Field(
        description="A short name (identifier) for the ontology that could be used to represent the domain of the document, None if no ontology is suitable"
    )
    present: bool = Field(
        description="Whether an ontology that could represent the domain of the document is present in the list of ontologies"
    )


class SemanticTriplesFactsReport(BaseModel):
    semantic_graph: RDFGraph = Field(
        default_factory=RDFGraph,
        description="Semantic triples (facts) representing the document in turtle (ttl) format.",
    )
    ontology_relevance_score: Optional[float] = Field(
        description="Score 0-100 for how relevant the ontology is to the document. 0 is the worst, 100 is the best."
    )
    triples_generation_score: Optional[float] = Field(
        description="Score 0-100 for how well the facts extraction / triples generation was performed. 0 is the worst, 100 is the best."
    )


class OntologyUpdateCritiqueReport(BaseModel):
    ontology_update_success: bool = Field(
        description="True if the ontology update was performed successfully, False otherwise."
    )
    ontology_update_score: float = Field(
        description="Score 0-100 for how well the update improves the original domain ontology of the document. 0 is the worst, 100 is the best."
    )

    ontology_update_critique_comment: Optional[str] = Field(
        description="A very concrete explanation of why the ontology update is not satisfactory. The explanation should be very specific and detailed."
    )


class KGCritiqueReport(BaseModel):
    facts_graph_derivation_success: bool = Field(
        description="True if the facts graph derivation was performed successfully, False otherwise."
    )
    facts_graph_derivation_score: float = Field(
        description="Score 0-100 for how well the triples of facts represent the original document. 0 is the worst, 100 is the best."
    )

    facts_graph_derivation_critique_comment: Optional[str] = Field(
        description="A very concrete explanation of why the semantic graph of facts derivation is not satisfactory. The explanation should be very specific and detailed."
    )


class OntologyProperties(BaseModel):
    short_name: Optional[str] = Field(
        default=None,
        description="A short name (identifier) for the ontology. It should be an abbreviation. Must be provided.",
    )
    title: Optional[str] = Field(
        default=None, description="Ontology title. Must be provided."
    )
    description: Optional[str] = Field(
        default=None,
        description="A concise description (3-4 sentences) of the ontology (domain, purpose, applicability, etc.)",
    )
    version: Optional[str] = Field(
        description="Version of the ontology",
        default="0.0.0",
    )
    iri: Optional[str] = Field(
        default=None,
        description="Ontology IRI (Internationalized Resource Identifier)",
    )

    @property
    def namespace(self):
        return iri2namespace(self.iri, ontology=True)


class Ontology(OntologyProperties):
    """
    A Pydantic model representing an ontology with its RDF graph and description.

    Attributes:
        graph (Graph): The RDF graph containing the ontology data
        description (str): A human-readable description of the ontology
        version (Optional[str]): Optional version information
    """

    graph: RDFGraph = Field(
        default_factory=RDFGraph,
        description="Semantic triples (abstract entities/relations) that define the ontology in turtle (ttl) format as a string.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __iadd__(self, other: "Ontology") -> "Ontology":
        """
        In-place addition operator for Ontology instances.
        Merges the RDF graphs and takes properties from the right-hand operand.

        Args:
            other (Ontology): The ontology to add to this one

        Returns:
            Ontology: self after modification
        """

        self.graph += other.graph

        # Take properties from the right-hand operand
        self.title = other.title
        self.short_name = other.short_name
        self.description = other.description
        self.iri = other.iri
        self.version = other.version

        return self

    @classmethod
    def from_file(cls, file_path: pathlib.Path, format: str = "turtle", **kwargs):
        """
        Create an Ontology instance by loading a graph from a file.

        Args:
            file_path (str): Path to the ontology file
            format (str): Format of the input file (default: "turtle")
            **kwargs: Additional arguments to pass to the constructor

        Returns:
            Ontology: A new Ontology instance
        """
        graph: RDFGraph = RDFGraph()
        graph.parse(file_path, format=format)
        return cls(graph=graph, **kwargs)

    def set_properties(self, **kwargs):
        self.__dict__.update(**kwargs)

    def describe(self) -> str:
        return (
            f"Ontology name: {self.short_name}\n"
            f"Description: {self.description}\n"
            f"Ontology IRI: {self.iri}\n"
        )

    @property
    def iri_id(self):
        oid = self.iri.split("/")[-1].split("#")[0]
        if not oid:
            oid = "default"
        return oid


class WorkflowNode(StrEnum):
    CONVERT_TO_MD = "Convert to Markdown"
    CHUNK = "Chunk Text"

    SELECT_ONTOLOGY = "Select Ontology"
    TEXT_TO_ONTOLOGY = "Text to Ontology"
    TEXT_TO_FACTS = "Text to Facts"
    SUBLIMATE_ONTOLOGY = "Sublimate Ontology"
    CRITICISE_ONTOLOGY = "Criticise Ontology"
    CRITICISE_FACTS = "Criticise Facts"

    CHUNKS_EMPTY = "Chunks Empty Check"

    SAVE_KG = "Save KG"


class Chunk(BaseModel):
    text: str = Field(description="Text of the chunk")

    hid: str = Field(description="An almost unique (hash) id for the chunk")

    doc_iri: str = Field(description="IRI of parent doc")

    graph: Optional[RDFGraph] = Field(
        description="RDF triples representing the facts from the current document",
        default_factory=RDFGraph,
    )

    processed: bool = Field(
        default=False, description="Whether chunk has been processed"
    )

    @property
    def iri(self):
        return f"{self.doc_iri}/chunk/{self.hid}"

    @property
    def namespace(self):
        return iri2namespace(self.iri, ontology=False)


class AgentState(BasePydanticModel):
    """State for the ontology-based knowledge graph agent."""

    input_text: Optional[str] = None
    current_domain: Optional[str] = None

    doc_hid: Optional[str] = Field(
        description="An almost unique hash / id for the parent document of the chunk"
    )

    files: dict[str, bytes | dict] = Field(
        default_factory=lambda: dict(), description="Files to process"
    )

    current_chunk: Optional[Chunk] = Field(
        description="Current document chunk for processing"
    )

    chunks: dict[str, Chunk] = Field(
        default_factory=lambda: dict(), description="Chunks of the input text"
    )

    current_ontology: Ontology = Field(
        default_factory=lambda: Ontology(
            short_name=ONTOLOGY_VOID_ID,
            title="null title",
            description="null description",
            graph=RDFGraph(),
            iri=ONTOLOGY_VOID_IRI,
        ),
        description="Ontology object that contain the semantic graph as well as the description, name, short name, version, and IRI of the ontology",
    )
    graph_facts: RDFGraph = Field(
        default_factory=RDFGraph,
        description="RDF triples representing the facts from the current document",
    )
    ontology_addendum: Ontology = Field(
        default_factory=lambda: Ontology(
            short_name=ONTOLOGY_VOID_ID,
            title="null title",
            description="null description",
            graph=RDFGraph(),
            iri=ONTOLOGY_VOID_IRI,
        ),
        description="Ontology object that contain the semantic graph as well as the description, name, short name, version, and IRI of the ontology",
    )
    failure_stage: Optional[str] = None
    failure_reason: Optional[str] = None
    success_score: Optional[float] = 0.0
    status: Status = Status.SUCCESS
    node_visits: defaultdict[WorkflowNode, int] = Field(
        default_factory=lambda: defaultdict(int),
        description="Number of visits per node",
    )
    max_visits: int = Field(
        default=3, description="Maximum number of visits allowed per node"
    )

    max_chunks: Optional[int] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_domain = os.getenv("CURRENT_DOMAIN", DEFAULT_DOMAIN)

    def set_failure(self, stage: str, reason: str, success_score: float = 0.0) -> None:
        """
        Set failure state with stage and reason.

        Args:
            stage: The stage where the failure occurred
            reason: The reason for the failure
            success_score: The reason for the failure
        """
        self.failure_stage = stage
        self.failure_reason = reason
        self.success_score = success_score
        self.status = Status.FAILED

    def clear_failure(self) -> None:
        """Clear failure state and set status to success."""
        self.failure_stage = None
        self.failure_reason = None
        self.success_score = 0.0
        self.status = Status.SUCCESS

    @property
    def doc_iri(self):
        return f"{self.current_domain}/doc/{self.doc_hid}"

    @property
    def doc_namespace(self):
        return iri2namespace(self.doc_iri, ontology=False)
