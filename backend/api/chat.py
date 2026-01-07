"""
Chat API endpoint module.
Handles user chat queries with RAG-powered responses.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json

from api.rag import get_rag_pipeline, RAGPipeline
from services.chat_log import get_chat_log_service, ChatLogService


router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., description="The user's message")
    session_id: Optional[str] = Field(default=None, description="Chat session ID for conversation continuity")
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
    domain: Optional[str] = None
    collection: Optional[str] = None


class CollectionStats(BaseModel):
    """Statistics about which collections were used."""
    collection: str
    domain: str
    count: int


class UsageStats(BaseModel):
    """Token usage and timing statistics."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    response_time_ms: float = 0.0


class ChatResponse(BaseModel):
    """Response model for non-streaming chat."""
    answer: str
    sources: List[SourceDocument]
    session_id: Optional[str] = None
    usage: Optional[UsageStats] = None
    domains: List[str] = []  # List of domains used in response
    collection_breakdown: List[CollectionStats] = []  # Stats per collection


async def stream_response(
    query: str,
    chat_history: Optional[List[Dict[str, str]]],
    top_k: Optional[int],
    rag_pipeline: RAGPipeline,
    chat_log: ChatLogService,
    session_id: str,
):
    """Generate streaming response with SSE format."""
    full_response = ""
    sources_list = []
    try:
        generator, metadata = await rag_pipeline.query_stream(
            query=query,
            chat_history=chat_history,
            top_k=top_k,
        )

        usage_stats = None
        async for item in generator:
            if item.get("type") == "content":
                content = item["content"]
                full_response += content
                data = {"type": "chunk", "content": content}
                yield f"data: {json.dumps(data)}\n\n"
            elif item.get("type") == "stats":
                usage_stats = {
                    "prompt_tokens": item.get("prompt_tokens", 0),
                    "completion_tokens": item.get("completion_tokens", 0),
                    "total_tokens": item.get("total_tokens", 0),
                    "response_time_ms": item.get("response_time_ms", 0),
                }

        # Prepare sources
        sources_list = [
            {
                "id": doc.id,
                "source_url": doc.source_url,
                "score": doc.score,
            }
            for doc in metadata.sources
        ]

        # Calculate collection breakdown
        collection_counts: dict = {}
        for doc in metadata.sources:
            col_name = doc.collection or doc.metadata.get("collection", "unknown")
            domain = doc.domain or doc.metadata.get("domain", "general_docs")
            key = f"{col_name}|{domain}"
            if key not in collection_counts:
                collection_counts[key] = {"collection": col_name, "domain": domain, "count": 0}
            collection_counts[key]["count"] += 1

        sources_data = {
            "type": "sources",
            "sources": [
                {
                    "id": doc.id,
                    "content": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                    "score": doc.score,
                    "source_url": doc.source_url,
                    "metadata": doc.metadata,
                    "domain": doc.domain or doc.metadata.get("domain"),
                    "collection": doc.collection or doc.metadata.get("collection"),
                }
                for doc in metadata.sources
            ],
            "domains": list(metadata.domains) if metadata.domains else [],
            "collection_breakdown": list(collection_counts.values()),
        }
        yield f"data: {json.dumps(sources_data)}\n\n"

        # Send usage stats
        if usage_stats:
            yield f"data: {json.dumps({'type': 'usage', **usage_stats})}\n\n"

        # Log assistant response to database
        if full_response:
            chat_log.add_message(
                session_id=session_id,
                role="assistant",
                content=full_response,
                sources=sources_list if sources_list else None,
            )

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        error_data = {"type": "error", "message": str(e)}
        yield f"data: {json.dumps(error_data)}\n\n"


@router.post("/")
async def chat(
    request: ChatRequest,
    rag_pipeline: RAGPipeline = Depends(get_rag_pipeline),
    chat_log: ChatLogService = Depends(get_chat_log_service),
    x_user_id: Optional[str] = Header(default=None),
):
    """Chat endpoint that processes user queries using RAG."""
    # Get or create session
    session_id = request.session_id
    if not session_id:
        session = chat_log.create_session(user_id=x_user_id)
        session_id = session.id

    # Log user message
    chat_log.add_message(
        session_id=session_id,
        role="user",
        content=request.message,
    )

    # Build chat history
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
                chat_log=chat_log,
                session_id=session_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Session-Id": session_id,
            },
        )

    try:
        result = await rag_pipeline.query(
            query=request.message,
            chat_history=chat_history,
            top_k=request.top_k,
        )

        # Log assistant response
        sources_data = [
            {"id": doc.id, "source_url": doc.source_url, "score": doc.score}
            for doc in result.sources
        ]
        chat_log.add_message(
            session_id=session_id,
            role="assistant",
            content=result.answer,
            sources=sources_data,
        )

        # Calculate collection breakdown
        collection_counts: dict = {}
        for doc in result.sources:
            col_name = doc.collection or doc.metadata.get("collection", "unknown")
            domain = doc.domain or doc.metadata.get("domain", "general_docs")
            key = f"{col_name}|{domain}"
            if key not in collection_counts:
                collection_counts[key] = {"collection": col_name, "domain": domain, "count": 0}
            collection_counts[key]["count"] += 1

        return ChatResponse(
            answer=result.answer,
            sources=[
                SourceDocument(
                    id=doc.id,
                    content=doc.content,
                    score=doc.score,
                    source_url=doc.source_url,
                    metadata=doc.metadata,
                    domain=doc.domain or doc.metadata.get("domain"),
                    collection=doc.collection or doc.metadata.get("collection"),
                )
                for doc in result.sources
            ],
            session_id=session_id,
            usage=UsageStats(
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                total_tokens=result.usage.total_tokens,
                response_time_ms=result.usage.response_time_ms,
            ),
            domains=list(result.domains) if result.domains else [],
            collection_breakdown=[
                CollectionStats(**stats) for stats in collection_counts.values()
            ],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions")
async def get_suggestions():
    """Get auto-suggest questions for the chat widget."""
    return {
        "suggestions": [
            "ขอดูรายการหนี้ค้างชำระ (AR Aging) ที่เกินกำหนด 30 วัน",
            "มีบิลค่าใช้จ่าย (AP) ใบไหนที่รออนุมัติการจ่ายเงินบ้าง?",
            "ขอวิธีแก้ไขกรณีมียอดหนี้ค้างชำระ (AR) เกิน 90 วัน",
            "มีข้อผิดพลาด (Error) หรือปัญหา (Issue) อะไรที่พบในระบบ PMS บ้าง?",
            "ขอดูรายงานสรุปค่าใช้จ่าย (Expense Report) ประจำเดือนล่าสุด",
            "ช่วยแนะนำวิธีเพิ่มประสิทธิภาพการจัดการหนี้ค้างชำระ (AR Management)",
        ]
    }


# ===== Chat History Endpoints =====

@router.post("/sessions")
async def create_session(
    chat_log: ChatLogService = Depends(get_chat_log_service),
    x_user_id: Optional[str] = Header(default=None),
):
    """Create a new chat session."""
    session = chat_log.create_session(user_id=x_user_id)
    return {
        "session_id": session.id,
        "created_at": session.created_at,
    }


@router.get("/sessions")
async def list_sessions(
    limit: int = 50,
    chat_log: ChatLogService = Depends(get_chat_log_service),
    x_user_id: Optional[str] = Header(default=None),
):
    """List chat sessions for a user."""
    if x_user_id:
        sessions = chat_log.get_user_sessions(x_user_id, limit=limit)
    else:
        sessions = chat_log.get_recent_sessions(limit=limit)

    return {
        "sessions": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            }
            for s in sessions
        ]
    }


@router.get("/sessions/{session_id}")
async def get_session_history(
    session_id: str,
    chat_log: ChatLogService = Depends(get_chat_log_service),
):
    """Get chat history for a session."""
    session = chat_log.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = chat_log.get_session_messages(session_id)

    return {
        "session_id": session.id,
        "created_at": session.created_at,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources,
                "timestamp": m.timestamp,
            }
            for m in messages
        ]
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    chat_log: ChatLogService = Depends(get_chat_log_service),
):
    """Delete a chat session."""
    deleted = chat_log.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Session deleted", "session_id": session_id}


@router.get("/stats")
async def get_chat_stats(
    chat_log: ChatLogService = Depends(get_chat_log_service),
):
    """Get chat statistics."""
    return chat_log.get_stats()
