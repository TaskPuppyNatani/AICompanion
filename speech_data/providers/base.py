from __future__ import annotations

import time
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Base contract and lifecycle orchestration for text generation backends."""

    startup_timeout_seconds = 15
    poll_interval_seconds = 0.5

    def __init__(self):
        self.started_by_companion = False

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
            if self.health_check():
                elapsed = time.monotonic() - start_time
                print(f"Provider ready: {provider_name} ({elapsed:.2f} s)")
                return

            time.sleep(self.poll_interval_seconds)

        elapsed = time.monotonic() - start_time
        print(f"Provider failed: {provider_name} ({elapsed:.2f} s)")
        raise RuntimeError(
            f"{type(self).__name__} failed to become ready"
        )

    @abstractmethod
    def stop(self) -> None:
        """Stop the provider when supported by this backend."""
        ...

    @abstractmethod
    def generate_text(self, prompt: str) -> str | None:
        """Generate a non-streaming response for the prompt."""
        ...
