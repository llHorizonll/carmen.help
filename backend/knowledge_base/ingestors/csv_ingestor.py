"""
CSV file ingestor for importing tabular data into ChromaDB collections.
"""

import csv
import io
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

from .base import BaseIngestor, IngestorConfig, IngestedChunk, SourceType


class CSVIngestor(BaseIngestor):
    """
    Ingest data from CSV files.

    Supports:
    - File path or file content (string/bytes)
    - Configurable column mapping for content and metadata
    - Multiple content columns combined into single text
    - Custom delimiters and quote characters
    """

    def __init__(
        self,
        config: IngestorConfig,
        content_columns: List[str],
        metadata_columns: Optional[List[str]] = None,
        delimiter: str = ",",
        quotechar: str = '"',
        combine_separator: str = "\n\n",
        row_template: Optional[str] = None,
    ):
        """
        Initialize CSV ingestor.

        Args:
            config: Ingestion configuration
            content_columns: Column names to use for content (will be combined)
            metadata_columns: Column names to store as metadata
            delimiter: CSV delimiter character
            quotechar: CSV quote character
            combine_separator: Separator when combining multiple content columns
            row_template: Optional template for formatting row content.
                         Use {column_name} placeholders.
                         Example: "Question: {question}\nAnswer: {answer}"
        """
        super().__init__(config)
        self.content_columns = content_columns
        self.metadata_columns = metadata_columns or []
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.combine_separator = combine_separator
        self.row_template = row_template

    def validate_source(self, source: Any) -> bool:
        """Validate CSV source (file path or content)."""
        if isinstance(source, (str, Path)):
            path = Path(source)
            if path.exists():
                return path.suffix.lower() == ".csv"
            # Might be CSV content string
            return True
        elif isinstance(source, bytes):
            return True
        elif hasattr(source, "read"):
            return True
        return False

    def _validate_columns(self, csv_columns: List[str]) -> tuple:
        """Validate that specified columns exist in CSV (case-insensitive)."""
        csv_cols_lower = {col.lower().strip(): col for col in csv_columns}
        missing_content = []
        missing_metadata = []

        for col in self.content_columns:
            if col.lower().strip() not in csv_cols_lower:
                missing_content.append(col)

        for col in self.metadata_columns:
            if col.lower().strip() not in csv_cols_lower:
                missing_metadata.append(col)

        return missing_content, missing_metadata

    async def ingest(self, source: Union[str, bytes, Path]) -> List[IngestedChunk]:
        """
        Ingest CSV data and return chunks.

        Args:
            source: File path, CSV content string, or bytes

        Returns:
            List of IngestedChunk objects
        """
        # Get CSV reader from source
        reader, source_name = self._get_reader(source)

        chunks = []
        row_num = 0
        first_row_checked = False

        for row in reader:
            row_num += 1

            # Validate columns on first row
            if not first_row_checked:
                first_row_checked = True
                missing_content, missing_metadata = self._validate_columns(list(row.keys()))
                if missing_content:
                    available_cols = ", ".join(row.keys())
                    raise ValueError(
                        f"Content columns not found in CSV: {', '.join(missing_content)}. "
                        f"Available columns: {available_cols}"
                    )

            # Build content from specified columns
            content = self._build_content(row)
            if not content or len(content.strip()) < self.config.min_chunk_size:
                continue

            # Build metadata from specified columns
            metadata = self._build_metadata(row, row_num, source_name)

            # Create chunk(s) - may split if content is too long
            row_chunks = self.chunk_text(content, f"{source_name}:row{row_num}")

            # Add row metadata to each chunk
            for chunk in row_chunks:
                chunk.metadata.update(metadata)

            chunks.extend(row_chunks)

        return chunks

    def _get_reader(self, source: Union[str, bytes, Path]) -> tuple:
        """Get CSV reader and source name from various input types."""
        if isinstance(source, Path):
            source = str(source)

        if isinstance(source, str):
            path = Path(source)
            if path.exists():
                # File path
                with open(path, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                source_name = path.name
            else:
                # CSV content string
                content = source
                source_name = "csv_content"
        elif isinstance(source, bytes):
            content = source.decode("utf-8-sig")
            source_name = "csv_bytes"
        elif hasattr(source, "read"):
            content = source.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8-sig")
            source_name = getattr(source, "name", "csv_file")
        else:
            raise ValueError(f"Unsupported source type: {type(source)}")

        reader = csv.DictReader(
            io.StringIO(content),
            delimiter=self.delimiter,
            quotechar=self.quotechar,
        )

        return reader, source_name

    def _get_column_value(self, row: Dict[str, str], col_name: str) -> str:
        """Get column value with case-insensitive matching."""
        # Try exact match first
        if col_name in row:
            return row[col_name]

        # Try case-insensitive match
        col_lower = col_name.lower().strip()
        for key in row.keys():
            if key.lower().strip() == col_lower:
                return row[key]

        return ""

    def _build_content(self, row: Dict[str, str]) -> str:
        """Build content string from row data."""
        if self.row_template:
            # Use template formatting
            try:
                return self.row_template.format(**row)
            except KeyError as e:
                # Missing column in template
                return ""

        # Combine content columns
        parts = []
        for col in self.content_columns:
            value = self._get_column_value(row, col).strip()
            if value:
                if len(self.content_columns) > 1:
                    # Include column name for context
                    parts.append(f"{col}: {value}")
                else:
                    parts.append(value)

        return self.combine_separator.join(parts)

    def _build_metadata(
        self, row: Dict[str, str], row_num: int, source_name: str
    ) -> Dict[str, Any]:
        """Build metadata dict from row data."""
        metadata = {
            "source_file": source_name,
            "row_number": row_num,
            "source_type": SourceType.CSV.value,
        }

        for col in self.metadata_columns:
            value = self._get_column_value(row, col)
            if value:
                metadata[col] = value

        return metadata


class USALICSVIngestor(CSVIngestor):
    """
    Specialized CSV ingestor for USALI (Uniform System of Accounts for the Lodging Industry) data.

    Expects columns like:
    - account_code: USALI account code (e.g., "4100")
    - account_name: Account name (e.g., "Rooms Revenue")
    - category: Category (e.g., "Revenue", "Expense")
    - department: Department (e.g., "Rooms", "F&B")
    - description: Detailed description
    """

    def __init__(
        self,
        config: IngestorConfig,
        account_code_column: str = "account_code",
        account_name_column: str = "account_name",
        description_column: str = "description",
        category_column: Optional[str] = "category",
        department_column: Optional[str] = "department",
    ):
        # Build content template for USALI format
        template_parts = [
            f"USALI Account: {{{account_code_column}}} - {{{account_name_column}}}",
        ]

        if category_column:
            template_parts.append(f"Category: {{{category_column}}}")
        if department_column:
            template_parts.append(f"Department: {{{department_column}}}")

        template_parts.append(f"Description: {{{description_column}}}")

        row_template = "\n".join(template_parts)

        # Metadata columns
        metadata_cols = [account_code_column, account_name_column]
        if category_column:
            metadata_cols.append(category_column)
        if department_column:
            metadata_cols.append(department_column)

        super().__init__(
            config=config,
            content_columns=[description_column],
            metadata_columns=metadata_cols,
            row_template=row_template,
        )

        self.account_code_column = account_code_column
        self.account_name_column = account_name_column

    def _build_metadata(
        self, row: Dict[str, str], row_num: int, source_name: str
    ) -> Dict[str, Any]:
        """Build USALI-specific metadata."""
        metadata = super()._build_metadata(row, row_num, source_name)

        # Add USALI-specific fields
        account_code = row.get(self.account_code_column, "")
        if account_code:
            metadata["usali_code"] = account_code

            # Categorize by code prefix
            if account_code.startswith("4"):
                metadata["usali_type"] = "revenue"
            elif account_code.startswith("5"):
                metadata["usali_type"] = "cost_of_sales"
            elif account_code.startswith("6"):
                metadata["usali_type"] = "labor"
            elif account_code.startswith("7"):
                metadata["usali_type"] = "other_expense"
            elif account_code.startswith("8"):
                metadata["usali_type"] = "undistributed"
            elif account_code.startswith("9"):
                metadata["usali_type"] = "fixed_charges"

        return metadata
