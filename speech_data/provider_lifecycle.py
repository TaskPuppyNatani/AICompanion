from __future__ import annotations

import threading
from typing import Any

from speech_data.profile_manager import get_active_profile
from speech_data.provider_factory import construct_provider
from speech_data.providers.base import LLMProvider


class ProviderLifecycle:
    """Own the active provider instance and provider/model readiness."""

    def __init__(self):
        self._lock = threading.RLock()
        self._provider: LLMProvider | None = None
        self._identity: tuple[str, str] | None = None

    def _profile_identity(self, profile: dict[str, Any]) -> tuple[str, str]:
        provider = profile.get("provider", "")
        model = profile.get("model", "")

        if not isinstance(provider, str) or not provider.strip():
            provider = "llama_cpp"

        if not isinstance(model, str):
            model = ""

        return provider.strip(), model.strip()

    def _stop_provider(self, provider: LLMProvider | None) -> None:
        if provider is None:
            return

        provider.stop()

    def get_provider_for_active_profile(self) -> LLMProvider:
        active_profile = get_active_profile()
        active_identity = self._profile_identity(active_profile)

        with self._lock:
            if self._provider is not None and self._identity == active_identity:
                self._provider.ensure_running()
                return self._provider

            previous_provider = self._provider
            previous_identity = self._identity
            self._print_activation_summary(active_profile)
            replacement_provider = construct_provider(active_profile)
            must_stop_before_start = (
                previous_provider is not None
                and previous_identity is not None
                and previous_identity[0] == active_identity[0]
                and previous_identity[1] != active_identity[1]
            )

            if (
                must_stop_before_start
                and not previous_provider.started_by_companion
            ):
                raise RuntimeError(
                    "Cannot switch model for externally managed provider "
                    f"'{active_identity[0]}'."
                )

            if must_stop_before_start:
                self._stop_provider(previous_provider)

            try:
                replacement_provider.ensure_running()
            except Exception as e:
                print(f"Provider startup failed: {e!r}")
                if must_stop_before_start and previous_provider is not None:
                    try:
                        previous_provider.ensure_running()
                    except Exception as restore_error:
                        print(
                            "Provider restore failed after switch failure:",
                            repr(restore_error),
                        )

                raise

            if not must_stop_before_start:
                self._stop_provider(previous_provider)

            self._provider = replacement_provider
            self._identity = active_identity
            return self._provider

    def _print_activation_summary(self, profile: dict[str, Any]) -> None:
        profile_name = profile.get("display_name") or profile.get("name")
        profile_key = profile.get("key")
        provider = profile.get("provider", "")
        model = profile.get("model", "")

        if isinstance(profile_name, str) and profile_name.strip():
            if isinstance(profile_key, str) and profile_key.strip():
                print(f"Activating profile: {profile_name.strip()} ({profile_key})")
            else:
                print(f"Activating profile: {profile_name.strip()}")

        if isinstance(provider, str) and provider.strip():
            provider_label = provider.strip().replace("_", ".")
            print(f"Starting provider: {provider_label}")

        if isinstance(model, str) and model.strip():
            print(f"Model: {model.strip()}")


provider_lifecycle = ProviderLifecycle()


def get_provider_for_active_profile() -> LLMProvider:
    return provider_lifecycle.get_provider_for_active_profile()
