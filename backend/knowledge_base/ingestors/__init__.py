"""
Data ingestors for importing content from various sources into ChromaDB collections.

Supported sources:
- CSV files
- Database connections (PostgreSQL, MySQL, SQLite)
- URL/API fetching
"""

from .base import (
    BaseIngestor,
    IngestorConfig,
    IngestedChunk,
    SourceType,
    IngestionResult,
)
from .csv_ingestor import CSVIngestor, USALICSVIngestor
from .database_ingestor import (
    DatabaseConfig,
    DatabaseIngestor,
    AutoDetectDatabaseIngestor,
    test_database_connection,
    list_database_tables,
    get_table_columns,
    preview_table_data,
)

__all__ = [
    "BaseIngestor",
    "IngestorConfig",
    "IngestedChunk",
    "SourceType",
    "IngestionResult",
    "CSVIngestor",
    "USALICSVIngestor",
    "DatabaseConfig",
    "DatabaseIngestor",
    "AutoDetectDatabaseIngestor",
    "test_database_connection",
    "list_database_tables",
    "get_table_columns",
    "preview_table_data",
]
