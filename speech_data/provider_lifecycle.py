from __future__ import annotations

import threading
import time
from typing import Any

from speech_data.profile_manager import get_active_profile
from speech_data.provider_factory import construct_provider
from speech_data.providers.base import LLMProvider


class ProviderLifecycle:
    """Own the active provider instance and provider startup readiness."""

    def __init__(self):
        self._lock = threading.RLock()
        self._provider: LLMProvider | None = None
        self._identity: tuple[str, tuple[tuple[str, str], ...]] | None = None

    def _profile_startup_identity(
        self,
        profile: dict[str, Any],
    ) -> tuple[str, tuple[tuple[str, str], ...]]:
        provider = profile.get("provider", "")
        model = profile.get("model", "")
        mmproj = profile.get("mmproj", "")

        if not isinstance(provider, str) or not provider.strip():
            provider = "llama_cpp"

        if not isinstance(model, str):
            model = ""

        if not isinstance(mmproj, str):
            mmproj = ""

        startup_inputs = (
            ("model", model.strip()),
            ("mmproj", mmproj.strip()),
        )

        return provider.strip(), startup_inputs

    def _stop_provider(self, provider: LLMProvider | None) -> None:
        if provider is None:
            return

        provider.stop()

    def get_provider_for_active_profile(self) -> LLMProvider:
        start_time = time.perf_counter()
        active_profile = get_active_profile()
        active_identity = self._profile_startup_identity(active_profile)

        with self._lock:
            if self._provider is not None and self._identity == active_identity:
                ensure_start_time = time.perf_counter()
                self._provider.ensure_running()
                ensure_elapsed_ms = (time.perf_counter() - ensure_start_time) * 1000
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                print(
                    f"[AI CLICK PERF] provider_lifecycle {elapsed_ms:.2f} ms "
                    f"reused=True replaced=False ensure_running=True "
                    f"ensure_ms={ensure_elapsed_ms:.2f}"
                )
                return self._provider

            previous_provider = self._provider
            previous_identity = self._identity
            self._print_activation_summary(active_profile)
            replacement_provider = construct_provider(active_profile)
            must_stop_before_start = (
                previous_provider is not None
                and previous_identity is not None
                and previous_identity[0] == active_identity[0]
                and previous_identity != active_identity
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
                ensure_start_time = time.perf_counter()
                replacement_provider.ensure_running()
                ensure_elapsed_ms = (time.perf_counter() - ensure_start_time) * 1000
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                print(
                    f"[AI CLICK PERF] provider_lifecycle {elapsed_ms:.2f} ms "
                    f"reused=False replaced=True ensure_running=True failed=True"
                )
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
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            print(
                f"[AI CLICK PERF] provider_lifecycle {elapsed_ms:.2f} ms "
                f"reused=False replaced=True ensure_running=True "
                f"ensure_ms={ensure_elapsed_ms:.2f}"
            )
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
