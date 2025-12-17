"""
LLM client for OpenRouter with Anthropic Claude.
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from typing import List, Dict, Any, Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def get_llm(
    model: Optional[str] = None,
    temperature: float = 0,
    max_tokens: int = 4096
) -> ChatOpenAI:
    """
    Create an LLM client configured for OpenRouter with Claude.

    Args:
        model: Model identifier (defaults to settings.OPENROUTER_MODEL)
        temperature: Sampling temperature (0 = deterministic)
        max_tokens: Maximum tokens in response

    Returns:
        Configured ChatOpenAI instance
    """
    model = model or settings.OPENROUTER_MODEL

    return ChatOpenAI(
        model=model,
        openai_api_key=settings.OPENROUTER_API_KEY,
        openai_api_base=settings.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": settings.APP_URL,
            "X-Title": settings.APP_NAME
        },
        temperature=temperature,
        max_tokens=max_tokens
    )


# Available models through OpenRouter
SUPPORTED_MODELS = [
    "anthropic/claude-sonnet-4-20250514",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-opus",
    "anthropic/claude-3-haiku",
]


async def generate_response(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0
) -> str:
    """
    Generate a response using the LLM.

    Args:
        system_prompt: System message for context
        user_prompt: User message/question
        model: Optional model override
        temperature: Sampling temperature

    Returns:
        Generated response text
    """
    llm = get_llm(model=model, temperature=temperature)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    try:
        response = await llm.ainvoke(messages)
        return response.content
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise


async def generate_with_history(
    system_prompt: str,
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0
) -> str:
    """
    Generate a response with conversation history.

    Args:
        system_prompt: System message for context
        messages: List of message dicts with 'role' and 'content'
        model: Optional model override
        temperature: Sampling temperature

    Returns:
        Generated response text
    """
    llm = get_llm(model=model, temperature=temperature)

    formatted_messages = [SystemMessage(content=system_prompt)]

    for msg in messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')

        if role == 'user' or role == 'human':
            formatted_messages.append(HumanMessage(content=content))
        elif role == 'assistant' or role == 'ai':
            formatted_messages.append(AIMessage(content=content))

    try:
        response = await llm.ainvoke(formatted_messages)
        return response.content
    except Exception as e:
        logger.error(f"LLM generation with history failed: {e}")
        raise


# Global LLM instance for reuse
_llm_instance = None


def get_shared_llm() -> ChatOpenAI:
    """Get or create a shared LLM instance."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = get_llm()
    return _llm_instance
