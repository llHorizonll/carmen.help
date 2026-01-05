"""
LLM Service module for Z.ai integration.
Uses OpenAI-compatible SDK to communicate with Z.ai API.
"""

from typing import AsyncGenerator, Optional, List, Dict, Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings


class LLMService:
    """Service class for interacting with Z.ai LLM using OpenAI-compatible API."""

    def __init__(self):
        """Initialize the LLM service with Z.ai configuration."""
        self.model = settings.zai_model
        self.max_tokens = settings.zai_max_tokens
        self.temperature = settings.zai_temperature
        self._client = None

    def _get_client(self):
        """Lazy initialize OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI

            api_key = settings.zai_api_key
            if not api_key:
                api_key = "dummy-key-for-testing"
                print("Warning: ZAI_API_KEY not set. LLM calls will fail.")

            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=settings.zai_api_base,
            )
        return self._client

    async def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate a non-streaming response from the LLM."""
        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                stream=False,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM Error: {e}")
            return f"I apologize, but I'm unable to process your request. Please ensure your Z.ai API key is configured correctly. Error: {str(e)}"

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response from the LLM."""
        try:
            client = self._get_client()
            stream = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"LLM Stream Error: {e}")
            yield f"Error: Unable to connect to LLM service. {str(e)}"

    def build_rag_prompt(self, context: str) -> str:
        """Build a system prompt with RAG context."""
        if not context:
            return """You are Carmen AI Assistant, a helpful support agent for Carmen Cloud.
You help users with questions about Carmen Cloud. Since no specific documentation was found,
provide general helpful guidance and suggest checking the official documentation
at https://docscarmencloud.vercel.app for detailed information."""

        return f"""You are Carmen AI Assistant, a helpful support agent for Carmen Cloud.
You provide accurate, helpful responses based on the Carmen Cloud documentation.

DOCUMENTATION CONTEXT:
{context}

INSTRUCTIONS:
- Answer questions based primarily on the provided documentation context
- Be concise but thorough in your explanations
- If uncertain, say so clearly and suggest checking the official documentation
- Always cite which documentation section your answer is based on
- If the question cannot be answered from the context, acknowledge this
- Include links to https://docscarmencloud.vercel.app when relevant
- Maintain a friendly, professional tone"""


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
