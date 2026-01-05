"""
Chat API endpoint module.
Handles user chat queries with RAG-powered responses.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json

from api.rag import get_rag_pipeline, RAGPipeline


router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., description="The user's message")
    chat_history: Optional[List[ChatMessage]] = Field(
        default=None, description="Previous conversation history"
    )
    stream: bool = Field(default=True, description="Whether to stream the response")
    top_k: Optional[int] = Field(default=None, description="Number of documents to retrieve")


class SourceDocument(BaseModel):
    """Source document information."""
    id: str
    content: str
    score: float
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ChatResponse(BaseModel):
    """Response model for non-streaming chat."""
    answer: str
    sources: List[SourceDocument]


async def stream_response(
    query: str,
    chat_history: Optional[List[Dict[str, str]]],
    top_k: Optional[int],
    rag_pipeline: RAGPipeline,
):
    """Generate streaming response with SSE format."""
    try:
        generator, metadata = await rag_pipeline.query_stream(
            query=query,
            chat_history=chat_history,
            top_k=top_k,
        )

        async for chunk in generator:
            data = {"type": "chunk", "content": chunk}
            yield f"data: {json.dumps(data)}\n\n"

        sources_data = {
            "type": "sources",
            "sources": [
                {
                    "id": doc.id,
                    "content": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                    "score": doc.score,
                    "source_url": doc.source_url,
                    "metadata": doc.metadata,
                }
                for doc in metadata.sources
            ],
        }
        yield f"data: {json.dumps(sources_data)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        error_data = {"type": "error", "message": str(e)}
        yield f"data: {json.dumps(error_data)}\n\n"


@router.post("/")
async def chat(
    request: ChatRequest,
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline),
):
    """Chat endpoint that processes user queries using RAG."""
    chat_history = None
    if request.chat_history:
        chat_history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.chat_history
        ]

    if request.stream:
        return StreamingResponse(
            stream_response(
                query=request.message,
                chat_history=chat_history,
                top_k=request.top_k,
                rag_pipeline=rag_pipeline,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        result = await rag_pipeline.query(
            query=request.message,
            chat_history=chat_history,
            top_k=request.top_k,
        )

        return ChatResponse(
            answer=result.answer,
            sources=[
                SourceDocument(
                    id=doc.id,
                    content=doc.content,
                    score=doc.score,
                    source_url=doc.source_url,
                    metadata=doc.metadata,
                )
                for doc in result.sources
            ],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions")
async def get_suggestions():
    """Get auto-suggest questions for the chat widget."""
    return {
        "suggestions": [
            "How do I set up billing?",
            "What is the site policy?",
            "How do I create a new project?",
        ]
    }
