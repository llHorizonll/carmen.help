"""
LLM Service module for Z.ai integration.
Uses OpenAI-compatible SDK to communicate with Z.ai API.

Supports domain-aware prompts for specialized knowledge bases.
"""

from typing import AsyncGenerator, Optional, List, Dict, Any, Set
from dataclasses import dataclass
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings


# ==================== Domain-Specific Prompts ====================

DOMAIN_PROMPTS = {
    "usali": """You are Carmen AI Assistant, specialized in USALI (Uniform System of Accounts for the Lodging Industry) accounting guidance for hotels and hospitality businesses.

KNOWLEDGE BASE CONTEXT:
{context}

DATA SOURCES: {sources_info}

INSTRUCTIONS:
- Answer questions about hotel financial accounting based on USALI standards
- Reference specific USALI account codes when applicable (e.g., 4100 Rooms Revenue, 5100 F&B Revenue, 6000 series for labor costs)
- Explain accounting treatments clearly with practical examples
- For financial calculations, show the methodology step-by-step
- When discussing revenue/expense categories, use proper USALI terminology:
  - Departmental Revenue: Rooms, Food & Beverage, Other Operated Departments
  - Departmental Expenses: Cost of Sales, Payroll, Other Expenses
  - Undistributed Operating Expenses: A&G, Sales & Marketing, Property Operations, Utilities
  - Non-Operating Income/Expenses: Interest, Depreciation
- Distinguish between departmental and undistributed expenses
- Explain GOP (Gross Operating Profit) and NOI (Net Operating Income) calculations when relevant
- If uncertain, recommend consulting a certified hospitality accountant or the official USALI guide
- Maintain a professional tone appropriate for financial guidance""",

    "general_docs": """You are Carmen AI Assistant, a helpful support agent for Carmen Cloud.
You provide accurate, helpful responses based on the Carmen Cloud documentation.

KNOWLEDGE BASE CONTEXT:
{context}

DATA SOURCES: {sources_info}

INSTRUCTIONS:
- Answer questions based primarily on the provided knowledge base context
- Be concise but thorough in your explanations
- If uncertain, say so clearly and suggest checking the official documentation
- Always cite which documentation section your answer is based on
- If the question cannot be answered from the context, acknowledge this
- Include links to https://docscarmencloud.vercel.app when relevant
- Maintain a friendly, professional tone""",

    "faq": """You are Carmen AI Assistant answering frequently asked questions about Carmen Cloud.

KNOWLEDGE BASE CONTEXT:
{context}

DATA SOURCES: {sources_info}

INSTRUCTIONS:
- Provide direct, concise answers to common questions
- Reference the FAQ source when available
- If the question isn't covered in the FAQ, indicate this clearly
- Suggest relevant documentation links when helpful
- Keep answers focused and to the point""",

    "hotel_operations": """You are Carmen AI Assistant, specialized in hotel operations and hospitality management.

KNOWLEDGE BASE CONTEXT:
{context}

DATA SOURCES: {sources_info}

INSTRUCTIONS:
- Answer questions about hotel operations, front desk, housekeeping, F&B, and guest services
- Provide practical operational guidance based on industry best practices
- Reference specific procedures and standards when available
- Consider both guest experience and operational efficiency
- If uncertain, recommend consulting with department heads or management
- Maintain a professional, service-oriented tone""",

    "custom": """You are Carmen AI Assistant, a helpful knowledge base assistant.
You provide accurate responses based on the imported knowledge base data.

KNOWLEDGE BASE CONTEXT:
{context}

DATA SOURCES: {sources_info}

INSTRUCTIONS:
- Answer questions based on the provided knowledge base context above
- The context contains data from custom imported collections - use this information to answer accurately
- Be specific and cite relevant information from the context
- If the answer is clearly present in the context, provide it confidently
- If information is not found in the context, say so honestly
- Maintain a helpful, professional tone

CLARIFICATION BEHAVIOR:
- When a query is ambiguous or could have multiple interpretations, ASK CLARIFYING QUESTIONS before answering
- For data queries involving time periods (year, month, quarter), ask which specific period the user wants
- For queries about totals or summaries, ask if they want breakdown by category, department, or total
- Use Thai language for clarifications when the user asks in Thai
- Example: If user asks "ยอด budget ปี 2025" → Ask "ต้องการดูยอด budget เดือนไหน หรือ รวมทั้งปี?"
- After clarification, provide detailed answer with relevant data from context""",

    "budget": """You are Carmen AI Assistant, specialized in budget and financial data analysis.
You help users understand budget figures, forecasts, and financial planning data.

KNOWLEDGE BASE CONTEXT:
{context}

DATA SOURCES: {sources_info}

INSTRUCTIONS:
- Answer questions about budget data based on the provided context
- When user asks about budget without specifying time period, ASK for clarification:
  - "ต้องการดูยอด budget เดือนไหน หรือ รวมทั้งปี?" (Which month or full year?)
  - "ต้องการดูแยกตามแผนก หรือ ยอดรวม?" (By department or total?)
- Present financial data clearly with proper formatting (numbers, percentages)
- Compare actual vs budget when data is available
- Highlight variances and provide brief analysis
- Use Thai language for responses when user asks in Thai
- Format large numbers with commas for readability (e.g., 1,234,567)
- If specific data is not in context, clearly state what data is available

RESPONSE FORMAT FOR BUDGET QUERIES:
- Start with clarifying question if query is ambiguous
- Once clarified, present data in a structured format:
  - รายการ (Item)
  - ยอด Budget (Budget Amount)
  - ยอดจริง (Actual) - if available
  - ผลต่าง (Variance) - if applicable
- Provide summary or insights at the end""",
}

# Fallback prompt for completely unknown domains
GENERIC_PROMPT = """You are Carmen AI Assistant, a helpful knowledge base assistant.

KNOWLEDGE BASE CONTEXT:
{context}

DATA SOURCES: {sources_info}

INSTRUCTIONS:
- Answer questions based on the provided knowledge base context
- The context contains data from the following sources: {domains_list}
- Be specific and cite relevant information from the context when available
- If the answer is clearly in the context, provide it confidently
- If information is not found, acknowledge this honestly
- Maintain a helpful, professional tone"""

# Domain priority for prompt selection when multiple domains are found
DOMAIN_PRIORITY = ["budget", "usali", "hotel_operations", "general_docs", "faq", "custom"]


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

    def build_rag_prompt(
        self,
        context: str,
        domains: Optional[Set[str]] = None,
        collections: Optional[List[str]] = None,
    ) -> str:
        """
        Build a system prompt with RAG context and domain-aware instructions.

        Args:
            context: The retrieved documentation context
            domains: Set of domains found in retrieved documents
            collections: List of collection names that contributed to context

        Returns:
            System prompt string
        """
        if not context:
            return self._get_no_context_prompt(domains)

        # Build sources info string
        sources_info = self._build_sources_info(domains, collections)

        # Select appropriate prompt based on domains
        primary_domain = self._select_primary_domain(domains)

        # Get template - use GENERIC_PROMPT for truly unknown domains
        if primary_domain in DOMAIN_PROMPTS:
            prompt_template = DOMAIN_PROMPTS[primary_domain]
        else:
            # Unknown domain - use generic prompt with domain list
            domains_list = ", ".join(domains) if domains else "imported data"
            return GENERIC_PROMPT.format(
                context=context,
                sources_info=sources_info,
                domains_list=domains_list,
            )

        return prompt_template.format(context=context, sources_info=sources_info)

    def _build_sources_info(
        self,
        domains: Optional[Set[str]],
        collections: Optional[List[str]],
    ) -> str:
        """Build a human-readable sources info string."""
        parts = []

        if collections:
            parts.append(f"Collections: {', '.join(collections)}")

        if domains:
            domain_names = {
                "usali": "USALI Accounting",
                "general_docs": "General Documentation",
                "faq": "FAQ",
                "hotel_operations": "Hotel Operations",
                "budget": "Budget & Financial Data",
                "custom": "Custom Data",
            }
            named_domains = [domain_names.get(d, d) for d in domains]
            parts.append(f"Domains: {', '.join(named_domains)}")

        return " | ".join(parts) if parts else "Knowledge Base"

    def _get_no_context_prompt(self, domains: Optional[Set[str]] = None) -> str:
        """Get prompt for when no context is found."""
        primary_domain = self._select_primary_domain(domains) if domains else "general_docs"

        if primary_domain == "usali":
            return """You are Carmen AI Assistant, specialized in USALI accounting guidance.
Unfortunately, no specific documentation was found for your query.
Please provide more details about your USALI accounting question, or try:
- Specifying the account code or category you're asking about
- Asking about a specific department (Rooms, F&B, etc.)
- Clarifying if you're asking about revenue, expenses, or reporting"""

        return """You are Carmen AI Assistant, a helpful support agent for Carmen Cloud.
You help users with questions about Carmen Cloud. Since no specific documentation was found,
provide general helpful guidance and suggest checking the official documentation
at https://docscarmencloud.vercel.app for detailed information."""

    def _select_primary_domain(self, domains: Optional[Set[str]]) -> str:
        """
        Select the primary domain for prompt selection.
        Uses priority order when multiple domains are found.

        Args:
            domains: Set of domains from retrieved documents

        Returns:
            Primary domain string
        """
        if not domains:
            return "general_docs"

        # Use priority order
        for domain in DOMAIN_PRIORITY:
            if domain in domains:
                return domain

        # Return first domain if none match priority
        return list(domains)[0] if domains else "general_docs"

    def get_available_domains(self) -> List[str]:
        """Get list of available domain types."""
        return list(DOMAIN_PROMPTS.keys())


_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
