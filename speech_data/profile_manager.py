from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from pathlib import Path
from collections.abc import Iterator
from typing import Any

from config import BASE_DIR, SPEECH_DATA_DIR
from config_store import get_config_value, set_config_value


PROFILES_DIR = SPEECH_DATA_DIR / "profiles"
DEFAULT_ACTIVE_PROFILE = "fast-chat"
REQUIRED_PROFILE_FIELDS = ("name", "category", "provider", "model")


class ProfileManager:
    """Load and resolve provider-owned model profiles from disk."""

    def __init__(self, profiles_dir: Path = PROFILES_DIR):
        self.profiles_dir = profiles_dir
        self._active_profile_override: ContextVar[str | None] = ContextVar(
            "active_profile_override",
            default=None,
        )

    def _normalize_profile(
        self,
        profile_key: str,
        profile_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        normalized: dict[str, Any] = {"key": profile_key}

        for field in REQUIRED_PROFILE_FIELDS:
            value = profile_data.get(field)

            if not isinstance(value, str) or not value.strip():
                print(
                    f"[MODEL] Profile '{profile_key}' missing required field '{field}'."
                )
                return None

            normalized[field] = value.strip()

        settings = profile_data.get("settings", {})
        normalized["settings"] = deepcopy(settings) if isinstance(settings, dict) else {}
        normalized["display_name"] = normalized["name"]
        return normalized

    def load_profiles(self) -> dict[str, dict[str, Any]]:
        profiles: dict[str, dict[str, Any]] = {}

        if not self.profiles_dir.is_dir():
            return profiles

        for profile_path in sorted(self.profiles_dir.glob("*.json")):
            profile_key = profile_path.stem

            try:
                with open(profile_path, "r", encoding="utf-8") as profile_file:
                    profile_data = json.load(profile_file)
            except (OSError, json.JSONDecodeError) as e:
                print(f"[MODEL] Could not load profile '{profile_path}': {e}")
                continue

            if not isinstance(profile_data, dict):
                print(f"[MODEL] Profile '{profile_path}' must be a JSON object.")
                continue

            normalized = self._normalize_profile(profile_key, profile_data)

            if normalized is not None:
                profiles[profile_key] = normalized

        return profiles

    def list_profiles(self) -> dict[str, dict[str, Any]]:
        return self.load_profiles()

    def get_active_profile_name(self) -> str:
        override_key = self._active_profile_override.get()
        if override_key is not None:
            return self._resolve_profile_name(override_key)

        configured_key = get_config_value(
            "active_model_profile",
            DEFAULT_ACTIVE_PROFILE,
        )

        if not isinstance(configured_key, str) or not configured_key.strip():
            configured_key = DEFAULT_ACTIVE_PROFILE

        configured_key = configured_key.strip()
        return self._resolve_profile_name(configured_key)

    def _resolve_profile_name(self, profile_key: str) -> str:
        profiles = self.load_profiles()

        if profile_key in profiles:
            return profile_key

        if DEFAULT_ACTIVE_PROFILE in profiles:
            if profile_key != DEFAULT_ACTIVE_PROFILE:
                print(
                    "[MODEL] Active profile "
                    f"'{profile_key}' is not configured; "
                    f"falling back to profile '{DEFAULT_ACTIVE_PROFILE}'."
                )

            return DEFAULT_ACTIVE_PROFILE

        if profiles:
            fallback_key = next(iter(profiles))
            print(
                "[MODEL] Default profile "
                f"'{DEFAULT_ACTIVE_PROFILE}' is not configured; "
                f"falling back to profile '{fallback_key}'."
            )
            return fallback_key

        return DEFAULT_ACTIVE_PROFILE

    def get_active_profile(self) -> dict[str, Any]:
        profiles = self.load_profiles()
        profile_key = self.get_active_profile_name()
        profile = profiles.get(profile_key)

        if profile is not None:
            return deepcopy(profile)

        return {
            "key": DEFAULT_ACTIVE_PROFILE,
            "name": "Fast Chat",
            "display_name": "Fast Chat",
            "category": "chat",
            "provider": "llama_cpp",
            "model": "models/chat/gemma3.gguf",
            "settings": {},
        }

    def set_active_profile(self, profile_key: str) -> bool:
        if not isinstance(profile_key, str) or not profile_key.strip():
            raise ValueError("profile_key must be a non-empty string")

        profile_key = profile_key.strip()
        profiles = self.load_profiles()

        if profile_key not in profiles:
            return False

        set_config_value("active_model_profile", profile_key)
        return True

    @contextmanager
    def use_profile(self, profile_key: str | None) -> Iterator[None]:
        if not isinstance(profile_key, str) or not profile_key.strip():
            yield
            return

        token = self._active_profile_override.set(profile_key.strip())

        try:
            yield
        finally:
            self._active_profile_override.reset(token)

    def resolve_model_path(self, profile: dict[str, Any]) -> Path:
        model = profile.get("model")

        if not isinstance(model, str) or not model.strip():
            model = self.get_active_profile()["model"]

        model_path = Path(model)

        if not model_path.is_absolute():
            model_path = BASE_DIR / model_path

        return model_path


profile_manager = ProfileManager()


def list_profiles() -> dict[str, dict[str, Any]]:
    return profile_manager.list_profiles()


def get_active_profile_name() -> str:
    return profile_manager.get_active_profile_name()


def get_active_profile() -> dict[str, Any]:
    return profile_manager.get_active_profile()


def set_active_profile(profile_key: str) -> bool:
    return profile_manager.set_active_profile(profile_key)


def use_profile(profile_key: str | None) -> Iterator[None]:
    return profile_manager.use_profile(profile_key)


def resolve_model_path(profile: dict[str, Any]) -> Path:
    return profile_manager.resolve_model_path(profile)
