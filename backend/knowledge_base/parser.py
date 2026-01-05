"""
Markdown Parser

Parses Markdown and MDX files into semantic chunks split by headers.
Each chunk includes metadata about the source file and section.
"""

import re
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Generator
import logging

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """
    Represents a chunk of documentation content.
    """

    content: str
    source_file: str
    section_title: str
    header_level: int
    parent_sections: list[str] = field(default_factory=list)
    chunk_id: str = ""
    start_line: int = 0
    end_line: int = 0

    def __post_init__(self):
        """Generate chunk ID if not provided."""
        if not self.chunk_id:
            # Create a unique ID based on content, location, and line numbers
            unique_str = f"{self.source_file}:{self.section_title}:{self.start_line}:{self.end_line}:{self.content}"
            content_hash = hashlib.md5(unique_str.encode()).hexdigest()[:16]
            self.chunk_id = f"chunk_{content_hash}"

    @property
    def full_path(self) -> str:
        """Get the full section path including parent sections."""
        if self.parent_sections:
            return " > ".join(self.parent_sections + [self.section_title])
        return self.section_title

    def to_dict(self) -> dict:
        """Convert chunk to dictionary for storage."""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "source_file": self.source_file,
            "section_title": self.section_title,
            "full_path": self.full_path,
            "header_level": self.header_level,
            "parent_sections": self.parent_sections,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


class MarkdownParser:
    """
    Parses Markdown and MDX files into semantic chunks.
    """

    # Regex patterns for parsing
    HEADER_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    MDX_IMPORT_PATTERN = re.compile(r"^import\s+.+$", re.MULTILINE)
    MDX_EXPORT_PATTERN = re.compile(r"^export\s+.+$", re.MULTILINE)
    CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)

    def __init__(
        self,
        min_chunk_size: int = 50,
        max_chunk_size: int = 2000,
        split_on_headers: list[int] = None,
        include_code_blocks: bool = True,
    ):
        """
        Initialize the parser.

        Args:
            min_chunk_size: Minimum characters for a valid chunk
            max_chunk_size: Maximum characters before forcing a split
            split_on_headers: Header levels to split on (default: [2, 3])
            include_code_blocks: Whether to include code blocks in chunks
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.split_on_headers = split_on_headers or [2, 3]
        self.include_code_blocks = include_code_blocks

    def _extract_frontmatter(self, content: str) -> tuple[dict, str]:
        """
        Extract YAML frontmatter from content.

        Returns:
            Tuple of (frontmatter_dict, content_without_frontmatter)
        """
        match = self.FRONTMATTER_PATTERN.match(content)
        if not match:
            return {}, content

        frontmatter_text = match.group(1)
        remaining_content = content[match.end():]

        # Simple YAML parsing (key: value pairs)
        frontmatter = {}
        for line in frontmatter_text.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip().strip('"\'')

        return frontmatter, remaining_content

    def _clean_mdx_content(self, content: str) -> str:
        """
        Remove MDX-specific syntax that isn't useful for embeddings.
        """
        # Remove import statements
        content = self.MDX_IMPORT_PATTERN.sub("", content)
        # Remove export statements (but keep exported content)
        content = self.MDX_EXPORT_PATTERN.sub("", content)
        # Remove JSX component tags (simplified)
        content = re.sub(r"<[A-Z][a-zA-Z]*[^>]*/>", "", content)
        content = re.sub(r"<[A-Z][a-zA-Z]*[^>]*>.*?</[A-Z][a-zA-Z]*>", "", content, flags=re.DOTALL)

        return content

    def _find_headers(self, content: str) -> list[tuple[int, int, str, int]]:
        """
        Find all headers in the content.

        Returns:
            List of (line_number, header_level, header_text, char_position)
        """
        headers = []
        lines = content.split("\n")
        char_pos = 0

        for line_num, line in enumerate(lines):
            match = self.HEADER_PATTERN.match(line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                headers.append((line_num, level, title, char_pos))
            char_pos += len(line) + 1  # +1 for newline

        return headers

    def _split_content_by_headers(
        self, content: str, source_file: str
    ) -> list[DocumentChunk]:
        """
        Split content into chunks based on header hierarchy.
        """
        chunks = []
        lines = content.split("\n")
        headers = self._find_headers(content)

        if not headers:
            # No headers found, treat entire content as one chunk
            clean_content = content.strip()
            if len(clean_content) >= self.min_chunk_size:
                chunks.append(
                    DocumentChunk(
                        content=clean_content,
                        source_file=source_file,
                        section_title="Document",
                        header_level=0,
                        start_line=0,
                        end_line=len(lines),
                    )
                )
            return chunks

        # Track parent sections for hierarchy
        section_stack: list[tuple[int, str]] = []  # (level, title)

        for i, (line_num, level, title, _) in enumerate(headers):
            # Determine end line (start of next header or end of file)
            if i + 1 < len(headers):
                end_line = headers[i + 1][0]
            else:
                end_line = len(lines)

            # Update section stack for hierarchy
            while section_stack and section_stack[-1][0] >= level:
                section_stack.pop()

            parent_sections = [s[1] for s in section_stack]

            # Only create chunks for headers at specified levels
            if level in self.split_on_headers:
                # Extract content for this section
                section_lines = lines[line_num:end_line]
                section_content = "\n".join(section_lines).strip()

                # Skip if content is too small
                if len(section_content) >= self.min_chunk_size:
                    # Handle oversized chunks
                    if len(section_content) > self.max_chunk_size:
                        sub_chunks = self._split_large_chunk(
                            section_content,
                            source_file,
                            title,
                            level,
                            parent_sections,
                            line_num,
                        )
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append(
                            DocumentChunk(
                                content=section_content,
                                source_file=source_file,
                                section_title=title,
                                header_level=level,
                                parent_sections=parent_sections.copy(),
                                start_line=line_num,
                                end_line=end_line,
                            )
                        )

            # Add to stack for child sections
            section_stack.append((level, title))

        return chunks

    def _split_large_chunk(
        self,
        content: str,
        source_file: str,
        title: str,
        level: int,
        parent_sections: list[str],
        start_line: int,
    ) -> list[DocumentChunk]:
        """
        Split an oversized chunk into smaller pieces.
        """
        chunks = []
        paragraphs = content.split("\n\n")

        current_chunk = ""
        chunk_num = 1

        for para in paragraphs:
            if len(current_chunk) + len(para) > self.max_chunk_size:
                if current_chunk:
                    chunks.append(
                        DocumentChunk(
                            content=current_chunk.strip(),
                            source_file=source_file,
                            section_title=f"{title} (Part {chunk_num})",
                            header_level=level,
                            parent_sections=parent_sections.copy(),
                            start_line=start_line,
                            end_line=start_line,  # Approximate
                        )
                    )
                    chunk_num += 1
                current_chunk = para
            else:
                current_chunk = current_chunk + "\n\n" + para if current_chunk else para

        # Add remaining content
        if current_chunk and len(current_chunk.strip()) >= self.min_chunk_size:
            chunks.append(
                DocumentChunk(
                    content=current_chunk.strip(),
                    source_file=source_file,
                    section_title=f"{title} (Part {chunk_num})" if chunk_num > 1 else title,
                    header_level=level,
                    parent_sections=parent_sections.copy(),
                    start_line=start_line,
                    end_line=start_line,
                )
            )

        return chunks

    def parse_file(self, file_path: Path) -> list[DocumentChunk]:
        """
        Parse a single Markdown or MDX file into chunks.

        Args:
            file_path: Path to the file to parse

        Returns:
            List of DocumentChunk objects
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return []

        # Extract frontmatter
        frontmatter, content = self._extract_frontmatter(content)

        # Clean MDX content if applicable
        if file_path.suffix.lower() == ".mdx":
            content = self._clean_mdx_content(content)

        # Get relative path for source reference
        source_file = str(file_path)

        # Split into chunks
        chunks = self._split_content_by_headers(content, source_file)

        # Add frontmatter metadata to chunks if available
        if frontmatter:
            for chunk in chunks:
                if "title" in frontmatter and chunk.section_title == "Document":
                    chunk.section_title = frontmatter["title"]

        logger.debug(f"Parsed {file_path}: {len(chunks)} chunks")
        return chunks

    def parse_directory(
        self,
        directory: Path,
        recursive: bool = True,
    ) -> Generator[DocumentChunk, None, None]:
        """
        Parse all Markdown/MDX files in a directory.

        Args:
            directory: Directory to parse
            recursive: Whether to search recursively

        Yields:
            DocumentChunk objects
        """
        if not directory.exists():
            logger.error(f"Directory does not exist: {directory}")
            return

        pattern = "**/*.md*" if recursive else "*.md*"

        for file_path in directory.glob(pattern):
            if file_path.suffix.lower() in [".md", ".mdx"]:
                chunks = self.parse_file(file_path)
                for chunk in chunks:
                    yield chunk

    def parse_all(self, directory: Path, recursive: bool = True) -> list[DocumentChunk]:
        """
        Parse all files and return as a list.

        Args:
            directory: Directory to parse
            recursive: Whether to search recursively

        Returns:
            List of all DocumentChunk objects
        """
        return list(self.parse_directory(directory, recursive))


def main():
    """
    Main entry point for parsing documentation.
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Parse Markdown/MDX files into chunks"
    )
    parser.add_argument(
        "path",
        help="File or directory to parse",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file for chunks (JSON format)",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=50,
        help="Minimum chunk size in characters",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=2000,
        help="Maximum chunk size in characters",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Create parser
    md_parser = MarkdownParser(
        min_chunk_size=args.min_size,
        max_chunk_size=args.max_size,
    )

    # Parse
    path = Path(args.path)
    if path.is_file():
        chunks = md_parser.parse_file(path)
    else:
        chunks = md_parser.parse_all(path)

    # Output results
    print(f"\nParsed {len(chunks)} chunks:")
    for chunk in chunks:
        print(f"  - {chunk.section_title} ({len(chunk.content)} chars)")
        print(f"    Source: {chunk.source_file}")
        if chunk.parent_sections:
            print(f"    Path: {chunk.full_path}")

    # Save to file if requested
    if args.output:
        output_data = [chunk.to_dict() for chunk in chunks]
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
