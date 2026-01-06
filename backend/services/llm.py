"""
LLM Service module for Z.ai integration.
Uses OpenAI-compatible SDK to communicate with Z.ai API.
"""

from typing import AsyncGenerator, Optional, List, Dict, Any
from dataclasses import dataclass
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings


@dataclass
class LLMResponse:
    """Response from the LLM with usage statistics."""
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    response_time_ms: float = 0.0


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
    ) -> LLMResponse:
        """Generate a non-streaming response from the LLM."""
        start_time = time.time()
        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                stream=False,
            )
            elapsed_ms = (time.time() - start_time) * 1000

            # Extract token usage
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0

            return LLMResponse(
                content=response.choices[0].message.content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                response_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            print(f"LLM Error: {e}")
            return LLMResponse(
                content=f"I apologize, but I'm unable to process your request. Please ensure your Z.ai API key is configured correctly. Error: {str(e)}",
                response_time_ms=elapsed_ms,
            )

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate a streaming response from the LLM.

        Yields dictionaries with 'content' for text chunks and 'stats' for final usage.
        """
        start_time = time.time()
        total_content = ""
        try:
            client = self._get_client()
            stream = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                stream=True,
                stream_options={"include_usage": True},
            )

            prompt_tokens = 0
            completion_tokens = 0

            async for chunk in stream:
                # Check for usage stats (sent at the end with stream_options)
                if hasattr(chunk, 'usage') and chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens or 0
                    completion_tokens = chunk.usage.completion_tokens or 0

                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    total_content += content
                    yield {"type": "content", "content": content}

            # Send final stats
            elapsed_ms = (time.time() - start_time) * 1000
            yield {
                "type": "stats",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "response_time_ms": elapsed_ms,
            }
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            print(f"LLM Stream Error: {e}")
            yield {"type": "content", "content": f"Error: Unable to connect to LLM service. {str(e)}"}
            yield {"type": "stats", "response_time_ms": elapsed_ms, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

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
