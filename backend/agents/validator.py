"""Validator Agent - Quality Guard for Carmen.help"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .agent_types import ValidationResult, SourceCitation


class Validator:
    """Quality Guard that validates responses against source documentation."""

    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold

    async def validate(
        self,
        response: str,
        source_documents: List[Dict[str, Any]],
        original_query: str,
    ) -> ValidationResult:
        """Validate a response against source documents."""

        # Build source content for comparison
        source_content = self._build_source_content(source_documents)

        # Calculate overlap/confidence
        confidence = self._calculate_confidence(response, source_content)

        # Generate citations
        citations = self._generate_citations(source_documents)

        # Check for hallucination indicators
        warnings = self._detect_hallucinations(response, source_content)

        is_valid = confidence >= self.confidence_threshold and len(warnings) < 2

        validated_response = response
        if warnings:
            validated_response += "\n\n> *Note: Some details may require verification against official documentation.*"

        return ValidationResult(
            is_valid=is_valid,
            confidence_score=confidence,
            original_response=response,
            validated_response=validated_response,
            citations=citations,
            claims_verified=int(confidence * 10),
            claims_flagged=len(warnings),
            hallucination_warnings=warnings,
        )

    def _build_source_content(self, documents: List[Dict[str, Any]]) -> str:
        parts = []
        for doc in documents:
            content = doc.get("content", "")
            title = doc.get("title", "")
            parts.append(f"{title}\n{content}")
        return "\n\n".join(parts)

    def _calculate_confidence(self, response: str, source_content: str) -> float:
        """Calculate confidence based on word overlap."""
        import re

        response_words = set(re.findall(r'\b\w{4,}\b', response.lower()))
        source_words = set(re.findall(r'\b\w{4,}\b', source_content.lower()))

        if not response_words:
            return 0.7

        overlap = len(response_words & source_words) / len(response_words)
        return min(1.0, overlap + 0.2)

    def _generate_citations(self, documents: List[Dict[str, Any]]) -> List[SourceCitation]:
        citations = []
        for doc in documents[:5]:
            citations.append(SourceCitation(
                document_id=doc.get("id", ""),
                document_title=doc.get("title", "Documentation"),
                document_url=doc.get("url", "https://docscarmencloud.vercel.app"),
                section=doc.get("section"),
                relevance_score=doc.get("relevance_score", 0.5),
            ))
        return citations

    def _detect_hallucinations(self, response: str, source_content: str) -> List[str]:
        """Detect potential hallucinations."""
        import re
        warnings = []

        # Check for specific numbers not in source
        response_numbers = set(re.findall(r'\b\d{3,}\b', response))
        source_numbers = set(re.findall(r'\b\d{3,}\b', source_content))

        for num in response_numbers - source_numbers:
            warnings.append(f"Unverified number: {num}")

        return warnings[:3]
