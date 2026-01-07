"""
Collection Metadata Service

Manages metadata for ChromaDB collections and tracks import jobs.
Uses SQLite for persistence.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ImportJobStatus(Enum):
    """Status of an import job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CollectionMetadata:
    """Metadata for a ChromaDB collection."""
    id: str
    name: str
    domain: str  # e.g., "usali", "general_docs", "faq"
    source_type: str  # "csv", "database", "url", "markdown"
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    config: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        now = datetime.utcnow().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "source_type": self.source_type,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "config": self.config,
            "stats": self.stats,
        }


@dataclass
class ImportJob:
    """Represents an import job for a collection."""
    id: str
    collection_name: str
    source_type: str
    status: ImportJobStatus
    progress: float = 0.0
    total_items: int = 0
    processed_items: int = 0
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "collection_name": self.collection_name,
            "source_type": self.source_type,
            "status": self.status.value,
            "progress": self.progress,
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "config": self.config,
        }


@dataclass
class SavedDatabaseConnection:
    """Saved database connection configuration."""
    id: str
    name: str
    db_type: str  # "mysql", "mariadb"
    host: str
    port: int
    user: str
    password: str
    database: str
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    def to_dict(self, include_password: bool = False) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "db_type": self.db_type,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "database": self.database,
            "created_at": self.created_at,
        }
        if include_password:
            result["password"] = self.password
        return result


class CollectionMetadataService:
    """Service for managing collection metadata and import jobs."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the collection metadata service.

        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            db_path = str(Path(__file__).parent.parent / "data" / "collections.db")

        self.db_path = db_path
        self._ensure_db_exists()
        self._init_tables()

    def _ensure_db_exists(self):
        """Ensure the database directory exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """Initialize database tables."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Collection metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS collection_metadata (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    domain TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    config TEXT,
                    stats TEXT
                )
            """)

            # Import jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_jobs (
                    id TEXT PRIMARY KEY,
                    collection_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL DEFAULT 0,
                    total_items INTEGER DEFAULT 0,
                    processed_items INTEGER DEFAULT 0,
                    error_message TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    config TEXT
                )
            """)

            # Saved database connections table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS saved_db_connections (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    db_type TEXT NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    user TEXT NOT NULL,
                    password TEXT NOT NULL,
                    database TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_collection_domain
                ON collection_metadata(domain)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_import_jobs_status
                ON import_jobs(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_import_jobs_collection
                ON import_jobs(collection_name)
            """)

            conn.commit()
            logger.info("Collection metadata database initialized")
        finally:
            conn.close()

    # ==================== Collection Methods ====================

    def create_collection(
        self,
        name: str,
        domain: str,
        source_type: str,
        description: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> CollectionMetadata:
        """
        Create a new collection metadata record.

        Args:
            name: Collection name (must be unique)
            domain: Domain type (e.g., "usali", "general_docs")
            source_type: Source type (e.g., "csv", "database")
            description: Collection description
            config: Optional configuration dict

        Returns:
            Created CollectionMetadata
        """
        metadata = CollectionMetadata(
            id=str(uuid.uuid4()),
            name=name,
            domain=domain,
            source_type=source_type,
            description=description,
            config=config,
        )

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO collection_metadata
                (id, name, domain, source_type, description, created_at, updated_at, config, stats)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.id,
                metadata.name,
                metadata.domain,
                metadata.source_type,
                metadata.description,
                metadata.created_at,
                metadata.updated_at,
                json.dumps(metadata.config) if metadata.config else None,
                json.dumps(metadata.stats) if metadata.stats else None,
            ))
            conn.commit()
            logger.info(f"Created collection metadata: {name}")
        finally:
            conn.close()

        return metadata

    def get_collection(self, name: str) -> Optional[CollectionMetadata]:
        """Get collection metadata by name."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM collection_metadata WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_collection(row)
            return None
        finally:
            conn.close()

    def get_all_collections(self) -> List[CollectionMetadata]:
        """Get all collection metadata records."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM collection_metadata
                ORDER BY updated_at DESC
            """)
            rows = cursor.fetchall()
            return [self._row_to_collection(row) for row in rows]
        finally:
            conn.close()

    def get_collections_by_domain(self, domain: str) -> List[CollectionMetadata]:
        """Get collections filtered by domain."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM collection_metadata WHERE domain = ? ORDER BY name",
                (domain,)
            )
            rows = cursor.fetchall()
            return [self._row_to_collection(row) for row in rows]
        finally:
            conn.close()

    def update_collection(
        self,
        name: str,
        domain: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        stats: Optional[Dict[str, Any]] = None,
    ) -> Optional[CollectionMetadata]:
        """Update collection metadata."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Build update query dynamically
            updates = ["updated_at = ?"]
            params = [datetime.utcnow().isoformat()]

            if domain is not None:
                updates.append("domain = ?")
                params.append(domain)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if config is not None:
                updates.append("config = ?")
                params.append(json.dumps(config))
            if stats is not None:
                updates.append("stats = ?")
                params.append(json.dumps(stats))

            params.append(name)

            cursor.execute(f"""
                UPDATE collection_metadata
                SET {', '.join(updates)}
                WHERE name = ?
            """, params)

            conn.commit()

            if cursor.rowcount > 0:
                return self.get_collection(name)
            return None
        finally:
            conn.close()

    def delete_collection(self, name: str) -> bool:
        """Delete collection metadata (not the actual ChromaDB collection)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM collection_metadata WHERE name = ?",
                (name,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()

            if deleted:
                logger.info(f"Deleted collection metadata: {name}")

            return deleted
        finally:
            conn.close()

    def _row_to_collection(self, row: sqlite3.Row) -> CollectionMetadata:
        """Convert database row to CollectionMetadata."""
        return CollectionMetadata(
            id=row["id"],
            name=row["name"],
            domain=row["domain"],
            source_type=row["source_type"],
            description=row["description"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            config=json.loads(row["config"]) if row["config"] else None,
            stats=json.loads(row["stats"]) if row["stats"] else None,
        )

    # ==================== Import Job Methods ====================

    def create_import_job(
        self,
        collection_name: str,
        source_type: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> ImportJob:
        """Create a new import job."""
        job = ImportJob(
            id=str(uuid.uuid4()),
            collection_name=collection_name,
            source_type=source_type,
            status=ImportJobStatus.PENDING,
            config=config,
        )

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO import_jobs
                (id, collection_name, source_type, status, progress, total_items,
                 processed_items, error_message, started_at, completed_at, config)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.id,
                job.collection_name,
                job.source_type,
                job.status.value,
                job.progress,
                job.total_items,
                job.processed_items,
                job.error_message,
                job.started_at,
                job.completed_at,
                json.dumps(job.config) if job.config else None,
            ))
            conn.commit()
            logger.info(f"Created import job: {job.id}")
        finally:
            conn.close()

        return job

    def get_import_job(self, job_id: str) -> Optional[ImportJob]:
        """Get import job by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM import_jobs WHERE id = ?",
                (job_id,)
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_import_job(row)
            return None
        finally:
            conn.close()

    def get_import_jobs(
        self,
        collection_name: Optional[str] = None,
        status: Optional[ImportJobStatus] = None,
        limit: int = 50,
    ) -> List[ImportJob]:
        """Get import jobs with optional filters."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            query = "SELECT * FROM import_jobs WHERE 1=1"
            params = []

            if collection_name:
                query += " AND collection_name = ?"
                params.append(collection_name)
            if status:
                query += " AND status = ?"
                params.append(status.value)

            query += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [self._row_to_import_job(row) for row in rows]
        finally:
            conn.close()

    def update_import_job(
        self,
        job_id: str,
        status: Optional[ImportJobStatus] = None,
        progress: Optional[float] = None,
        total_items: Optional[int] = None,
        processed_items: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[ImportJob]:
        """Update import job status and progress."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            updates = []
            params = []

            if status is not None:
                updates.append("status = ?")
                params.append(status.value)

                if status == ImportJobStatus.RUNNING:
                    updates.append("started_at = ?")
                    params.append(datetime.utcnow().isoformat())
                elif status in (ImportJobStatus.COMPLETED, ImportJobStatus.FAILED, ImportJobStatus.CANCELLED):
                    updates.append("completed_at = ?")
                    params.append(datetime.utcnow().isoformat())

            if progress is not None:
                updates.append("progress = ?")
                params.append(progress)
            if total_items is not None:
                updates.append("total_items = ?")
                params.append(total_items)
            if processed_items is not None:
                updates.append("processed_items = ?")
                params.append(processed_items)
            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)

            if not updates:
                return self.get_import_job(job_id)

            params.append(job_id)

            cursor.execute(f"""
                UPDATE import_jobs
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)

            conn.commit()

            if cursor.rowcount > 0:
                return self.get_import_job(job_id)
            return None
        finally:
            conn.close()

    def delete_import_job(self, job_id: str) -> bool:
        """Delete an import job record."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM import_jobs WHERE id = ?",
                (job_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted
        finally:
            conn.close()

    def _row_to_import_job(self, row: sqlite3.Row) -> ImportJob:
        """Convert database row to ImportJob."""
        return ImportJob(
            id=row["id"],
            collection_name=row["collection_name"],
            source_type=row["source_type"],
            status=ImportJobStatus(row["status"]),
            progress=row["progress"],
            total_items=row["total_items"],
            processed_items=row["processed_items"],
            error_message=row["error_message"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            config=json.loads(row["config"]) if row["config"] else None,
        )

    # ==================== Stats ====================

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Total collections
            cursor.execute("SELECT COUNT(*) FROM collection_metadata")
            total_collections = cursor.fetchone()[0]

            # Collections by domain
            cursor.execute("""
                SELECT domain, COUNT(*) as count
                FROM collection_metadata
                GROUP BY domain
            """)
            collections_by_domain = {row["domain"]: row["count"] for row in cursor.fetchall()}

            # Import jobs by status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM import_jobs
                GROUP BY status
            """)
            jobs_by_status = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Running jobs
            cursor.execute("""
                SELECT COUNT(*) FROM import_jobs
                WHERE status = ?
            """, (ImportJobStatus.RUNNING.value,))
            running_jobs = cursor.fetchone()[0]

            return {
                "total_collections": total_collections,
                "collections_by_domain": collections_by_domain,
                "jobs_by_status": jobs_by_status,
                "running_jobs": running_jobs,
                "db_path": self.db_path,
            }
        finally:
            conn.close()

    # ==================== Saved Database Connections ====================

    def save_database_connection(
        self,
        name: str,
        db_type: str,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> SavedDatabaseConnection:
        """
        Save a database connection for reuse.

        Args:
            name: Display name for the connection
            db_type: Database type (mysql, mariadb)
            host: Database host
            port: Database port
            user: Database user
            password: Database password
            database: Database name

        Returns:
            Created SavedDatabaseConnection
        """
        conn_record = SavedDatabaseConnection(
            id=str(uuid.uuid4()),
            name=name,
            db_type=db_type,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO saved_db_connections
                (id, name, db_type, host, port, user, password, database, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conn_record.id,
                conn_record.name,
                conn_record.db_type,
                conn_record.host,
                conn_record.port,
                conn_record.user,
                conn_record.password,
                conn_record.database,
                conn_record.created_at,
            ))
            conn.commit()
            logger.info(f"Saved database connection: {name}")
        finally:
            conn.close()

        return conn_record

    def get_database_connection(self, connection_id: str) -> Optional[SavedDatabaseConnection]:
        """Get saved database connection by ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM saved_db_connections WHERE id = ?",
                (connection_id,)
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_db_connection(row)
            return None
        finally:
            conn.close()

    def get_database_connection_by_name(self, name: str) -> Optional[SavedDatabaseConnection]:
        """Get saved database connection by name."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM saved_db_connections WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()

            if row:
                return self._row_to_db_connection(row)
            return None
        finally:
            conn.close()

    def get_all_database_connections(self) -> List[SavedDatabaseConnection]:
        """Get all saved database connections."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM saved_db_connections
                ORDER BY name
            """)
            rows = cursor.fetchall()
            return [self._row_to_db_connection(row) for row in rows]
        finally:
            conn.close()

    def delete_database_connection(self, connection_id: str) -> bool:
        """Delete a saved database connection."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM saved_db_connections WHERE id = ?",
                (connection_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()

            if deleted:
                logger.info(f"Deleted database connection: {connection_id}")

            return deleted
        finally:
            conn.close()

    def _row_to_db_connection(self, row: sqlite3.Row) -> SavedDatabaseConnection:
        """Convert database row to SavedDatabaseConnection."""
        return SavedDatabaseConnection(
            id=row["id"],
            name=row["name"],
            db_type=row["db_type"],
            host=row["host"],
            port=row["port"],
            user=row["user"],
            password=row["password"],
            database=row["database"],
            created_at=row["created_at"],
        )


# Singleton instance
_collection_metadata_service: Optional[CollectionMetadataService] = None


def get_collection_metadata_service() -> CollectionMetadataService:
    """Get or create the collection metadata service singleton."""
    global _collection_metadata_service
    if _collection_metadata_service is None:
        _collection_metadata_service = CollectionMetadataService()
    return _collection_metadata_service
