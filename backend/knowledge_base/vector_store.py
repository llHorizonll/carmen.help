"""
Vector Store Module

ChromaDB integration for storing and querying document embeddings.
Provides a simple interface for semantic search over documentation chunks.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .parser import DocumentChunk
from .embeddings import EmbeddingProvider, create_embedding_provider

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """
    Represents a search result from the vector store.
    """

    chunk_id: str
    content: str
    source_file: str
    section_title: str
    full_path: str
    score: float
    metadata: dict

    @classmethod
    def from_query_result(
        cls,
        chunk_id: str,
        content: str,
        metadata: dict,
        distance: float,
    ) -> "SearchResult":
        """Create SearchResult from ChromaDB query result."""
        return cls(
            chunk_id=chunk_id,
            content=content,
            source_file=metadata.get("source_file", ""),
            section_title=metadata.get("section_title", ""),
            full_path=metadata.get("full_path", ""),
            score=1 - distance,  # Convert distance to similarity score
            metadata=metadata,
        )


class VectorStore:
    """
    ChromaDB-based vector store for documentation chunks.
    """

    DEFAULT_COLLECTION_NAME = "carmen_docs"

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        persist_directory: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        """
        Initialize the vector store.

        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist the database
            embedding_provider: Provider for generating embeddings
        """
        self.collection_name = collection_name

        if persist_directory is None:
            persist_directory = str(Path(__file__).parent / "chroma_db")
        self.persist_directory = persist_directory

        # Initialize embedding provider
        if embedding_provider is None:
            self._embedding_provider = create_embedding_provider("huggingface")
        else:
            self._embedding_provider = embedding_provider

        # Initialize ChromaDB
        self._client = None
        self._collection = None

    def _get_client(self):
        """Lazy initialize ChromaDB client."""
        if self._client is not None:
            return self._client

        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            raise ImportError(
                "chromadb is required for vector storage. "
                "Install with: pip install chromadb"
            )

        logger.info(f"Initializing ChromaDB at {self.persist_directory}")

        # Create persistent client
        self._client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
            ),
        )

        return self._client

    def _get_collection(self):
        """Get or create the collection."""
        if self._collection is not None:
            return self._collection

        client = self._get_client()

        # Get or create collection
        self._collection = client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "description": "Carmen documentation chunks",
                "embedding_model": self._embedding_provider.model_name,
                "dimension": str(self._embedding_provider.dimension),
            },
        )

        logger.info(
            f"Collection '{self.collection_name}' initialized "
            f"({self._collection.count()} documents)"
        )

        return self._collection

    def add_chunk(self, chunk: DocumentChunk) -> str:
        """
        Add a single document chunk to the store.

        Args:
            chunk: DocumentChunk to add

        Returns:
            The chunk ID
        """
        collection = self._get_collection()

        # Generate embedding
        embedding = self._embedding_provider.embed_text(chunk.content)

        # Prepare metadata
        metadata = {
            "source_file": chunk.source_file,
            "section_title": chunk.section_title,
            "full_path": chunk.full_path,
            "header_level": chunk.header_level,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
        }

        # Add to collection
        collection.add(
            ids=[chunk.chunk_id],
            embeddings=[embedding],
            documents=[chunk.content],
            metadatas=[metadata],
        )

        logger.debug(f"Added chunk: {chunk.chunk_id}")
        return chunk.chunk_id

    def add_chunks(
        self,
        chunks: list[DocumentChunk],
        batch_size: int = 100,
        show_progress: bool = True,
    ) -> list[str]:
        """
        Add multiple document chunks to the store.

        Args:
            chunks: List of DocumentChunks to add
            batch_size: Number of chunks to process at once
            show_progress: Whether to show progress

        Returns:
            List of chunk IDs
        """
        if not chunks:
            return []

        collection = self._get_collection()
        all_ids = []

        # Process in batches
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            # Generate embeddings for batch
            texts = [chunk.content for chunk in batch]
            embeddings = self._embedding_provider.embed_batch(texts)

            # Prepare batch data
            ids = [chunk.chunk_id for chunk in batch]
            documents = texts
            metadatas = [
                {
                    "source_file": chunk.source_file,
                    "section_title": chunk.section_title,
                    "full_path": chunk.full_path,
                    "header_level": chunk.header_level,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                }
                for chunk in batch
            ]

            # Add batch to collection
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )

            all_ids.extend(ids)

            if show_progress:
                progress = min(i + batch_size, len(chunks))
                logger.info(f"Added {progress}/{len(chunks)} chunks")

        logger.info(f"Added {len(all_ids)} chunks to collection")
        return all_ids

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[dict] = None,
    ) -> list[SearchResult]:
        """
        Search for similar documents.

        Args:
            query: Search query text
            n_results: Number of results to return
            filter_metadata: Optional metadata filters

        Returns:
            List of SearchResult objects
        """
        collection = self._get_collection()

        # Generate query embedding
        query_embedding = self._embedding_provider.embed_text(query)

        # Query collection
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata,
            include=["documents", "metadatas", "distances"],
        )

        # Convert to SearchResult objects
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                search_results.append(
                    SearchResult.from_query_result(
                        chunk_id=chunk_id,
                        content=results["documents"][0][i],
                        metadata=results["metadatas"][0][i],
                        distance=results["distances"][0][i],
                    )
                )

        return search_results

    def search_by_file(
        self,
        query: str,
        source_file: str,
        n_results: int = 5,
    ) -> list[SearchResult]:
        """
        Search within a specific source file.

        Args:
            query: Search query text
            source_file: Source file to filter by
            n_results: Number of results to return

        Returns:
            List of SearchResult objects
        """
        return self.search(
            query=query,
            n_results=n_results,
            filter_metadata={"source_file": source_file},
        )

    def get_chunk(self, chunk_id: str) -> Optional[SearchResult]:
        """
        Retrieve a specific chunk by ID.

        Args:
            chunk_id: The chunk ID to retrieve

        Returns:
            SearchResult or None if not found
        """
        collection = self._get_collection()

        results = collection.get(
            ids=[chunk_id],
            include=["documents", "metadatas"],
        )

        if results["ids"]:
            return SearchResult(
                chunk_id=chunk_id,
                content=results["documents"][0],
                source_file=results["metadatas"][0].get("source_file", ""),
                section_title=results["metadatas"][0].get("section_title", ""),
                full_path=results["metadatas"][0].get("full_path", ""),
                score=1.0,
                metadata=results["metadatas"][0],
            )

        return None

    def delete_chunk(self, chunk_id: str) -> bool:
        """
        Delete a chunk by ID.

        Args:
            chunk_id: The chunk ID to delete

        Returns:
            True if deleted, False if not found
        """
        collection = self._get_collection()

        try:
            collection.delete(ids=[chunk_id])
            logger.debug(f"Deleted chunk: {chunk_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete chunk {chunk_id}: {e}")
            return False

    def delete_by_source(self, source_file: str) -> int:
        """
        Delete all chunks from a specific source file.

        Args:
            source_file: Source file path

        Returns:
            Number of chunks deleted
        """
        collection = self._get_collection()

        # Get all chunks from this source
        results = collection.get(
            where={"source_file": source_file},
            include=["metadatas"],
        )

        if not results["ids"]:
            return 0

        # Delete them
        collection.delete(ids=results["ids"])
        logger.info(f"Deleted {len(results['ids'])} chunks from {source_file}")

        return len(results["ids"])

    def clear(self) -> int:
        """
        Clear all documents from the collection.

        Returns:
            Number of documents deleted
        """
        collection = self._get_collection()
        count = collection.count()

        # Delete collection and recreate
        client = self._get_client()
        client.delete_collection(self.collection_name)
        self._collection = None

        logger.info(f"Cleared {count} documents from collection")
        return count

    def count(self) -> int:
        """
        Get the number of documents in the collection.

        Returns:
            Document count
        """
        collection = self._get_collection()
        return collection.count()

    def get_stats(self) -> dict:
        """
        Get statistics about the vector store.

        Returns:
            Dictionary with store statistics
        """
        collection = self._get_collection()

        # Get all metadata to compute stats
        results = collection.get(include=["metadatas"])

        source_files = set()
        for metadata in results.get("metadatas", []):
            if metadata and "source_file" in metadata:
                source_files.add(metadata["source_file"])

        return {
            "collection_name": self.collection_name,
            "total_chunks": collection.count(),
            "unique_source_files": len(source_files),
            "embedding_model": self._embedding_provider.model_name,
            "embedding_dimension": self._embedding_provider.dimension,
            "persist_directory": self.persist_directory,
        }


def main():
    """
    Main entry point for testing the vector store.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Test vector store operations"
    )
    parser.add_argument(
        "--action",
        choices=["search", "stats", "clear"],
        default="stats",
        help="Action to perform",
    )
    parser.add_argument(
        "--query", "-q",
        help="Search query (for search action)",
    )
    parser.add_argument(
        "--results", "-n",
        type=int,
        default=5,
        help="Number of search results",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Create store
    store = VectorStore()

    if args.action == "stats":
        stats = store.get_stats()
        print("\nVector Store Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    elif args.action == "search":
        if not args.query:
            print("Error: --query is required for search action")
            return 1

        results = store.search(args.query, n_results=args.results)
        print(f"\nSearch results for: '{args.query}'")
        print("-" * 50)

        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result.section_title} (score: {result.score:.3f})")
            print(f"   Source: {result.source_file}")
            print(f"   Path: {result.full_path}")
            print(f"   Content: {result.content[:200]}...")

    elif args.action == "clear":
        confirm = input("Are you sure you want to clear all data? (yes/no): ")
        if confirm.lower() == "yes":
            count = store.clear()
            print(f"Cleared {count} documents")
        else:
            print("Cancelled")

    return 0


if __name__ == "__main__":
    exit(main())
