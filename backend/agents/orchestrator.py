"""Orchestrator - Multi-Agent Coordinator for Carmen.help"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from .agent_types import AgentType, AgentResponse, SourceCitation
from .prompts import LIBRARIAN_SYSTEM_PROMPT, EXPERT_SYSTEM_PROMPT, EXECUTOR_SYSTEM_PROMPT
from .validator import Validator


class Orchestrator:
    """Manager that coordinates the multi-agent system."""

    def __init__(
        self,
        llm_client,
        vector_db,
        enable_validation: bool = True,
    ):
        self.llm_client = llm_client
        self.vector_db = vector_db
        self.enable_validation = enable_validation
        self.validator = Validator()

    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process a user query through the multi-agent system."""
        start_time = datetime.utcnow()

        # Step 1: Librarian retrieves documents
        documents = await self._retrieve_documents(query)

        # Step 2: Expert synthesizes response
        context = self._format_documents(documents)
        response = await self._generate_expert_response(query, context)

        # Step 3: Check if Executor is needed
        if self._needs_executor(query):
            executor_response = await self._generate_executor_response(query, response)
            response = f"{response}\n\n---\n\n## Executable Action\n\n{executor_response}"

        # Step 4: Validate response
        citations = []
        if self.enable_validation:
            validation = await self.validator.validate(response, documents, query)
            response = validation.validated_response
            citations = validation.citations

        end_time = datetime.utcnow()

        return {
            "success": True,
            "response": response,
            "citations": [c.to_markdown() for c in citations],
            "processing_time_ms": (end_time - start_time).total_seconds() * 1000,
        }

    async def _retrieve_documents(self, query: str) -> List[Dict[str, Any]]:
        """Retrieve relevant documents from vector DB."""
        results = await self.vector_db.search(query=query, top_k=5)
        return results

    def _format_documents(self, documents: List[Dict[str, Any]]) -> str:
        parts = []
        for i, doc in enumerate(documents):
            parts.append(f"[{i+1}] {doc.get('title', 'Document')}\n{doc.get('content', '')}")
        return "\n\n---\n\n".join(parts)

    async def _generate_expert_response(self, query: str, context: str) -> str:
        """Generate Expert agent response."""
        messages = [
            {"role": "system", "content": EXPERT_SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {query}\n\nDocumentation:\n{context}"},
        ]
        return await self.llm_client.chat_completion(messages=messages)

    async def _generate_executor_response(self, query: str, expert_context: str) -> str:
        """Generate Executor agent response."""
        messages = [
            {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT},
            {"role": "user", "content": f"Request: {query}\n\nContext:\n{expert_context}"},
        ]
        return await self.llm_client.chat_completion(messages=messages)

    def _needs_executor(self, query: str) -> bool:
        """Check if query needs Executor agent."""
        action_keywords = ["api", "curl", "json", "command", "cli", "create", "delete", "update"]
        return any(kw in query.lower() for kw in action_keywords)
