from __future__ import annotations

from speech_data.profile_manager import get_active_profile
from speech_data.providers.base import LLMProvider
from speech_data.providers.llama_cpp_provider import LlamaCppProvider


def _get_provider_name(profile: dict) -> str:
    provider_name = profile.get("provider", "")

    if isinstance(provider_name, str) and provider_name.strip():
        return provider_name.strip()

    return "llama_cpp"


def get_active_provider_name() -> str:
    """Return the currently active LLM provider name."""
    return _get_provider_name(get_active_profile())


def construct_provider(profile: dict) -> LLMProvider:
    """Construct a provider instance for the profile."""
    provider_name = _get_provider_name(profile)

    if provider_name == "llama_cpp":
        return LlamaCppProvider(profile=profile)

    raise RuntimeError(
        "[MODEL] Unsupported provider "
        f"'{provider_name}'. Rivet currently supports only 'llama_cpp'."
    )


def get_active_provider() -> LLMProvider:
    """Return the ready provider for the current active profile."""
    from speech_data.provider_lifecycle import get_provider_for_active_profile

    return get_provider_for_active_profile()
