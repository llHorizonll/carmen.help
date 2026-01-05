"""
Vector Database Retriever Service using ChromaDB.
"""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import os

# Fix import path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings


@dataclass
class RetrievedDocument:
    """Represents a document retrieved from the vector database."""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    source_url: Optional[str] = None


class RetrieverService:
    """Service for retrieving relevant documents from ChromaDB."""

    def __init__(self):
        """Initialize the retriever service with ChromaDB."""
        self.collection_name = settings.vector_collection
        self.top_k = settings.rag_top_k
        self.similarity_threshold = settings.rag_similarity_threshold
        self._client = None
        self._collection = None

    def _get_client(self):
        """Lazy initialize ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                persist_dir = settings.chroma_persist_dir

                # Create directory if not exists
                os.makedirs(persist_dir, exist_ok=True)

                # Use new ChromaDB API
                self._client = chromadb.PersistentClient(path=persist_dir)
            except Exception as e:
                print(f"ChromaDB init error: {e}")
                # Fallback to in-memory client
                import chromadb
                self._client = chromadb.Client()
        return self._client

    @property
    def collection(self):
        """Get or create the ChromaDB collection."""
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedDocument]:
        """Search for relevant documents in ChromaDB."""
        k = top_k or self.top_k

        try:
            # Check if collection has any documents
            if self.collection.count() == 0:
                print("Warning: Vector database is empty. Run knowledge_base sync first.")
                return []

            where_filter = filter_metadata if filter_metadata else None

            results = self.collection.query(
                query_texts=[query],
                n_results=k,
                where=where_filter,
                include=["documents", "metadatas", "distances"]
            )

            documents = []
            if results and results['ids'] and len(results['ids'][0]) > 0:
                for i, doc_id in enumerate(results['ids'][0]):
                    distance = results['distances'][0][i] if results['distances'] else 0
                    score = 1 - distance  # Convert distance to similarity

                    if score >= self.similarity_threshold:
                        metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                        content = results['documents'][0][i] if results['documents'] else ""

                        # Build source URL from metadata
                        source_url = None
                        if metadata.get('source_file'):
                            source_file = metadata['source_file'].replace('.md', '').replace('.mdx', '')
                            source_url = f"{settings.docs_site_url}/{source_file}"

                        documents.append(RetrievedDocument(
                            id=doc_id,
                            content=content,
                            metadata=metadata,
                            score=score,
                            source_url=source_url
                        ))

            return documents

        except Exception as e:
            print(f"Search error: {e}")
            return []

    async def search_with_context(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> Tuple[str, List[RetrievedDocument]]:
        """Search and build context string for RAG."""
        documents = await self.search(query, top_k)

        if not documents:
            return "", []

        context_parts = []
        max_chars = settings.rag_context_max_tokens * 4
        total_chars = 0

        for i, doc in enumerate(documents, 1):
            source_info = f"(Source: {doc.source_url})" if doc.source_url else ""
            section_title = doc.metadata.get('section_title', 'Documentation')
            doc_text = f"[{i}. {section_title}] {source_info}\n{doc.content}\n"

            if total_chars + len(doc_text) > max_chars:
                break
            context_parts.append(doc_text)
            total_chars += len(doc_text)

        context = "\n---\n".join(context_parts)
        return context, documents


_retriever_service: Optional[RetrieverService] = None


def get_retriever_service() -> RetrieverService:
    """Get or create the retriever service singleton."""
    global _retriever_service
    if _retriever_service is None:
        _retriever_service = RetrieverService()
    return _retriever_service
