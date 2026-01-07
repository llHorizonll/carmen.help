"""
RAG (Retrieval Augmented Generation) module.
Orchestrates the RAG pipeline: query -> vector search -> context augmentation -> LLM response.

Supports:
- Multi-collection search with result merging
- Domain-aware prompt selection based on retrieved documents
"""

from typing import AsyncGenerator, List, Dict, Any, Optional, Set
from dataclasses import dataclass, field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.llm import get_llm_service, LLMService, LLMResponse
from services.retriever import get_retriever_service, RetrieverService, RetrievedDocument


@dataclass
class UsageStats:
    """Token usage and timing statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    response_time_ms: float = 0.0


@dataclass
class RAGResponse:
    """Response from the RAG pipeline."""
    answer: str
    sources: List[RetrievedDocument]
    context_used: str
    usage: UsageStats = field(default_factory=UsageStats)
    domains: Set[str] = field(default_factory=set)  # Domains found in search results


@dataclass
class RAGStreamResponse:
    """Metadata for streaming RAG response."""
    sources: List[RetrievedDocument]
    context_used: str
    usage: UsageStats = field(default_factory=UsageStats)
    domains: Set[str] = field(default_factory=set)  # Domains found in search results


class RAGPipeline:
    """RAG Pipeline that orchestrates retrieval and generation."""

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        retriever_service: Optional[RetrieverService] = None,
    ):
        self.llm = llm_service or get_llm_service()
        self.retriever = retriever_service or get_retriever_service()

    def _build_messages(
        self,
        query: str,
        context: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        domains: Optional[Set[str]] = None,
        collections: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Build the message list for the LLM with domain-aware prompt."""
        messages = []

        # Use domain-aware prompt builder with collection info
        system_prompt = self.llm.build_rag_prompt(context, domains, collections)
        messages.append({"role": "system", "content": system_prompt})

        if chat_history:
            for msg in chat_history:
                messages.append(msg)

        messages.append({"role": "user", "content": query})
        return messages

    def _extract_collections(self, documents: List[RetrievedDocument]) -> List[str]:
        """Extract unique collection names from retrieved documents."""
        collections = set()
        for doc in documents:
            if doc.collection_name:
                collections.add(doc.collection_name)
        return list(collections)

    async def query(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
        use_multi_collection: bool = True,
    ) -> RAGResponse:
        """
        Execute the full RAG pipeline and return a complete response.

        Args:
            query: User query
            chat_history: Optional conversation history
            top_k: Number of documents to retrieve
            use_multi_collection: If True, search all collections (default)
        """
        try:
            # Step 1: Retrieve relevant documents
            if use_multi_collection:
                context, documents, domains = await self.retriever.search_with_context_multi(query, top_k)
            else:
                # Backward compatible single-collection search
                context, documents = await self.retriever.search_with_context(query, top_k)
                domains = set()

            # Step 2: Extract collection names for prompt context
            collections = self._extract_collections(documents)

            # Step 3: Build messages with context, domain, and collection info
            messages = self._build_messages(query, context, chat_history, domains, collections)

            # Step 4: Generate response from LLM
            llm_response = await self.llm.generate(messages)

            return RAGResponse(
                answer=llm_response.content,
                sources=documents,
                context_used=context,
                usage=UsageStats(
                    prompt_tokens=llm_response.prompt_tokens,
                    completion_tokens=llm_response.completion_tokens,
                    total_tokens=llm_response.total_tokens,
                    response_time_ms=llm_response.response_time_ms,
                ),
                domains=domains,
            )
        except Exception as e:
            print(f"RAG Pipeline Error: {e}")
            return RAGResponse(
                answer=f"I encountered an error processing your request: {str(e)}",
                sources=[],
                context_used="",
            )

    async def query_stream(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
        use_multi_collection: bool = True,
    ) -> tuple[AsyncGenerator[Dict[str, Any], None], RAGStreamResponse]:
        """
        Execute the RAG pipeline with streaming response.

        Args:
            query: User query
            chat_history: Optional conversation history
            top_k: Number of documents to retrieve
            use_multi_collection: If True, search all collections (default)

        Yields dicts with 'type': 'content' for text and 'type': 'stats' for usage.
        """
        try:
            if use_multi_collection:
                context, documents, domains = await self.retriever.search_with_context_multi(query, top_k)
            else:
                context, documents = await self.retriever.search_with_context(query, top_k)
                domains = set()

            # Extract collection names for prompt context
            collections = self._extract_collections(documents)

            messages = self._build_messages(query, context, chat_history, domains, collections)

            async def generate():
                async for item in self.llm.generate_stream(messages):
                    yield item

            metadata = RAGStreamResponse(
                sources=documents,
                context_used=context,
                domains=domains,
            )

            return generate(), metadata
        except Exception as e:
            print(f"RAG Stream Error: {e}")

            async def error_generate():
                yield {"type": "content", "content": f"Error: {str(e)}"}
                yield {"type": "stats", "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "response_time_ms": 0}

            return error_generate(), RAGStreamResponse(sources=[], context_used="")


_rag_pipeline: Optional[RAGPipeline] = None


def get_rag_pipeline() -> RAGPipeline:
    """Get or create the RAG pipeline singleton."""
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline
