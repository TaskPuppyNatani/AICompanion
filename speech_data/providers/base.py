from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Base contract and lifecycle orchestration for text generation backends."""

    startup_timeout_seconds = 15
    poll_interval_seconds = 0.5

    def __init__(self):
        self.started_by_companion = False
        self.last_readiness_state = "not checked"

    def apply_profile_lifecycle_settings(
        self,
        profile: dict[str, Any] | None,
    ) -> None:
        """Apply optional lifecycle settings supplied by a model profile."""
        if not isinstance(profile, dict):
            return

        startup_timeout = profile.get("startup_timeout_seconds")

        if isinstance(startup_timeout, bool):
            return

        if isinstance(startup_timeout, (int, float)) and startup_timeout > 0:
            self.startup_timeout_seconds = float(startup_timeout)

    @abstractmethod
    def health_check(self) -> bool:
        """Return whether the provider is ready to accept requests."""
        ...

    @abstractmethod
    def start(self) -> None:
        """Start the provider when supported by this backend."""
        ...

    def ensure_running(self) -> None:
        """Start the provider if needed and wait until it is healthy."""
        start_time = time.monotonic()
        provider_name = type(self).__name__

        if self.health_check():
            elapsed = time.monotonic() - start_time
            print(f"Provider ready: {provider_name} ({elapsed:.2f} s)")
            return

        print(f"Starting provider: {provider_name}")
        self.start()

        deadline = time.monotonic() + self.startup_timeout_seconds

        while time.monotonic() < deadline:
            process = getattr(self, "process", None)
            if process is not None:
                return_code = process.poll()

                if return_code is not None:
                    self.last_readiness_state = (
                        f"process exited with code {return_code}"
                    )
                    elapsed = time.monotonic() - start_time
                    print(
                        f"Provider failed: {provider_name} ({elapsed:.2f} s): "
                        f"{self.last_readiness_state}"
                    )
                    raise RuntimeError(
                        f"{type(self).__name__} failed to become ready: "
                        f"{self.last_readiness_state}"
                    )

            if self.health_check():
                elapsed = time.monotonic() - start_time
                print(f"Provider ready: {provider_name} ({elapsed:.2f} s)")
                return

            time.sleep(self.poll_interval_seconds)

        elapsed = time.monotonic() - start_time
        print(
            f"Provider failed: {provider_name} ({elapsed:.2f} s): "
            f"{self.last_readiness_state}"
        )
        raise RuntimeError(
            f"{type(self).__name__} failed to become ready: "
            f"{self.last_readiness_state}"
        )

    @abstractmethod
    def stop(self) -> None:
        """Stop the provider when supported by this backend."""
        ...

    @abstractmethod
    def generate_text(self, prompt: str) -> str | None:
        """Generate a non-streaming response for the prompt."""
        ...
