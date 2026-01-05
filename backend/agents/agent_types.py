"""Agent Type Definitions for Carmen.help Multi-Agent System"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


class AgentType(Enum):
    LIBRARIAN = "librarian"
    EXPERT = "expert"
    EXECUTOR = "executor"
    VALIDATOR = "validator"


@dataclass
class AgentRole:
    agent_type: AgentType
    name: str
    description: str
    capabilities: List[str]
    temperature: float = 0.3
    max_tokens: int = 2048


@dataclass
class SourceCitation:
    document_id: str
    document_title: str
    document_url: str
    section: Optional[str] = None
    relevance_score: float = 0.0

    def to_markdown(self) -> str:
        if self.section:
            return f"[{self.document_title} - {self.section}]({self.document_url})"
        return f"[{self.document_title}]({self.document_url})"


@dataclass
class AgentResponse:
    agent_type: AgentType
    content: str
    citations: List[SourceCitation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    processing_time_ms: float = 0.0
    context_documents: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationResult:
    is_valid: bool
    confidence_score: float
    original_response: str
    validated_response: str
    citations: List[SourceCitation] = field(default_factory=list)
    claims_verified: int = 0
    claims_flagged: int = 0
    hallucination_warnings: List[str] = field(default_factory=list)


# Agent Role Definitions
AGENT_ROLES = {
    AgentType.LIBRARIAN: AgentRole(
        agent_type=AgentType.LIBRARIAN,
        name="The Librarian",
        description="Information Retrieval Specialist",
        capabilities=["Search vector DB", "Parse Markdown", "Rank relevance"],
        temperature=0.1,
    ),
    AgentType.EXPERT: AgentRole(
        agent_type=AgentType.EXPERT,
        name="The Expert",
        description="Technical Support Specialist",
        capabilities=["Synthesize guides", "Explain concepts", "Troubleshoot"],
        temperature=0.3,
    ),
    AgentType.EXECUTOR: AgentRole(
        agent_type=AgentType.EXECUTOR,
        name="The Executor",
        description="Action-Oriented Assistant",
        capabilities=["Generate JSON", "Create CLI commands", "Code snippets"],
        temperature=0.2,
    ),
    AgentType.VALIDATOR: AgentRole(
        agent_type=AgentType.VALIDATOR,
        name="The Validator",
        description="Quality Guard",
        capabilities=["Verify claims", "Detect hallucinations", "Add citations"],
        temperature=0.1,
    ),
}
