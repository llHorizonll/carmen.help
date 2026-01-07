"""
Base classes and interfaces for data ingestors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncIterator
from enum import Enum
import hashlib
import uuid
from datetime import datetime


class SourceType(Enum):
    """Supported data source types."""
    MARKDOWN = "markdown"
    CSV = "csv"
    DATABASE = "database"
    URL = "url"


@dataclass
class IngestorConfig:
    """Configuration for data ingestion."""
    collection_name: str
    source_type: SourceType
    domain: str  # e.g., "usali", "general_docs", "faq"
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Chunking settings
    chunk_size: int = 1000  # Max characters per chunk
    chunk_overlap: int = 100  # Overlap between chunks
    min_chunk_size: int = 50  # Minimum chunk size

    def to_collection_metadata(self) -> Dict[str, Any]:
        """Convert config to ChromaDB collection metadata."""
        return {
            "domain": self.domain,
            "source_type": self.source_type.value,
            "description": self.description,
            "created_at": datetime.utcnow().isoformat(),
            "chunk_size": self.chunk_size,
            **self.metadata,
        }


@dataclass
class IngestedChunk:
    """Represents a chunk ready for embedding and storage."""
    chunk_id: str
    content: str
    source_type: SourceType
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        content: str,
        source_type: SourceType,
        source_identifier: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "IngestedChunk":
        """Create a chunk with auto-generated ID."""
        # Generate deterministic ID based on content and source
        hash_input = f"{source_identifier}:{content[:500]}"
        chunk_id = hashlib.md5(hash_input.encode()).hexdigest()[:16]

        return cls(
            chunk_id=chunk_id,
            content=content,
            source_type=source_type,
            metadata=metadata or {},
        )

    @classmethod
    def create_with_uuid(
        cls,
        content: str,
        source_type: SourceType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "IngestedChunk":
        """Create a chunk with random UUID."""
        return cls(
            chunk_id=str(uuid.uuid4())[:16],
            content=content,
            source_type=source_type,
            metadata=metadata or {},
        )


class BaseIngestor(ABC):
    """Abstract base class for all data ingestors."""

    def __init__(self, config: IngestorConfig):
        self.config = config

    @abstractmethod
    async def ingest(self, source: Any) -> List[IngestedChunk]:
        """
        Ingest data from source and return chunks.

        Args:
            source: The data source (file path, connection string, URL, etc.)

        Returns:
            List of IngestedChunk objects ready for embedding
        """
        pass

    @abstractmethod
    def validate_source(self, source: Any) -> bool:
        """
        Validate the data source before ingestion.

        Args:
            source: The data source to validate

        Returns:
            True if source is valid, False otherwise
        """
        pass

    async def ingest_stream(self, source: Any) -> AsyncIterator[IngestedChunk]:
        """
        Stream chunks from source for memory-efficient processing.
        Default implementation calls ingest() and yields results.
        Override for true streaming support.
        """
        chunks = await self.ingest(source)
        for chunk in chunks:
            yield chunk

    def chunk_text(self, text: str, source_identifier: str) -> List[IngestedChunk]:
        """
        Split text into chunks based on config settings.

        Args:
            text: The text to chunk
            source_identifier: Identifier for generating chunk IDs

        Returns:
            List of IngestedChunk objects
        """
        if not text or len(text.strip()) < self.config.min_chunk_size:
            return []

        chunks = []
        text = text.strip()

        # If text fits in one chunk, return as-is
        if len(text) <= self.config.chunk_size:
            chunks.append(IngestedChunk.create(
                content=text,
                source_type=self.config.source_type,
                source_identifier=f"{source_identifier}:0",
                metadata={"part": 1, "total_parts": 1},
            ))
            return chunks

        # Split into overlapping chunks
        start = 0
        part = 1

        while start < len(text):
            end = start + self.config.chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence ending within last 20% of chunk
                search_start = end - int(self.config.chunk_size * 0.2)
                for sep in ['. ', '.\n', '? ', '!\n', '\n\n']:
                    last_sep = text.rfind(sep, search_start, end)
                    if last_sep > start:
                        end = last_sep + len(sep)
                        break

            chunk_text = text[start:end].strip()

            if len(chunk_text) >= self.config.min_chunk_size:
                chunks.append(IngestedChunk.create(
                    content=chunk_text,
                    source_type=self.config.source_type,
                    source_identifier=f"{source_identifier}:{part}",
                    metadata={"part": part},
                ))
                part += 1

            # Move start with overlap
            start = end - self.config.chunk_overlap
            if start <= 0 or end >= len(text):
                start = end

        # Update total_parts in metadata
        total_parts = len(chunks)
        for chunk in chunks:
            chunk.metadata["total_parts"] = total_parts

        return chunks


@dataclass
class IngestionResult:
    """Result of an ingestion operation."""
    success: bool
    collection_name: str
    total_chunks: int
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "collection_name": self.collection_name,
            "total_chunks": self.total_chunks,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }
