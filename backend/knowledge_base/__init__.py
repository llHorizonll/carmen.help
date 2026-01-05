"""
Carmen.help Knowledge Base Package

This package provides tools for:
- Syncing documentation from GitHub repositories
- Parsing Markdown/MDX files into semantic chunks
- Generating embeddings using HuggingFace or Z.ai
- Storing and querying vectors with ChromaDB

Usage:
    from knowledge_base.parser import MarkdownParser
    from knowledge_base.sync_docs import DocSyncer
    from knowledge_base.embeddings import create_embedding_provider
    from knowledge_base.vector_store import VectorStore
"""

__version__ = "0.1.0"

__all__ = [
    "MarkdownParser",
    "DocumentChunk",
    "EmbeddingProvider",
    "HuggingFaceEmbeddings",
    "ZaiEmbeddings",
    "VectorStore",
    "DocSyncer",
]


def __getattr__(name):
    """Lazy import to avoid circular import issues when running as module."""
    if name == "MarkdownParser":
        from .parser import MarkdownParser
        return MarkdownParser
    elif name == "DocumentChunk":
        from .parser import DocumentChunk
        return DocumentChunk
    elif name == "EmbeddingProvider":
        from .embeddings import EmbeddingProvider
        return EmbeddingProvider
    elif name == "HuggingFaceEmbeddings":
        from .embeddings import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings
    elif name == "ZaiEmbeddings":
        from .embeddings import ZaiEmbeddings
        return ZaiEmbeddings
    elif name == "VectorStore":
        from .vector_store import VectorStore
        return VectorStore
    elif name == "DocSyncer":
        from .sync_docs import DocSyncer
        return DocSyncer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
