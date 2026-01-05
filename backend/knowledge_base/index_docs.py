"""
Index Documentation Script

Parses markdown documentation, generates embeddings, and stores in ChromaDB.
"""

import os
import logging
from pathlib import Path

from .sync_docs import DocSyncer
from .parser import MarkdownParser
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


def index_documentation(
    docs_path: str = None,
    chroma_path: str = None,
    collection_name: str = "carmen_docs",
):
    """
    Index documentation into ChromaDB.

    Args:
        docs_path: Path to documentation files
        chroma_path: Path to ChromaDB storage
        collection_name: Name of ChromaDB collection
    """
    # Default paths
    if docs_path is None:
        syncer = DocSyncer()
        docs_path = syncer.get_docs_path()

    if chroma_path is None:
        # Use the same path as the retriever service
        chroma_path = str(Path(__file__).parent.parent / "data" / "chroma")

    docs_path = Path(docs_path)

    logger.info(f"Indexing docs from: {docs_path}")
    logger.info(f"ChromaDB path: {chroma_path}")

    # Check if docs exist
    if not docs_path.exists():
        logger.error(f"Docs path does not exist: {docs_path}")
        logger.info("Run 'python -m knowledge_base.sync_docs' first")
        return False

    # Find all markdown files
    md_files = list(docs_path.rglob("*.md")) + list(docs_path.rglob("*.mdx"))

    if not md_files:
        logger.error(f"No markdown files found in: {docs_path}")
        return False

    logger.info(f"Found {len(md_files)} markdown files")

    # Parse all documents
    parser = MarkdownParser()
    all_chunks = []

    for md_file in md_files:
        try:
            chunks = parser.parse_file(md_file)  # Pass Path object, not string
            all_chunks.extend(chunks)
            logger.debug(f"Parsed {len(chunks)} chunks from {md_file.name}")
        except Exception as e:
            logger.warning(f"Failed to parse {md_file}: {e}")

    logger.info(f"Total chunks: {len(all_chunks)}")

    if not all_chunks:
        logger.error("No chunks to index")
        return False

    # Create vector store and add chunks
    store = VectorStore(
        collection_name=collection_name,
        persist_directory=chroma_path,
    )

    # Clear existing data
    try:
        existing = store.count()
        if existing > 0:
            logger.info(f"Clearing {existing} existing documents")
            store.clear()
    except:
        pass

    # Add new chunks
    logger.info("Generating embeddings and indexing...")
    store.add_chunks(all_chunks, show_progress=True)

    # Verify
    final_count = store.count()
    logger.info(f"Indexing complete! {final_count} documents in ChromaDB")

    return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Index Carmen Cloud documentation into ChromaDB"
    )
    parser.add_argument(
        "--docs-path",
        help="Path to documentation folder",
    )
    parser.add_argument(
        "--chroma-path",
        help="Path to ChromaDB storage",
    )
    parser.add_argument(
        "--collection",
        default="carmen_docs",
        help="ChromaDB collection name",
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

    success = index_documentation(
        docs_path=args.docs_path,
        chroma_path=args.chroma_path,
        collection_name=args.collection,
    )

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
