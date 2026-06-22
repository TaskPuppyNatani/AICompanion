from __future__ import annotations

from speech_data.providers.base import LLMProvider
from speech_data.providers.ollama_provider import OllamaProvider

ACTIVE_PROVIDER_NAME = "ollama"


def get_active_provider_name() -> str:
    """Return the currently active LLM provider name."""
    return ACTIVE_PROVIDER_NAME


def get_active_provider() -> LLMProvider:
    """Resolve the current active LLM provider instance."""
    provider_name = get_active_provider_name()

    if provider_name == "ollama":
        return OllamaProvider()

    print(
        "[MODEL] Unknown provider "
        f"'{provider_name}', falling back to provider='ollama'."
    )
    return OllamaProvider()
