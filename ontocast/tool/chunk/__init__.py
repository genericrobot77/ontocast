"""Document chunking tools for OntoCast.

This package provides tools for splitting documents into manageable chunks
for processing. It includes semantic chunking capabilities and utilities
for chunk management.

Available tools:
- ChunkerTool: Main chunking tool for document segmentation
- util: Utility functions for chunk processing and management
"""

from ontocast.tool.chunk.chunker import ChunkerTool

__all__ = [
    "ChunkerTool",
]
