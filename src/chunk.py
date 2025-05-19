from langchain_experimental.text_splitter import SemanticChunker
from langchain_core.documents import Document
import torch


def split(doc, embed_model=None) -> list[Document]:
    if embed_model is None:
        from langchain_community.embeddings import HuggingFaceEmbeddings

        embed_model = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cuda" if torch.cuda.is_available() else "cpu"},
            encode_kwargs={"normalize_embeddings": False},
        )

    documents = [doc]

    text_splitter = SemanticChunker(
        buffer_size=5,
        breakpoint_threshold_type="standard_deviation",
        breakpoint_threshold_amount=3,
        embeddings=embed_model,
    )
    docs = text_splitter.create_documents(documents)
    return docs
