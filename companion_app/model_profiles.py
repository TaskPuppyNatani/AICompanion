from __future__ import annotations

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

        model_name_raw = profile_value.get("model_name")
        model_name = model_name_raw.strip() if isinstance(model_name_raw, str) else ""

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


def get_active_profile_name() -> str:
    configured_key = get_config_value(
        "active_model_profile",
        DEFAULT_ACTIVE_MODEL_PROFILE,
    )

    if not isinstance(configured_key, str) or not configured_key.strip():
        configured_key = DEFAULT_ACTIVE_MODEL_PROFILE

    profiles = load_model_profiles()

    if configured_key in profiles:
        return configured_key

    fallback_key = DEFAULT_ACTIVE_MODEL_PROFILE

    if configured_key != fallback_key:
        print(
            "[MODEL] Active profile "
            f"'{configured_key}' is not configured; "
            f"falling back to profile '{fallback_key}'."
        )

    return fallback_key


def get_active_model_profile_key() -> str:
    """Backward-compatible alias for profile name resolution."""
    return get_active_profile_name()


def get_active_profile() -> dict[str, str]:
    profiles = load_model_profiles()
    profile_key = get_active_profile_name()

    profile = profiles.get(profile_key)
    if profile:
        return profile

    return {
        "display_name": "Default",
        "model_name": OLLAMA_MODEL_NAME,
    }


def get_active_model_profile() -> dict[str, str]:
    """Backward-compatible alias for active profile data."""
    return get_active_profile()


def get_active_model_name() -> str:
    profiles = load_model_profiles()
    profile_key = get_active_profile_name()
    profile = profiles.get(profile_key) or {}

    model_name = profile.get("model_name", "")
    if not isinstance(model_name, str) or not model_name.strip():
        print(
            f"[MODEL] Active profile='{profile_key}' has invalid model_name; "
            f"using fallback model='{OLLAMA_MODEL_NAME}'."
        )
        return OLLAMA_MODEL_NAME

    print(f"[MODEL] Active profile='{profile_key}' model='{model_name}'")
    return model_name


def set_active_model_profile(profile_key: str) -> bool:
    if not isinstance(profile_key, str) or not profile_key.strip():
        raise ValueError("profile_key must be a non-empty string")

    profiles = load_model_profiles()

    if profile_key not in profiles:
        return False

    set_config_value("active_model_profile", profile_key)
    return True
