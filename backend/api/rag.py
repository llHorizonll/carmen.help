"""
RAG (Retrieval Augmented Generation) module.
Orchestrates the RAG pipeline: query -> vector search -> context augmentation -> LLM response.
"""

from typing import AsyncGenerator, List, Dict, Any, Optional
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.llm import get_llm_service, LLMService
from services.retriever import get_retriever_service, RetrieverService, RetrievedDocument


@dataclass
class RAGResponse:
    """Response from the RAG pipeline."""
    answer: str
    sources: List[RetrievedDocument]
    context_used: str


@dataclass
class RAGStreamResponse:
    """Metadata for streaming RAG response."""
    sources: List[RetrievedDocument]
    context_used: str


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
    ) -> List[Dict[str, str]]:
        """Build the message list for the LLM."""
        messages = []

        system_prompt = self.llm.build_rag_prompt(context)
        messages.append({"role": "system", "content": system_prompt})

        if chat_history:
            for msg in chat_history:
                messages.append(msg)

        messages.append({"role": "user", "content": query})
        return messages

    async def query(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
    ) -> RAGResponse:
        """Execute the full RAG pipeline and return a complete response."""
        try:
            # Step 1: Retrieve relevant documents
            context, documents = await self.retriever.search_with_context(query, top_k)

            # Step 2: Build messages with context
            messages = self._build_messages(query, context, chat_history)

            # Step 3: Generate response from LLM
            answer = await self.llm.generate(messages)

            return RAGResponse(
                answer=answer,
                sources=documents,
                context_used=context,
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
    ) -> tuple[AsyncGenerator[str, None], RAGStreamResponse]:
        """Execute the RAG pipeline with streaming response."""
        try:
            context, documents = await self.retriever.search_with_context(query, top_k)
            messages = self._build_messages(query, context, chat_history)

            async def generate():
                async for chunk in self.llm.generate_stream(messages):
                    yield chunk

            metadata = RAGStreamResponse(
                sources=documents,
                context_used=context,
            )

            return generate(), metadata
        except Exception as e:
            print(f"RAG Stream Error: {e}")

            async def error_generate():
                yield f"Error: {str(e)}"

            return error_generate(), RAGStreamResponse(sources=[], context_used="")


_rag_pipeline: Optional[RAGPipeline] = None


def get_rag_pipeline() -> RAGPipeline:
    """Get or create the RAG pipeline singleton."""
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline
