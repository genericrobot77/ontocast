from typing import Optional
import pathlib
from aot_cast.tool import (
    TripleStoreManager,
    FilesystemTripleStoreManager,
    OntologyManager,
    LLMTool,
    Converter,
    ChunkerTool,
)
from aot_cast.tool.aggregate import ChunkRDFGraphAggregator


class ToolBox:
    def __init__(self, **kwargs):
        working_directory: pathlib.Path = kwargs.pop("working_directory")
        ontology_directory: Optional[pathlib.Path] = kwargs.pop("ontology_directory")
        model_name: str = kwargs.pop("model_name")
        temperature: float = kwargs.pop("temperature")

        self.llm: LLMTool = LLMTool.create(model=model_name, temperature=temperature)
        self.triple_store_manager: TripleStoreManager = FilesystemTripleStoreManager(
            working_directory=working_directory, ontology_path=ontology_directory
        )
        self.ontology_manager: OntologyManager = OntologyManager()
        self.converter: Converter = Converter()
        self.chunker: ChunkerTool = ChunkerTool()
        self.aggregator: ChunkRDFGraphAggregator = ChunkRDFGraphAggregator()
