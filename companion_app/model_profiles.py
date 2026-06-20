from __future__ import annotations

from typing import Any

from config import OLLAMA_MODEL_NAME
from config_store import get_config_value, set_config_value

DEFAULT_ACTIVE_MODEL_PROFILE = "fast"


def load_model_profiles() -> dict[str, dict[str, str]]:
    """Load configured model profiles from app config.

    Returns an empty mapping when config is absent or malformed.
    """
    configured_profiles = get_config_value("model_profiles", {})

    if not isinstance(configured_profiles, dict):
        return {}

    normalized: dict[str, dict[str, str]] = {}

    for profile_key, profile_value in configured_profiles.items():
        if not isinstance(profile_key, str) or not profile_key.strip():
            continue

        if not isinstance(profile_value, dict):
            continue

        model_name = profile_value.get("model_name")
        if not isinstance(model_name, str) or not model_name.strip():
            continue

        display_name = profile_value.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = profile_key.replace("_", " ").title()

        normalized[profile_key] = {
            "display_name": display_name,
            "model_name": model_name,
        }

    return normalized


def list_model_profiles() -> dict[str, dict[str, str]]:
    return load_model_profiles()


def get_active_model_profile_key() -> str:
    configured_key = get_config_value(
        "active_model_profile",
        DEFAULT_ACTIVE_MODEL_PROFILE,
    )

    if not isinstance(configured_key, str) or not configured_key.strip():
        configured_key = DEFAULT_ACTIVE_MODEL_PROFILE

    profiles = load_model_profiles()

    if not profiles:
        return configured_key

    if configured_key in profiles:
        return configured_key

    if DEFAULT_ACTIVE_MODEL_PROFILE in profiles:
        fallback_key = DEFAULT_ACTIVE_MODEL_PROFILE
    else:
        fallback_key = next(iter(profiles))

    print(
        "[MODEL] Active profile "
        f"'{configured_key}' is not configured; "
        f"falling back to profile '{fallback_key}'."
    )

    return fallback_key


def get_active_model_profile() -> dict[str, str]:
    profiles = load_model_profiles()
    profile_key = get_active_model_profile_key()

    profile = profiles.get(profile_key)
    if profile:
        return profile

    return {
        "display_name": "Default",
        "model_name": OLLAMA_MODEL_NAME,
    }


def get_active_model_name() -> str:
    profiles = load_model_profiles()

    if not profiles:
        print(
            "[MODEL] No model profiles configured; "
            f"using fallback model='{OLLAMA_MODEL_NAME}'."
        )
        return OLLAMA_MODEL_NAME

    profile_key = get_active_model_profile_key()
    profile = profiles.get(profile_key)

    if not profile:
        print(
            "[MODEL] Active profile lookup failed; "
            f"using fallback model='{OLLAMA_MODEL_NAME}'."
        )
        return OLLAMA_MODEL_NAME

    model_name = profile.get("model_name", "")
    if not isinstance(model_name, str) or not model_name.strip():
        print(
            f"[MODEL] Profile '{profile_key}' has invalid model_name; "
            f"using fallback model='{OLLAMA_MODEL_NAME}'."
        )
        return OLLAMA_MODEL_NAME

    print(f"[MODEL] Active profile='{profile_key}' model='{model_name}'")
    return model_name


def set_active_model_profile(profile_key: str) -> None:
    if not isinstance(profile_key, str) or not profile_key.strip():
        raise ValueError("profile_key must be a non-empty string")

    profiles = load_model_profiles()

    if profiles and profile_key not in profiles:
        raise ValueError(f"Unknown model profile: {profile_key}")

    set_config_value("active_model_profile", profile_key)
