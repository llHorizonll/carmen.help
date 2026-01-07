"""
Collection Ingestion API

Endpoints for managing ChromaDB collections and importing data from various sources.
"""

import os
import tempfile
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from services.collection_metadata import (
    get_collection_metadata_service,
    CollectionMetadata,
    ImportJob,
    ImportJobStatus,
)
from knowledge_base.ingestors import IngestorConfig, SourceType
from knowledge_base.ingestors.csv_ingestor import CSVIngestor, USALICSVIngestor

# Database imports - optional, may fail if pymysql not installed
DATABASE_AVAILABLE = False
try:
    from knowledge_base.ingestors.database_ingestor import (
        DatabaseConfig,
        DatabaseIngestor,
        AutoDetectDatabaseIngestor,
        test_database_connection,
        list_database_tables,
        get_table_columns,
        preview_table_data,
    )
    DATABASE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Database features unavailable - {e}")
    # Create placeholder classes/functions
    class DatabaseConfig:
        pass
    class DatabaseIngestor:
        pass
    class AutoDetectDatabaseIngestor:
        pass
    def test_database_connection(*args, **kwargs):
        return False, "pymysql not installed. Run: pip install pymysql"
    def list_database_tables(*args, **kwargs):
        return []
    def get_table_columns(*args, **kwargs):
        return []
    def preview_table_data(*args, **kwargs):
        return {"columns": [], "rows": [], "total_count": 0}

from knowledge_base.vector_store import VectorStore
from knowledge_base.embeddings import HuggingFaceEmbeddings

router = APIRouter(prefix="/api/admin/collections", tags=["collection-management"])


# ==================== Request/Response Models ====================

class CollectionCreateRequest(BaseModel):
    """Request to create a new collection."""
    name: str
    domain: str  # "usali", "general_docs", "faq", "hotel_operations"
    description: str = ""


class CollectionUpdateRequest(BaseModel):
    """Request to update collection metadata."""
    domain: Optional[str] = None
    description: Optional[str] = None


class CollectionResponse(BaseModel):
    """Response with collection info."""
    id: str
    name: str
    domain: str
    source_type: str
    description: str
    created_at: str
    updated_at: str
    document_count: int = 0


class ImportJobResponse(BaseModel):
    """Response with import job info."""
    id: str
    collection_name: str
    source_type: str
    status: str
    progress: float
    total_items: int
    processed_items: int
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class CSVImportConfig(BaseModel):
    """Configuration for CSV import."""
    content_columns: List[str]
    metadata_columns: List[str] = []
    delimiter: str = ","
    is_usali: bool = False


class DatabaseConnectionRequest(BaseModel):
    """Database connection configuration."""
    db_type: str = "mariadb"  # "mysql", "mariadb"
    host: str = "127.0.0.1"
    port: int = 3306
    user: str
    password: str
    database: str


class DatabaseTableRequest(BaseModel):
    """Request for table operations."""
    db_type: str = "mariadb"
    host: str = "127.0.0.1"
    port: int = 3306
    user: str
    password: str
    database: str
    table_name: str


class DatabaseImportRequest(BaseModel):
    """Request to import from database."""
    collection_name: str
    domain: str
    description: str = ""
    db_type: str = "mariadb"
    host: str = "127.0.0.1"
    port: int = 3306
    user: str
    password: str
    database: str
    table_name: str
    content_columns: List[str]
    metadata_columns: List[str] = []
    where_clause: Optional[str] = None
    auto_detect_columns: bool = True
    save_connection: bool = False
    connection_name: Optional[str] = None


class SavedConnectionRequest(BaseModel):
    """Request to save a database connection."""
    name: str
    db_type: str = "mariadb"
    host: str = "127.0.0.1"
    port: int = 3306
    user: str
    password: str
    database: str


class SavedConnectionResponse(BaseModel):
    """Response with saved connection info."""
    id: str
    name: str
    db_type: str
    host: str
    port: int
    user: str
    database: str
    created_at: str


# ==================== Helper Functions ====================

def get_chroma_client():
    """Get ChromaDB client."""
    import chromadb
    persist_dir = settings.chroma_persist_dir
    os.makedirs(persist_dir, exist_ok=True)
    return chromadb.PersistentClient(path=persist_dir)


async def process_csv_import(
    job_id: str,
    collection_name: str,
    domain: str,
    file_path: str,
    config: CSVImportConfig,
):
    """Background task to process CSV import."""
    metadata_service = get_collection_metadata_service()

    try:
        # Update job status to running
        metadata_service.update_import_job(job_id, status=ImportJobStatus.RUNNING)

        # Create ingestor config
        ingestor_config = IngestorConfig(
            collection_name=collection_name,
            source_type=SourceType.CSV,
            domain=domain,
            chunk_size=1000,
        )

        # Create appropriate ingestor
        if config.is_usali:
            ingestor = USALICSVIngestor(config=ingestor_config)
        else:
            ingestor = CSVIngestor(
                config=ingestor_config,
                content_columns=config.content_columns,
                metadata_columns=config.metadata_columns,
                delimiter=config.delimiter,
            )

        # Validate and ingest
        if not ingestor.validate_source(file_path):
            raise ValueError("Invalid CSV file")

        chunks = await ingestor.ingest(file_path)

        if not chunks:
            raise ValueError("No data extracted from CSV")

        # Update total items
        metadata_service.update_import_job(job_id, total_items=len(chunks))

        # Create vector store and add chunks
        embedding_provider = HuggingFaceEmbeddings()
        vector_store = VectorStore(
            collection_name=collection_name,
            persist_directory=settings.chroma_persist_dir,
            embedding_provider=embedding_provider,
        )

        # Set collection metadata
        client = get_chroma_client()
        try:
            collection = client.get_collection(collection_name)
            # ChromaDB doesn't support updating metadata directly, so we work around
        except:
            collection = client.create_collection(
                name=collection_name,
                metadata={
                    "domain": domain,
                    "source_type": "csv",
                    "created_at": datetime.utcnow().isoformat(),
                }
            )

        # Add chunks in batches
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            # Prepare data for ChromaDB
            ids = [chunk.chunk_id for chunk in batch]
            documents = [chunk.content for chunk in batch]
            metadatas = [chunk.metadata for chunk in batch]

            # Generate embeddings
            embeddings = embedding_provider.embed_batch(documents)

            # Add to collection
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )

            # Update progress
            processed = min(i + batch_size, len(chunks))
            progress = processed / len(chunks) * 100
            metadata_service.update_import_job(
                job_id,
                processed_items=processed,
                progress=progress,
            )

        # Update job as completed
        metadata_service.update_import_job(
            job_id,
            status=ImportJobStatus.COMPLETED,
            processed_items=len(chunks),
            progress=100.0,
        )

        # Update collection stats
        metadata_service.update_collection(
            collection_name,
            stats={"document_count": len(chunks), "last_import": datetime.utcnow().isoformat()},
        )

    except Exception as e:
        # Update job as failed
        metadata_service.update_import_job(
            job_id,
            status=ImportJobStatus.FAILED,
            error_message=str(e),
        )
        raise

    finally:
        # Clean up temp file
        try:
            os.unlink(file_path)
        except:
            pass


# ==================== Collection CRUD Endpoints ====================

@router.post("/create", response_model=CollectionResponse)
async def create_collection(request: CollectionCreateRequest):
    """Create a new empty collection with metadata."""
    metadata_service = get_collection_metadata_service()

    # Check if collection already exists
    existing = metadata_service.get_collection(request.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Collection '{request.name}' already exists")

    # Validate domain
    valid_domains = ["budget", "usali", "general_docs", "faq", "hotel_operations", "custom"]
    if request.domain not in valid_domains:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid domain. Must be one of: {', '.join(valid_domains)}"
        )

    # Create metadata record
    metadata = metadata_service.create_collection(
        name=request.name,
        domain=request.domain,
        source_type="pending",  # Will be updated when data is imported
        description=request.description,
    )

    # Create empty ChromaDB collection
    client = get_chroma_client()
    try:
        client.create_collection(
            name=request.name,
            metadata={
                "domain": request.domain,
                "description": request.description,
                "created_at": datetime.utcnow().isoformat(),
            }
        )
    except Exception as e:
        # Rollback metadata
        metadata_service.delete_collection(request.name)
        raise HTTPException(status_code=500, detail=f"Failed to create ChromaDB collection: {str(e)}")

    return CollectionResponse(
        id=metadata.id,
        name=metadata.name,
        domain=metadata.domain,
        source_type=metadata.source_type,
        description=metadata.description,
        created_at=metadata.created_at,
        updated_at=metadata.updated_at,
        document_count=0,
    )


@router.get("/", response_model=List[CollectionResponse])
async def list_collections(include_empty: bool = False):
    """
    List all collections with metadata.

    Args:
        include_empty: If False (default), filter out collections that exist in
                      metadata but not in ChromaDB (stale records)
    """
    metadata_service = get_collection_metadata_service()
    client = get_chroma_client()

    # Get list of actual ChromaDB collections
    chroma_collections_map = {}
    try:
        chroma_collections = client.list_collections()
        for col in chroma_collections:
            chroma_collections_map[col.name] = col
    except Exception as e:
        print(f"Error listing ChromaDB collections: {e}")

    collections = metadata_service.get_all_collections()
    result = []

    for meta in collections:
        # Check if collection exists in ChromaDB
        chroma_col = chroma_collections_map.get(meta.name)

        if chroma_col:
            doc_count = chroma_col.count()
            result.append(CollectionResponse(
                id=meta.id,
                name=meta.name,
                domain=meta.domain,
                source_type=meta.source_type,
                description=meta.description,
                created_at=meta.created_at,
                updated_at=meta.updated_at,
                document_count=doc_count,
            ))
        elif include_empty:
            # Include stale metadata records if requested
            result.append(CollectionResponse(
                id=meta.id,
                name=meta.name,
                domain=meta.domain,
                source_type=meta.source_type,
                description=meta.description,
                created_at=meta.created_at,
                updated_at=meta.updated_at,
                document_count=0,
            ))

    # Also add ChromaDB collections not in metadata
    metadata_names = {m.name for m in collections}
    for col_name, chroma_col in chroma_collections_map.items():
        if col_name not in metadata_names:
            col_meta = chroma_col.metadata or {}
            result.append(CollectionResponse(
                id=f"chroma_{col_name}",
                name=col_name,
                domain=col_meta.get("domain", "general_docs"),
                source_type=col_meta.get("source_type", "unknown"),
                description=col_meta.get("description", ""),
                created_at=col_meta.get("created_at", ""),
                updated_at=col_meta.get("created_at", ""),
                document_count=chroma_col.count(),
            ))

    return result


# ==================== Import Job Endpoints ====================
# NOTE: These must be defined BEFORE /{collection_name} to avoid route conflicts

@router.get("/import-jobs", response_model=List[ImportJobResponse])
async def list_import_jobs(
    collection_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    """List import jobs with optional filters."""
    metadata_service = get_collection_metadata_service()

    status_enum = None
    if status:
        try:
            status_enum = ImportJobStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    jobs = metadata_service.get_import_jobs(
        collection_name=collection_name,
        status=status_enum,
        limit=limit,
    )

    return [
        ImportJobResponse(
            id=job.id,
            collection_name=job.collection_name,
            source_type=job.source_type,
            status=job.status.value,
            progress=job.progress,
            total_items=job.total_items,
            processed_items=job.processed_items,
            error_message=job.error_message,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
        for job in jobs
    ]


@router.get("/import-jobs/{job_id}", response_model=ImportJobResponse)
async def get_import_job(job_id: str):
    """Get import job status."""
    metadata_service = get_collection_metadata_service()
    job = metadata_service.get_import_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Import job '{job_id}' not found")

    return ImportJobResponse(
        id=job.id,
        collection_name=job.collection_name,
        source_type=job.source_type,
        status=job.status.value,
        progress=job.progress,
        total_items=job.total_items,
        processed_items=job.processed_items,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.delete("/import-jobs/{job_id}")
async def delete_import_job(job_id: str):
    """Delete an import job record."""
    metadata_service = get_collection_metadata_service()
    deleted = metadata_service.delete_import_job(job_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Import job '{job_id}' not found")

    return {"success": True, "message": f"Import job '{job_id}' deleted"}


# ==================== Domain Info Endpoint ====================
# NOTE: Must be defined BEFORE /{collection_name} to avoid route conflicts

@router.get("/domains")
async def list_domains():
    """List available domain types."""
    return {
        "domains": [
            {"id": "budget", "name": "Budget & Financial", "description": "Budget data and financial planning"},
            {"id": "usali", "name": "USALI Accounting", "description": "Hotel financial accounting (USALI standards)"},
            {"id": "general_docs", "name": "General Documentation", "description": "General Carmen Cloud documentation"},
            {"id": "faq", "name": "FAQ", "description": "Frequently asked questions"},
            {"id": "hotel_operations", "name": "Hotel Operations", "description": "Hotel operations and hospitality management"},
            {"id": "custom", "name": "Custom", "description": "Custom domain type"},
        ]
    }


# ==================== Import Endpoints ====================
# NOTE: Must be defined BEFORE /{collection_name} to avoid route conflicts

@router.post("/import/csv", response_model=ImportJobResponse)
async def import_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection_name: str = Form(...),
    domain: str = Form(...),
    content_columns: str = Form(...),  # comma-separated
    metadata_columns: str = Form(""),  # comma-separated
    delimiter: str = Form(","),
    is_usali: bool = Form(False),
):
    """
    Import data from a CSV file.

    - **file**: CSV file to upload
    - **collection_name**: Name of the collection to import into
    - **domain**: Domain type (usali, general_docs, faq, etc.)
    - **content_columns**: Comma-separated column names for content
    - **metadata_columns**: Comma-separated column names for metadata (optional)
    - **delimiter**: CSV delimiter (default: comma)
    - **is_usali**: Use USALI-specific ingestor format
    """
    metadata_service = get_collection_metadata_service()

    # Parse columns
    content_cols = [c.strip() for c in content_columns.split(",") if c.strip()]
    metadata_cols = [c.strip() for c in metadata_columns.split(",") if c.strip()]

    if not content_cols:
        raise HTTPException(status_code=400, detail="At least one content column is required")

    # Save uploaded file to temp location
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    try:
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {str(e)}")

    # Ensure collection exists or create it
    existing = metadata_service.get_collection(collection_name)
    if not existing:
        metadata_service.create_collection(
            name=collection_name,
            domain=domain,
            source_type="csv",
            description=f"Imported from {file.filename}",
        )
    else:
        # Update source type
        metadata_service.update_collection(collection_name, config={"source_type": "csv"})

    # Create import job
    config = CSVImportConfig(
        content_columns=content_cols,
        metadata_columns=metadata_cols,
        delimiter=delimiter,
        is_usali=is_usali,
    )

    job = metadata_service.create_import_job(
        collection_name=collection_name,
        source_type="csv",
        config=config.model_dump(),
    )

    # Start background import task
    background_tasks.add_task(
        process_csv_import,
        job.id,
        collection_name,
        domain,
        temp_file.name,
        config,
    )

    return ImportJobResponse(
        id=job.id,
        collection_name=job.collection_name,
        source_type=job.source_type,
        status=job.status.value,
        progress=job.progress,
        total_items=job.total_items,
        processed_items=job.processed_items,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post("/import/database", response_model=ImportJobResponse)
async def import_database(
    background_tasks: BackgroundTasks,
    request: DatabaseImportRequest,
):
    """
    Import data from a database table.

    - **collection_name**: Name of the collection to import into
    - **domain**: Domain type (usali, general_docs, etc.)
    - **table_name**: Database table to import from
    - **content_columns**: Columns to use as searchable content
    - **metadata_columns**: Columns to store as metadata
    - **where_clause**: Optional SQL WHERE clause (without 'WHERE')
    - **auto_detect_columns**: Auto-detect text columns for content
    """
    metadata_service = get_collection_metadata_service()

    # Validate at least one content column if not auto-detecting
    if not request.auto_detect_columns and not request.content_columns:
        raise HTTPException(
            status_code=400,
            detail="At least one content column is required when auto-detect is disabled"
        )

    # Ensure collection exists or create it
    existing = metadata_service.get_collection(request.collection_name)
    if not existing:
        metadata_service.create_collection(
            name=request.collection_name,
            domain=request.domain,
            source_type="database",
            description=request.description or f"Imported from {request.table_name}",
        )

    # Save connection if requested
    if request.save_connection and request.connection_name:
        metadata_service.save_database_connection(
            name=request.connection_name,
            db_type=request.db_type,
            host=request.host,
            port=request.port,
            user=request.user,
            password=request.password,
            database=request.database,
        )

    # Create import job
    job = metadata_service.create_import_job(
        collection_name=request.collection_name,
        source_type="database",
        config={
            "table_name": request.table_name,
            "content_columns": request.content_columns,
            "metadata_columns": request.metadata_columns,
            "where_clause": request.where_clause,
            "auto_detect": request.auto_detect_columns,
        },
    )

    # Prepare db config dict (without password in logs)
    db_config_dict = {
        "db_type": request.db_type,
        "host": request.host,
        "port": request.port,
        "user": request.user,
        "password": request.password,
        "database": request.database,
    }

    # Start background import task
    background_tasks.add_task(
        process_database_import,
        job.id,
        request.collection_name,
        request.domain,
        db_config_dict,
        request.table_name,
        request.content_columns,
        request.metadata_columns,
        request.where_clause,
        request.auto_detect_columns,
    )

    return ImportJobResponse(
        id=job.id,
        collection_name=job.collection_name,
        source_type=job.source_type,
        status=job.status.value,
        progress=job.progress,
        total_items=job.total_items,
        processed_items=job.processed_items,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


# ==================== Collection Detail Endpoints ====================
# NOTE: /{collection_name} routes must come AFTER all specific routes

@router.get("/{collection_name}", response_model=CollectionResponse)
async def get_collection(collection_name: str):
    """Get collection details."""
    metadata_service = get_collection_metadata_service()
    client = get_chroma_client()

    metadata = metadata_service.get_collection(collection_name)

    # Get document count
    doc_count = 0
    try:
        chroma_col = client.get_collection(collection_name)
        doc_count = chroma_col.count()
    except:
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")

    if metadata:
        return CollectionResponse(
            id=metadata.id,
            name=metadata.name,
            domain=metadata.domain,
            source_type=metadata.source_type,
            description=metadata.description,
            created_at=metadata.created_at,
            updated_at=metadata.updated_at,
            document_count=doc_count,
        )
    else:
        # Return info from ChromaDB only
        try:
            chroma_col = client.get_collection(collection_name)
            col_meta = chroma_col.metadata or {}
            return CollectionResponse(
                id=f"chroma_{collection_name}",
                name=collection_name,
                domain=col_meta.get("domain", "general_docs"),
                source_type=col_meta.get("source_type", "unknown"),
                description=col_meta.get("description", ""),
                created_at=col_meta.get("created_at", ""),
                updated_at=col_meta.get("created_at", ""),
                document_count=doc_count,
            )
        except:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")


@router.put("/{collection_name}", response_model=CollectionResponse)
async def update_collection(collection_name: str, request: CollectionUpdateRequest):
    """Update collection metadata."""
    metadata_service = get_collection_metadata_service()

    metadata = metadata_service.update_collection(
        collection_name,
        domain=request.domain,
        description=request.description,
    )

    if not metadata:
        raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")

    # Get document count
    client = get_chroma_client()
    doc_count = 0
    try:
        chroma_col = client.get_collection(collection_name)
        doc_count = chroma_col.count()
    except:
        pass

    return CollectionResponse(
        id=metadata.id,
        name=metadata.name,
        domain=metadata.domain,
        source_type=metadata.source_type,
        description=metadata.description,
        created_at=metadata.created_at,
        updated_at=metadata.updated_at,
        document_count=doc_count,
    )


@router.delete("/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete a collection and all its data."""
    metadata_service = get_collection_metadata_service()
    client = get_chroma_client()

    # Delete from ChromaDB
    try:
        client.delete_collection(collection_name)
    except Exception as e:
        print(f"Warning: Could not delete ChromaDB collection: {e}")

    # Delete metadata
    deleted = metadata_service.delete_collection(collection_name)

    return {"success": True, "message": f"Collection '{collection_name}' deleted"}


@router.post("/cleanup-stale")
async def cleanup_stale_collections():
    """
    Remove metadata records for collections that don't exist in ChromaDB.
    This cleans up stale records from failed or incomplete imports.
    """
    metadata_service = get_collection_metadata_service()
    client = get_chroma_client()

    # Get actual ChromaDB collections
    chroma_names = set()
    try:
        chroma_collections = client.list_collections()
        chroma_names = {col.name for col in chroma_collections}
    except Exception as e:
        return {"success": False, "error": f"Failed to list ChromaDB collections: {e}"}

    # Find and delete stale metadata records
    metadata_collections = metadata_service.get_all_collections()
    deleted_count = 0
    deleted_names = []

    for meta in metadata_collections:
        if meta.name not in chroma_names:
            # This metadata record has no corresponding ChromaDB collection
            if metadata_service.delete_collection(meta.name):
                deleted_count += 1
                deleted_names.append(meta.name)

    return {
        "success": True,
        "deleted_count": deleted_count,
        "deleted_collections": deleted_names,
        "message": f"Cleaned up {deleted_count} stale collection(s)",
    }


# ==================== Database Connection Endpoints ====================

@router.post("/database/test-connection")
async def test_db_connection(request: DatabaseConnectionRequest):
    """Test database connection."""
    if not DATABASE_AVAILABLE:
        return {"success": False, "message": "Database driver not installed. Please run: pip install pymysql"}

    try:
        db_config = DatabaseConfig(
            db_type=request.db_type,
            host=request.host,
            port=request.port,
            user=request.user,
            password=request.password,
            database=request.database,
        )

        success, message = test_database_connection(db_config)
        return {"success": success, "message": message}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}


@router.post("/database/tables")
async def list_db_tables(request: DatabaseConnectionRequest):
    """List all tables in the database."""
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database driver not installed. Please run: pip install pymysql")

    db_config = DatabaseConfig(
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        user=request.user,
        password=request.password,
        database=request.database,
    )

    try:
        tables = list_database_tables(db_config)
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/database/columns")
async def get_db_columns(request: DatabaseTableRequest):
    """Get columns for a table."""
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database driver not installed. Please run: pip install pymysql")

    db_config = DatabaseConfig(
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        user=request.user,
        password=request.password,
        database=request.database,
    )

    try:
        columns = get_table_columns(db_config, request.table_name)
        return {"columns": columns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/database/preview")
async def preview_db_data(request: DatabaseTableRequest, limit: int = 10):
    """Preview table data."""
    if not DATABASE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Database driver not installed. Please run: pip install pymysql")

    db_config = DatabaseConfig(
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        user=request.user,
        password=request.password,
        database=request.database,
    )

    try:
        preview = preview_table_data(db_config, request.table_name, limit)
        return preview
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Database Import ====================

async def process_database_import(
    job_id: str,
    collection_name: str,
    domain: str,
    db_config_dict: Dict[str, Any],
    table_name: str,
    content_columns: List[str],
    metadata_columns: List[str],
    where_clause: Optional[str] = None,
    auto_detect: bool = True,
):
    """Background task to process database import."""
    metadata_service = get_collection_metadata_service()

    try:
        # Update job status to running
        metadata_service.update_import_job(job_id, status=ImportJobStatus.RUNNING)

        # Create database config
        db_config = DatabaseConfig(**db_config_dict)

        # Create ingestor config
        ingestor_config = IngestorConfig(
            collection_name=collection_name,
            source_type=SourceType.DATABASE,
            domain=domain,
            chunk_size=1000,
        )

        # Create appropriate ingestor
        if auto_detect and not content_columns:
            ingestor = AutoDetectDatabaseIngestor(
                config=ingestor_config,
                db_config=db_config,
                table_name=table_name,
                where_clause=where_clause,
            )
        else:
            ingestor = DatabaseIngestor(
                config=ingestor_config,
                db_config=db_config,
                table_name=table_name,
                content_columns=content_columns,
                metadata_columns=metadata_columns,
                where_clause=where_clause,
            )

        # Validate connection
        if not ingestor.validate_source(None):
            raise ValueError("Failed to connect to database")

        # Ingest data
        chunks = await ingestor.ingest(None)

        if not chunks:
            raise ValueError("No data extracted from database")

        # Update total items
        metadata_service.update_import_job(job_id, total_items=len(chunks))

        # Create vector store
        embedding_provider = HuggingFaceEmbeddings()

        # Get or create ChromaDB collection
        client = get_chroma_client()
        try:
            collection = client.get_collection(collection_name)
        except:
            collection = client.create_collection(
                name=collection_name,
                metadata={
                    "domain": domain,
                    "source_type": "database",
                    "source_table": table_name,
                    "created_at": datetime.utcnow().isoformat(),
                }
            )

        # Add chunks in batches
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            # Prepare data for ChromaDB
            ids = [chunk.chunk_id for chunk in batch]
            documents = [chunk.content for chunk in batch]
            metadatas = [chunk.metadata for chunk in batch]

            # Generate embeddings
            embeddings = embedding_provider.embed_batch(documents)

            # Add to collection
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )

            # Update progress
            processed = min(i + batch_size, len(chunks))
            progress = processed / len(chunks) * 100
            metadata_service.update_import_job(
                job_id,
                processed_items=processed,
                progress=progress,
            )

        # Update job as completed
        metadata_service.update_import_job(
            job_id,
            status=ImportJobStatus.COMPLETED,
            processed_items=len(chunks),
            progress=100.0,
        )

        # Update collection stats
        metadata_service.update_collection(
            collection_name,
            stats={
                "document_count": len(chunks),
                "source_table": table_name,
                "last_import": datetime.utcnow().isoformat(),
            },
        )

    except Exception as e:
        # Update job as failed
        metadata_service.update_import_job(
            job_id,
            status=ImportJobStatus.FAILED,
            error_message=str(e),
        )
        raise


# ==================== Saved Database Connections ====================

@router.get("/database/connections", response_model=List[SavedConnectionResponse])
async def list_saved_connections():
    """List all saved database connections."""
    metadata_service = get_collection_metadata_service()
    connections = metadata_service.get_all_database_connections()

    return [
        SavedConnectionResponse(
            id=conn.id,
            name=conn.name,
            db_type=conn.db_type,
            host=conn.host,
            port=conn.port,
            user=conn.user,
            database=conn.database,
            created_at=conn.created_at,
        )
        for conn in connections
    ]


@router.post("/database/connections", response_model=SavedConnectionResponse)
async def save_connection(request: SavedConnectionRequest):
    """Save a database connection for reuse."""
    metadata_service = get_collection_metadata_service()

    conn = metadata_service.save_database_connection(
        name=request.name,
        db_type=request.db_type,
        host=request.host,
        port=request.port,
        user=request.user,
        password=request.password,
        database=request.database,
    )

    return SavedConnectionResponse(
        id=conn.id,
        name=conn.name,
        db_type=conn.db_type,
        host=conn.host,
        port=conn.port,
        user=conn.user,
        database=conn.database,
        created_at=conn.created_at,
    )


@router.get("/database/connections/{connection_id}")
async def get_saved_connection(connection_id: str, include_password: bool = False):
    """Get a saved database connection."""
    metadata_service = get_collection_metadata_service()
    conn = metadata_service.get_database_connection(connection_id)

    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    return conn.to_dict(include_password=include_password)


@router.delete("/database/connections/{connection_id}")
async def delete_saved_connection(connection_id: str):
    """Delete a saved database connection."""
    metadata_service = get_collection_metadata_service()
    deleted = metadata_service.delete_database_connection(connection_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")

    return {"success": True, "message": "Connection deleted"}
