"""Provider registry for different API formats."""

from ..base import BaseProvider
from ..models import ApiFormat
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .openai import OpenAIProvider

# Provider registry - order matters for auto-detection
# More specific providers should come first
PROVIDERS: list[type[BaseProvider]] = [
    GeminiProvider,  # Gemini has distinct format (contents, system_instruction)
    ClaudeProvider,
    OpenAIProvider,  # OpenAI is the fallback/default
]


def detect_provider(record: dict) -> type[BaseProvider]:
    """Detect the appropriate provider for a record.

    Args:
        record: Raw trace record

    Returns:
        Provider class that can handle the record
    """
    for provider_cls in PROVIDERS:
        if provider_cls.detect(record):
            return provider_cls

    # Default to OpenAI as fallback
    return OpenAIProvider


def get_provider(api_format: ApiFormat, record: dict | None = None) -> type[BaseProvider]:
    """Get the provider class for the specified format.

    Args:
        api_format: The API format ("auto", "openai", "claude", or "gemini")
        record: Optional record for auto-detection

    Returns:
        Provider class for the specified format
    """
    if api_format == "auto":
        if record is None:
            return OpenAIProvider
        return detect_provider(record)

    if api_format == "claude":
        return ClaudeProvider

    if api_format == "gemini":
        return GeminiProvider

    return OpenAIProvider


__all__ = [
    "PROVIDERS",
    "detect_provider",
    "get_provider",
    "OpenAIProvider",
    "ClaudeProvider",
    "GeminiProvider",
]
