"""
Database Ingestor for importing data from MySQL/MariaDB databases.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import pymysql
import pymysql.cursors

from .base import BaseIngestor, IngestorConfig, IngestedChunk, SourceType


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    db_type: str  # "mysql", "mariadb"
    host: str
    port: int
    user: str
    password: str
    database: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excludes password for logging)."""
        return {
            "db_type": self.db_type,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "database": self.database,
        }


class DatabaseConnection:
    """Context manager for database connections."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection = None

    def __enter__(self):
        self.connection = pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset='utf8mb4',
            use_unicode=True,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
        )
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()


def test_database_connection(config: DatabaseConfig) -> tuple[bool, str]:
    """
    Test database connection.

    Returns:
        Tuple of (success, message)
    """
    try:
        with DatabaseConnection(config) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True, "Connection successful"
    except pymysql.Error as e:
        return False, f"Connection failed: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def list_database_tables(config: DatabaseConfig) -> List[Dict[str, Any]]:
    """
    List all tables in the database with row counts.

    Returns:
        List of dicts with 'name' and 'row_count'
    """
    tables = []
    try:
        with DatabaseConnection(config) as conn:
            with conn.cursor() as cursor:
                # Get tables
                cursor.execute("SHOW TABLES")
                raw_names = cursor.fetchall()
                table_names = []
                for row in raw_names:
                    name = list(row.values())[0]
                    # Ensure table name is a string
                    if isinstance(name, bytes):
                        name = name.decode('utf-8')
                    table_names.append(name)

                # Get row counts
                for table_name in table_names:
                    try:
                        cursor.execute(f"SELECT COUNT(*) as cnt FROM `{table_name}`")
                        result = cursor.fetchone()
                        row_count = result['cnt'] if result else 0
                    except:
                        row_count = 0

                    tables.append({
                        "name": table_name,
                        "row_count": row_count,
                    })
    except Exception as e:
        raise Exception(f"Failed to list tables: {str(e)}")

    return tables


def get_table_columns(config: DatabaseConfig, table_name: str) -> List[Dict[str, Any]]:
    """
    Get columns for a table with type info.

    Returns:
        List of dicts with 'name', 'type', 'nullable', 'is_text'
    """
    columns = []
    text_types = ['char', 'varchar', 'text', 'tinytext', 'mediumtext', 'longtext', 'enum', 'set']

    try:
        with DatabaseConnection(config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"DESCRIBE `{table_name}`")
                for row in cursor.fetchall():
                    # Ensure values are strings
                    field_name = row['Field']
                    if isinstance(field_name, bytes):
                        field_name = field_name.decode('utf-8')

                    field_type = row['Type']
                    if isinstance(field_type, bytes):
                        field_type = field_type.decode('utf-8')

                    col_type = field_type.lower()
                    is_text = any(t in col_type for t in text_types)

                    columns.append({
                        "name": field_name,
                        "type": field_type,
                        "nullable": row['Null'] == 'YES',
                        "is_text": is_text,
                        "is_key": row['Key'] == 'PRI',
                    })
    except Exception as e:
        raise Exception(f"Failed to get columns: {str(e)}")

    return columns


def _ensure_json_serializable(value: Any) -> Any:
    """Convert value to JSON-serializable format."""
    if value is None:
        return None
    if isinstance(value, bytes):
        # Decode bytes to string
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            return value.decode('utf-8', errors='replace')
    if hasattr(value, 'isoformat'):
        # Handle datetime
        return value.isoformat()
    if isinstance(value, (int, float, bool, str)):
        return value
    # Convert other types to string
    return str(value)


def preview_table_data(
    config: DatabaseConfig,
    table_name: str,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Preview table data.

    Returns:
        Dict with 'columns', 'rows', 'total_count'
    """
    try:
        with DatabaseConnection(config) as conn:
            with conn.cursor() as cursor:
                # Get total count
                cursor.execute(f"SELECT COUNT(*) as cnt FROM `{table_name}`")
                total_count = cursor.fetchone()['cnt']

                # Get sample rows
                cursor.execute(f"SELECT * FROM `{table_name}` LIMIT {limit}")
                raw_rows = cursor.fetchall()

                # Ensure all values are JSON-serializable
                rows = []
                for row in raw_rows:
                    clean_row = {}
                    for key, value in row.items():
                        clean_row[key] = _ensure_json_serializable(value)
                    rows.append(clean_row)

                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []

                return {
                    "columns": columns,
                    "rows": rows,
                    "total_count": total_count,
                }
    except Exception as e:
        raise Exception(f"Failed to preview data: {str(e)}")


class DatabaseIngestor(BaseIngestor):
    """Ingest data from MySQL/MariaDB database tables."""

    def __init__(
        self,
        config: IngestorConfig,
        db_config: DatabaseConfig,
        table_name: str,
        content_columns: List[str],
        metadata_columns: Optional[List[str]] = None,
        where_clause: Optional[str] = None,
        combine_separator: str = "\n\n",
    ):
        """
        Initialize database ingestor.

        Args:
            config: Ingestor configuration
            db_config: Database connection configuration
            table_name: Table to import from
            content_columns: Columns to use as searchable content
            metadata_columns: Columns to store as metadata
            where_clause: Optional SQL WHERE clause (without 'WHERE' keyword)
            combine_separator: Separator for combining multiple content columns
        """
        super().__init__(config)
        self.db_config = db_config
        self.table_name = table_name
        self.content_columns = content_columns
        self.metadata_columns = metadata_columns or []
        self.where_clause = where_clause
        self.combine_separator = combine_separator

    def validate_source(self, source: Any) -> bool:
        """Validate database connection."""
        success, _ = test_database_connection(self.db_config)
        return success

    async def ingest(self, source: Any = None) -> List[IngestedChunk]:
        """
        Ingest data from database table.

        Args:
            source: Not used for database ingestion (uses db_config)

        Returns:
            List of IngestedChunk objects
        """
        all_chunks = []

        # Build SELECT columns
        select_columns = list(set(self.content_columns + self.metadata_columns))
        columns_sql = ", ".join([f"`{col}`" for col in select_columns])

        # Build query
        query = f"SELECT {columns_sql} FROM `{self.table_name}`"
        if self.where_clause:
            query += f" WHERE {self.where_clause}"

        try:
            with DatabaseConnection(self.db_config) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)

                    row_num = 0
                    for row in cursor.fetchall():
                        row_num += 1

                        # Build content from content columns
                        content_parts = []
                        for col in self.content_columns:
                            value = row.get(col)
                            if value is not None:
                                # Ensure value is a string
                                if isinstance(value, bytes):
                                    value = value.decode('utf-8', errors='replace')
                                # Format as "Column: Value" for better context
                                content_parts.append(f"{col}: {value}")

                        content = self.combine_separator.join(content_parts)

                        if not content.strip():
                            continue

                        # Build metadata
                        metadata = {
                            "source_table": self.table_name,
                            "source_database": self.db_config.database,
                            "row_number": row_num,
                        }

                        for col in self.metadata_columns:
                            value = row.get(col)
                            if value is not None:
                                # Ensure value is JSON-serializable
                                if isinstance(value, bytes):
                                    value = value.decode('utf-8', errors='replace')
                                elif hasattr(value, 'isoformat'):
                                    value = value.isoformat()
                                metadata[col] = value

                        # Chunk the content
                        source_id = f"{self.table_name}:row_{row_num}"
                        chunks = self.chunk_text(content, source_id)

                        # Add metadata to each chunk
                        for chunk in chunks:
                            chunk.metadata.update(metadata)
                            all_chunks.append(chunk)

        except Exception as e:
            raise Exception(f"Database ingestion failed: {str(e)}")

        return all_chunks


class AutoDetectDatabaseIngestor(DatabaseIngestor):
    """
    Database ingestor that auto-detects text columns for content.
    """

    def __init__(
        self,
        config: IngestorConfig,
        db_config: DatabaseConfig,
        table_name: str,
        where_clause: Optional[str] = None,
        include_non_text_in_metadata: bool = True,
    ):
        """
        Initialize with auto-detection of text columns.

        Args:
            config: Ingestor configuration
            db_config: Database connection configuration
            table_name: Table to import from
            where_clause: Optional SQL WHERE clause
            include_non_text_in_metadata: Include non-text columns as metadata
        """
        # Get columns and auto-detect text columns
        columns = get_table_columns(db_config, table_name)

        content_columns = [c['name'] for c in columns if c['is_text']]
        metadata_columns = []

        if include_non_text_in_metadata:
            metadata_columns = [c['name'] for c in columns if not c['is_text'] and not c['is_key']]

        # Add primary key to metadata
        key_columns = [c['name'] for c in columns if c['is_key']]
        metadata_columns = key_columns + metadata_columns

        super().__init__(
            config=config,
            db_config=db_config,
            table_name=table_name,
            content_columns=content_columns,
            metadata_columns=metadata_columns,
            where_clause=where_clause,
        )
