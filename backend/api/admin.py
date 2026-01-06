"""
Admin API endpoints for ChromaDB management and inspection.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import chromadb

from config import settings


router = APIRouter(prefix="/api/admin/chroma", tags=["admin"])


def get_chroma_client() -> chromadb.PersistentClient:
    """Get ChromaDB client instance."""
    return chromadb.PersistentClient(path=settings.chroma_persist_dir)


class CollectionInfo(BaseModel):
    """Collection information response."""
    name: str
    count: int
    metadata: dict


class DocumentResponse(BaseModel):
    """Document response model."""
    id: str
    document: Optional[str] = None
    metadata: Optional[dict] = None
    embedding: Optional[list[float]] = None


class DocumentsListResponse(BaseModel):
    """Paginated documents list response."""
    total: int
    offset: int
    limit: int
    documents: list[DocumentResponse]


class SearchResult(BaseModel):
    """Search result model."""
    id: str
    document: Optional[str] = None
    metadata: Optional[dict] = None
    distance: float
    similarity: float


@router.get("/collections", response_model=list[CollectionInfo])
async def list_collections():
    """List all ChromaDB collections with their stats."""
    try:
        client = get_chroma_client()
        collections = client.list_collections()

        result = []
        for col in collections:
            collection = client.get_collection(col.name)
            result.append(CollectionInfo(
                name=col.name,
                count=collection.count(),
                metadata=col.metadata or {}
            ))

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_name}", response_model=CollectionInfo)
async def get_collection_info(collection_name: str):
    """Get detailed information about a specific collection."""
    try:
        client = get_chroma_client()
        collection = client.get_collection(collection_name)

        return CollectionInfo(
            name=collection.name,
            count=collection.count(),
            metadata=collection.metadata or {}
        )
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_name}/documents", response_model=DocumentsListResponse)
async def list_documents(
    collection_name: str,
    offset: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of documents to return"),
    include_embeddings: bool = Query(False, description="Include embedding vectors in response")
):
    """List documents in a collection with pagination."""
    try:
        client = get_chroma_client()
        collection = client.get_collection(collection_name)
        total = collection.count()

        if total == 0:
            return DocumentsListResponse(
                total=0,
                offset=offset,
                limit=limit,
                documents=[]
            )

        include = ["documents", "metadatas"]
        if include_embeddings:
            include.append("embeddings")

        results = collection.get(
            include=include,
            limit=limit,
            offset=offset
        )

        documents = []
        for i, doc_id in enumerate(results["ids"]):
            doc = DocumentResponse(
                id=doc_id,
                document=results["documents"][i] if results["documents"] else None,
                metadata=results["metadatas"][i] if results["metadatas"] else None,
                embedding=results["embeddings"][i] if include_embeddings and results.get("embeddings") else None
            )
            documents.append(doc)

        return DocumentsListResponse(
            total=total,
            offset=offset,
            limit=limit,
            documents=documents
        )
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_name}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    collection_name: str,
    document_id: str,
    include_embedding: bool = Query(False, description="Include embedding vector in response")
):
    """Get a specific document by ID."""
    try:
        client = get_chroma_client()
        collection = client.get_collection(collection_name)

        include = ["documents", "metadatas"]
        if include_embedding:
            include.append("embeddings")

        results = collection.get(
            ids=[document_id],
            include=include
        )

        if not results["ids"]:
            raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")

        return DocumentResponse(
            id=results["ids"][0],
            document=results["documents"][0] if results["documents"] else None,
            metadata=results["metadatas"][0] if results["metadatas"] else None,
            embedding=results["embeddings"][0] if include_embedding and results.get("embeddings") else None
        )
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_name}/search", response_model=list[SearchResult])
async def search_documents(
    collection_name: str,
    q: str = Query(..., min_length=1, description="Search query text"),
    top_k: int = Query(10, ge=1, le=50, description="Number of results to return"),
    source_filter: Optional[str] = Query(None, description="Filter by source metadata field")
):
    """Search documents using semantic similarity.

    Note: This uses the collection's configured embedding function.
    If the collection doesn't have one, you'll need to provide embeddings directly.
    """
    try:
        client = get_chroma_client()
        collection = client.get_collection(collection_name)

        where_filter = None
        if source_filter:
            where_filter = {"source": {"$contains": source_filter}}

        results = collection.query(
            query_texts=[q],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0
                search_results.append(SearchResult(
                    id=doc_id,
                    document=results["documents"][0][i] if results["documents"] else None,
                    metadata=results["metadatas"][0][i] if results["metadatas"] else None,
                    distance=distance,
                    similarity=1 - distance
                ))

        return search_results
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{collection_name}/documents/{document_id}")
async def delete_document(collection_name: str, document_id: str):
    """Delete a specific document by ID."""
    try:
        client = get_chroma_client()
        collection = client.get_collection(collection_name)

        existing = collection.get(ids=[document_id])
        if not existing["ids"]:
            raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")

        collection.delete(ids=[document_id])

        return {"message": f"Document '{document_id}' deleted successfully"}
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_chroma_stats():
    """Get overall ChromaDB statistics."""
    try:
        client = get_chroma_client()
        collections = client.list_collections()

        total_documents = 0
        collection_stats = []

        for col in collections:
            collection = client.get_collection(col.name)
            count = collection.count()
            total_documents += count
            collection_stats.append({
                "name": col.name,
                "count": count,
                "metadata": col.metadata or {}
            })

        return {
            "persist_directory": settings.chroma_persist_dir,
            "total_collections": len(collections),
            "total_documents": total_documents,
            "collections": collection_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
