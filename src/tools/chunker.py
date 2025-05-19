from pydantic import Field
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
import torch
from .onto import Tool


class ChunkerTool(Tool):
    model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    breakpoint_threshold_type: str = Field(default="standard_deviation")
    breakpoint_threshold_amount: int = Field(default=3)
    bufer_size: int = Field(default=5)

    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._model = HuggingFaceEmbeddings(
            model_name=self.model,
            model_kwargs={"device": "cuda" if torch.cuda.is_available() else "cpu"},
            encode_kwargs={"normalize_embeddings": False},
        )

    def __call__(self, doc: str) -> list[str]:
        documents = [doc]

        text_splitter = SemanticChunker(
            buffer_size=self.bufer_size,
            breakpoint_threshold_type=self.breakpoint_threshold_type,
            breakpoint_threshold_amount=self.breakpoint_threshold_amount,
            embeddings=self._model,
        )
        docs = text_splitter.create_documents(documents)
        return docs
