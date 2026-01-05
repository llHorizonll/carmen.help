"""
Carmen.help Multi-Agent System

Manager-Worker pattern with four specialized agents:
- Librarian: Documentation retrieval
- Expert: Synthesizes step-by-step guides
- Executor: Generates JSON payloads/CLI commands
- Validator: Reviews responses for accuracy
"""

from .agent_types import AgentType, AgentRole, AgentResponse, ValidationResult
from .prompts import (
    LIBRARIAN_SYSTEM_PROMPT,
    EXPERT_SYSTEM_PROMPT,
    EXECUTOR_SYSTEM_PROMPT,
    VALIDATOR_SYSTEM_PROMPT,
)

__all__ = [
    "AgentType",
    "AgentRole",
    "AgentResponse",
    "ValidationResult",
    "LIBRARIAN_SYSTEM_PROMPT",
    "EXPERT_SYSTEM_PROMPT",
    "EXECUTOR_SYSTEM_PROMPT",
    "VALIDATOR_SYSTEM_PROMPT",
]
