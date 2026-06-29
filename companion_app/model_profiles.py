from __future__ import annotations

from typing import Any

from speech_data.profile_manager import (
    DEFAULT_ACTIVE_PROFILE,
    get_active_profile as get_provider_profile,
    get_active_profile_name as get_provider_profile_name,
    list_profiles as list_provider_profiles,
    set_active_profile,
)


DEFAULT_ACTIVE_MODEL_PROFILE = DEFAULT_ACTIVE_PROFILE


def _to_legacy_profile(profile: dict[str, Any]) -> dict[str, Any]:
    display_name = profile.get("display_name") or profile.get("name")

    if not isinstance(display_name, str) or not display_name.strip():
        display_name = str(profile.get("key", "")).replace("-", " ").title()

    model = profile.get("model", "")

    return {
        **profile,
        "display_name": display_name.strip(),
        "model_name": model if isinstance(model, str) else "",
    }


def load_model_profiles() -> dict[str, dict[str, Any]]:
    return {
        profile_key: _to_legacy_profile(profile)
        for profile_key, profile in list_provider_profiles().items()
    }


def list_model_profiles() -> dict[str, dict[str, Any]]:
    return load_model_profiles()


def get_active_profile_name() -> str:
    return get_provider_profile_name()


def get_active_model_profile_key() -> str:
    """Backward-compatible alias for profile name resolution."""
    return get_active_profile_name()


def get_active_profile() -> dict[str, Any]:
    return _to_legacy_profile(get_provider_profile())


def get_active_model_profile() -> dict[str, Any]:
    """Backward-compatible alias for active profile data."""
    return get_active_profile()


def get_active_model_name() -> str:
    profile = get_provider_profile()
    model = profile.get("model", "")

    if isinstance(model, str) and model.strip():
        return model.strip()

    return ""


def set_active_model_profile(profile_key: str) -> bool:
    return set_active_profile(profile_key)
